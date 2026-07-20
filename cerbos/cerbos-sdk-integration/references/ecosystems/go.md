# Go integration recipe

**SDK packages**: `github.com/cerbos/cerbos-sdk-go` ([pkg.go.dev](https://pkg.go.dev/github.com/cerbos/cerbos-sdk-go/cerbos))
**Live sources — fetch these before writing any integration code:**
- SDK repo README: https://raw.githubusercontent.com/cerbos/cerbos-sdk-go/main/README.md
- SDK API docs: https://pkg.go.dev/github.com/cerbos/cerbos-sdk-go/cerbos (client), https://pkg.go.dev/github.com/cerbos/cerbos-sdk-go/testutil (test harness)
- Docs index: https://docs.cerbos.dev/llms.txt

## 1. Client setup

```
go get github.com/cerbos/cerbos-sdk-go
```

The Go SDK talks to the PDP over **gRPC** (TCP or Unix domain socket). Use it for all Go
services; the PDP's HTTP/REST API is only for clients that cannot speak gRPC. Construct
**one client per process** at startup and inject it — never per request (it owns a gRPC
connection pool).

```go
import "github.com/cerbos/cerbos-sdk-go/cerbos"

func newCerbosClient() (*cerbos.GRPCClient, error) {
	addr := os.Getenv("CERBOS_ADDRESS") // e.g. "localhost:3593" or "unix:/var/sock/cerbos"
	if addr == "" {
		addr = "localhost:3593"
	}
	opts := []cerbos.Opt{cerbos.WithConnectTimeout(3 * time.Second)}
	if ca := os.Getenv("CERBOS_TLS_CA_CERT"); ca != "" {
		opts = append(opts, cerbos.WithTLSCACert(ca))
	} else {
		opts = append(opts, cerbos.WithPlaintext()) // local dev / same-host sidecar only
	}
	return cerbos.New(addr, opts...)
}
```

Other options (see pkg.go.dev for the full set): `WithTLSClientCert(cert, key)`,
`WithTLSInsecure()` (never in production), `WithMaxRetries(n)`, `WithRetryTimeout(d)`.

## 2. Principal construction

One canonical helper converts the app's auth context into a `*cerbos.Principal`. Every
callsite uses it; nobody builds principals inline. Store it in `context.Context` from the
auth middleware so handlers and service methods retrieve it uniformly.

```go
package authz

import (
	"context"
	"errors"

	"github.com/cerbos/cerbos-sdk-go/cerbos"
)

type principalKey struct{}

var ErrNoPrincipal = errors.New("no principal in context")

// PrincipalFromClaims maps verified JWT claims (or session data) to a Cerbos principal.
// Adapt the claim names to your IdP.
func PrincipalFromClaims(claims map[string]any) *cerbos.Principal {
	sub, _ := claims["sub"].(string)
	roles := toStringSlice(claims["roles"]) // your claim → []string helper

	return cerbos.NewPrincipal(sub, roles...).
		WithAttr("email", claims["email"]).
		WithAttr("department", claims["department"])
}

func ContextWithPrincipal(ctx context.Context, p *cerbos.Principal) context.Context {
	return context.WithValue(ctx, principalKey{}, p)
}

func PrincipalFromContext(ctx context.Context) (*cerbos.Principal, error) {
	p, ok := ctx.Value(principalKey{}).(*cerbos.Principal)
	if !ok || p == nil {
		return nil, ErrNoPrincipal
	}
	return p, nil
}
```

Only put **identity** facts on the principal (id, roles, org, department); resource facts
belong on the resource. If the app already has a `User` struct, adapt from that instead:
`func CerbosPrincipal(u *User) *cerbos.Principal`.

## 3. Framework integration points

Per [ARCHITECTURE.md](../ARCHITECTURE.md): authentication middleware builds the principal;
**resource-level checks live in the handler/service layer** where the resource is loaded.
Middleware-level checks are only for coarse, resource-independent gates.

### net/http (stdlib)

```go
// Auth middleware: verify token, stash principal. Runs before everything.
func AuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		claims, err := verifyToken(r) // your existing JWT/session verification
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		ctx := authz.ContextWithPrincipal(r.Context(), authz.PrincipalFromClaims(claims))
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// Handler: load resource, then check. Fail closed on any error.
func (s *Server) getOrder(w http.ResponseWriter, r *http.Request) {
	principal, err := authz.PrincipalFromContext(r.Context())
	if err != nil {
		http.Error(w, "unauthorized", http.StatusUnauthorized)
		return
	}
	order, err := s.store.GetOrder(r.Context(), r.PathValue("id"))
	if err != nil {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	resource := cerbos.NewResource("order", order.ID).
		WithAttr("ownerId", order.OwnerID).
		WithAttr("status", order.Status)

	allowed, err := s.cerbos.IsAllowed(r.Context(), principal, resource, "view")
	if err != nil || !allowed {
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	writeJSON(w, order)
}
```

### chi

chi uses stdlib middleware — `AuthMiddleware` above works unchanged. Scope it and do
resource checks in handlers exactly as above:

```go
r := chi.NewRouter()
r.Route("/orders", func(r chi.Router) {
	r.Use(AuthMiddleware)
	r.Get("/{id}", s.getOrder) // chi.URLParam(r, "id") instead of r.PathValue
})
```

### gin

```go
func AuthMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		claims, err := verifyToken(c.Request)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "unauthorized"})
			return
		}
		ctx := authz.ContextWithPrincipal(c.Request.Context(), authz.PrincipalFromClaims(claims))
		c.Request = c.Request.WithContext(ctx)
		c.Next()
	}
}
```

Handlers follow the same shape as the net/http example: `authz.PrincipalFromContext(c.Request.Context())`,
load the resource via `c.Param("id")`, call `IsAllowed` with `c.Request.Context()`, and
`c.AbortWithStatusJSON(http.StatusForbidden, ...)` when denied or on error.

### gRPC services

Place a **unary interceptor** for authentication (token → principal in context). Resource
checks stay in the service methods — the interceptor cannot see the loaded resource.

```go
func AuthUnaryInterceptor(ctx context.Context, req any, info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler) (any, error) {
	md, _ := metadata.FromIncomingContext(ctx)
	claims, err := verifyBearer(md.Get("authorization"))
	if err != nil {
		return nil, status.Error(codes.Unauthenticated, "unauthenticated")
	}
	return handler(authz.ContextWithPrincipal(ctx, authz.PrincipalFromClaims(claims)), req)
}

// In the service method: same pattern as HTTP handlers.
func (s *OrderService) GetOrder(ctx context.Context, req *pb.GetOrderRequest) (*pb.Order, error) {
	principal, err := authz.PrincipalFromContext(ctx)
	if err != nil {
		return nil, status.Error(codes.Unauthenticated, "unauthenticated")
	}
	order, err := s.store.GetOrder(ctx, req.GetId())
	if err != nil {
		return nil, status.Error(codes.NotFound, "not found")
	}
	resource := cerbos.NewResource("order", order.ID).WithAttr("ownerId", order.OwnerID)
	allowed, err := s.cerbos.IsAllowed(ctx, principal, resource, "view")
	if err != nil || !allowed {
		return nil, status.Error(codes.PermissionDenied, "forbidden")
	}
	return toProto(order), nil
}
```

Register with `grpc.NewServer(grpc.ChainUnaryInterceptor(AuthUnaryInterceptor))`. A
second interceptor may map `info.FullMethod` to coarse, resource-independent action gates,
but resource checks stay in methods.

## 4. Single-resource checks

`IsAllowed` for one action; `CheckResources` to batch actions (and resources) in one PDP
round trip — e.g. computing UI capability flags:

```go
resource := cerbos.NewResource("order", order.ID).
	WithAttr("ownerId", order.OwnerID).
	WithAttr("status", order.Status)

resp, err := s.cerbos.CheckResources(ctx, principal,
	cerbos.NewResourceBatch().Add(resource, "view", "update", "cancel"))
if err != nil {
	return nil, fmt.Errorf("authorization check failed: %w", err) // fail closed
}
res := resp.GetResource(order.ID)
if err := res.Err(); err != nil {
	return nil, fmt.Errorf("authorization check failed: %w", err)
}
perms := Permissions{
	CanView:   res.IsAllowed("view"),
	CanUpdate: res.IsAllowed("update"),
	CanCancel: res.IsAllowed("cancel"),
}
```

## 5. List filtering

Never load-then-filter in memory. `PlanResources` returns a filter to push into the query:

```go
import enginev1 "github.com/cerbos/cerbos/api/genpb/cerbos/engine/v1"

plan, err := s.cerbos.PlanResources(ctx, principal, cerbos.NewResource("order", ""), "view")
if err != nil {
	return nil, fmt.Errorf("plan resources: %w", err) // fail closed: no plan, no list
}
filter := plan.GetFilter()

switch filter.GetKind() {
case enginev1.PlanResourcesFilter_KIND_ALWAYS_DENIED:
	return []Order{}, nil // empty list, not an error
case enginev1.PlanResourcesFilter_KIND_ALWAYS_ALLOWED:
	return s.store.ListOrders(ctx, "", nil) // no extra WHERE clause
case enginev1.PlanResourcesFilter_KIND_CONDITIONAL:
	expr, ok := filter.GetCondition().GetNode().(*enginev1.PlanResourcesFilter_Expression_Operand_Expression)
	if !ok {
		return nil, errors.New("unexpected plan condition shape")
	}
	where, args, err := BuildPredicate(expr) // adapter below
	if err != nil {
		return nil, fmt.Errorf("translate query plan: %w", err)
	}
	return s.store.ListOrders(ctx, where, args)
default:
	return nil, errors.New("unspecified plan filter kind")
}
```

There is no maintained Go query-plan adapter library — write `BuildPredicate` in the
application, targeting its query layer (a SQL `WHERE` string + positional args for
pgx/`database/sql`, a predicate for Ent/sqlc/GORM, and so on). The hand-walk pattern is
the same for every target: recursively
switch on `Expression.Operator` — `and`/`or`/`not` recurse over operands; binary operators
(`eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in`, ...) map to SQL operators; operand nodes are
`Operand_Expression` (recurse), `Operand_Variable` (column reference) or `Operand_Value`
(bind parameter — never inline it). Variables arrive as `request.resource.attr.<name>`;
strip the prefix and map to a column through an explicit **allowlist**
(`map[string]string{"ownerId": "owner_id", ...}`). Reject unknown fields and unknown
operators with an error — that fails closed and surfaces policy/schema drift immediately.

## 6. Shadow-mode wrapper

Implements the shadow-check pattern from [ARCHITECTURE.md](../ARCHITECTURE.md): the legacy
boolean stays authoritative in shadow mode, Cerbos runs concurrently and can never block or
fail the response, mismatches are logged as structured JSON, and each callsite selects its
mode via config so endpoints cut over individually.

```go
package authz

import (
	"context"
	"log/slog"
	"os"
	"strings"
	"time"

	"github.com/cerbos/cerbos-sdk-go/cerbos"
)

type Mode string

const (
	ModeShadow  Mode = "shadow"
	ModeEnforce Mode = "enforce"
)

// ModeFor reads the per-callsite cutover flag, e.g. AUTHZ_MODE_ORDERS_GET=enforce.
// Defaults to shadow so new callsites are always safe.
func ModeFor(callsite string) Mode {
	key := "AUTHZ_MODE_" + strings.ToUpper(strings.ReplaceAll(callsite, ".", "_"))
	if os.Getenv(key) == string(ModeEnforce) {
		return ModeEnforce
	}
	return ModeShadow
}

type ShadowChecker struct {
	Client  *cerbos.GRPCClient
	Logger  *slog.Logger
	Timeout time.Duration // short, e.g. 200*time.Millisecond
}

type CheckInput struct {
	Endpoint     string // logical callsite, e.g. "orders.get"
	Principal    *cerbos.Principal
	Resource     *cerbos.Resource
	Action       string
	PrincipalID  string // passed explicitly: needed for the mismatch log
	ResourceKind string
	ResourceID   string
	RequestID    string
}

// ShadowCheck returns the authoritative decision for this callsite.
//
// Shadow mode: returns the legacy decision immediately. The Cerbos check runs in a
// goroutine on a context detached from request cancellation, bounded by Timeout; it never
// delays or fails the response. A differing (or errored) Cerbos result logs one line.
//
// Enforce mode: returns the Cerbos decision; errors and timeouts deny (fail closed).
func (s *ShadowChecker) ShadowCheck(ctx context.Context, mode Mode, in CheckInput, legacy bool) bool {
	if mode == ModeEnforce {
		cctx, cancel := context.WithTimeout(ctx, s.Timeout)
		defer cancel()
		allowed, err := s.Client.IsAllowed(cctx, in.Principal, in.Resource, in.Action)
		if err != nil {
			s.Logger.ErrorContext(ctx, "cerbos_check_error",
				slog.String("endpoint", in.Endpoint), slog.String("request_id", in.RequestID),
				slog.String("error", err.Error()))
			return false // fail closed
		}
		return allowed
	}

	// Shadow mode: fire and compare in the background.
	go func() {
		cctx, cancel := context.WithTimeout(context.WithoutCancel(ctx), s.Timeout)
		defer cancel()
		allowed, err := s.Client.IsAllowed(cctx, in.Principal, in.Resource, in.Action)
		if err != nil {
			s.Logger.Warn("cerbos_shadow_error",
				slog.String("endpoint", in.Endpoint), slog.String("request_id", in.RequestID),
				slog.String("error", err.Error()))
			return
		}
		if allowed != legacy {
			s.Logger.Warn("cerbos_shadow_mismatch",
				slog.String("event", "cerbos_shadow_mismatch"),
				slog.String("endpoint", in.Endpoint),
				slog.String("principal_id", in.PrincipalID),
				slog.String("resource_kind", in.ResourceKind),
				slog.String("resource_id", in.ResourceID),
				slog.String("action", in.Action),
				slog.Bool("legacy", legacy),
				slog.Bool("cerbos", allowed),
				slog.String("request_id", in.RequestID))
		}
	}()
	return legacy
}
```

Callsite usage — the legacy check stays exactly where it was:

```go
legacy := s.legacyACL.CanView(user, order) // existing authorization logic, untouched
allowed := s.shadow.ShadowCheck(r.Context(), authz.ModeFor("orders.get"), authz.CheckInput{
	Endpoint: "orders.get", Principal: principal, Resource: resource, Action: "view",
	PrincipalID: user.ID, ResourceKind: "order", ResourceID: order.ID,
	RequestID: requestIDFrom(r.Context()),
}, legacy)
if !allowed {
	http.Error(w, "forbidden", http.StatusForbidden)
	return
}
```

Use `slog.NewJSONHandler` so mismatch lines are queryable. Drive the cutover by watching
each endpoint's mismatch rate reach zero, then flipping its env var to `enforce`. Delete
the legacy check only after enforce has been stable.

## 7. Testing

The SDK ships a Docker-based PDP launcher in
`github.com/cerbos/cerbos-sdk-go/testutil` — the idiomatic choice for Go tests
(testcontainers-go with a `GenericContainer` running `ghcr.io/cerbos/cerbos` and mounting
the policy dir works equally well). Point it at a test policies directory and run real
checks:

```go
import (
	"testing"

	"github.com/cerbos/cerbos-sdk-go/cerbos"
	"github.com/cerbos/cerbos-sdk-go/testutil"
)

func TestOrderAuthorization(t *testing.T) {
	ctx := t.Context()

	pdp, err := testutil.LaunchCerbosServer(ctx, testutil.LaunchConf{
		PolicyDir: "../../policies", // repo's policy directory, or a testdata copy
	})
	if err != nil {
		t.Fatalf("launch cerbos: %v", err)
	}
	t.Cleanup(func() { _ = pdp.Stop() })
	if err := pdp.WaitForReady(ctx); err != nil {
		t.Fatalf("cerbos not ready: %v", err)
	}
	client, err := cerbos.New("passthrough:///"+pdp.GRPCAddr(), cerbos.WithPlaintext())
	if err != nil {
		t.Fatalf("create client: %v", err)
	}

	principal := cerbos.NewPrincipal("alice", "customer").WithAttr("department", "sales")
	other := cerbos.NewResource("order", "o2").WithAttr("ownerId", "bob")

	if allowed, err := client.IsAllowed(ctx, principal, other, "view"); err != nil || allowed {
		t.Errorf("expected alice to be denied on bob's order: allowed=%v err=%v", allowed, err)
	}
}
```

For handler/service tests, inject the test client through the same constructor the app
uses. Pin the container via the `CERBOS_TEST_CONTAINER_REPO`/`CERBOS_TEST_CONTAINER_TAG`
env vars in CI. Pure policy logic belongs in Cerbos's own YAML policy tests
(`cerbos compile`); Go tests should cover the integration seams — principal mapping,
resource attributes, plan-to-SQL translation, fail-closed paths.

## 8. Local dev PDP

`docker-compose.yaml`:

```yaml
services:
  cerbos:
    image: ghcr.io/cerbos/cerbos:latest
    command: ["server"]
    ports:
      - "3592:3592" # HTTP (API playground/curl)
      - "3593:3593" # gRPC (the Go SDK)
    volumes:
      - ./policies:/policies
```

The container's default configuration serves policies from `/policies` on disk with watch
enabled — edit a policy file and the PDP reloads it. Run the app with
`CERBOS_ADDRESS=localhost:3593` (no `CERBOS_TLS_CA_CERT`, so the client from section 1
connects in plaintext).
