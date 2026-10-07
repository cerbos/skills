# PHP PEP

Source of truth: [`cerbos/cerbos-sdk-php`](https://github.com/cerbos/cerbos-sdk-php). gRPC, request-object style.

The README's PDP examples have known defects — missing semicolons after the builder chains, no `use` statements, and one snippet passing a raw string where an `AttributeValue` is required. Use the shapes below rather than copying the README.

## Install

```bash
composer require cerbos/cerbos-sdk-php
```

PSR-4 maps `Cerbos\Sdk\` to `src/Sdk`, so the namespaces are `Cerbos\Sdk\CerbosClient`, `Cerbos\Sdk\Builder\{CerbosClientBuilder, CheckResourcesRequest, PlanResourcesRequest, Principal, Resource, ResourceEntry, AttributeValue, AuxData}` and `Cerbos\Sdk\Utility\RequestId`.

## Connecting

```php
use Cerbos\Sdk\Builder\CerbosClientBuilder;

$client = CerbosClientBuilder::newInstance("localhost:3593")
    ->withPlaintext(true)
    ->build();
```

`withPlaintext()` takes an explicit boolean here. TLS is on by default. Certificate setters take PEM **contents**, not paths: `withCaCertificate(string)`, `withTlsCertificate(string)`, `withTlsKey(string)`. Also `withMetadata(array $headers)` and `withPlayground(string $playgroundInstanceId)` — plaintext plus playground throws.

## Checking

```php
use Cerbos\Sdk\Builder\{CheckResourcesRequest, Principal, ResourceEntry, AttributeValue};
use Cerbos\Sdk\Utility\RequestId;

$request = CheckResourcesRequest::newInstance()
    ->withRequestId(RequestId::generate())
    ->withPrincipal(
        Principal::newInstance("john")
            ->withRole("employee")
            ->withAttribute("department", AttributeValue::stringValue("marketing"))
    )
    ->withResourceEntry(
        ResourceEntry::newInstance("leave_request", "xx125")
            ->withActions(["view:public", "approve"])
            ->withAttribute("owner", AttributeValue::stringValue("john"))
    );

$response = $client->checkResources($request);

if ($response->find("xx125")->isAllowed("view:public")) {
    // ...
}
```

The client surface is two calls:

```php
public function checkResources(CheckResourcesRequest $request, $headers = null): CheckResourcesResponse
public function planResources(PlanResourcesRequest $request, $headers = null): PlanResourcesResponse
```

**There is no `isAllowed` on the client and no single-resource method.** Every check goes through `checkResources`, then `CheckResourcesResponse::find(string $id)` gives you a `ResultEntry` and `ResultEntry::isAllowed(string $action)` gives the decision.

Attribute values are always `AttributeValue` objects — `AttributeValue::stringValue(...)` and friends — never bare PHP scalars.

Builders: `CheckResourcesRequest` also offers `withResourceEntries(array)`, `withAuxData`, `withIncludeMeta`, `withAllowPartialRequests`. `Principal` offers `withRoles(array)`, `withPolicyVersion`, `withAttributes(array)`, `withScope`.

## Query plan

```php
use Cerbos\Sdk\Builder\{PlanResourcesRequest, Resource};

$request = PlanResourcesRequest::newInstance()
    ->withRequestId(RequestId::generate())
    ->withActions(["approve"])
    ->withPrincipal($principal)
    ->withResource(Resource::newInstance("leave_request", "")->withPolicyVersion("20210210"));

$response = $client->planResources($request);

if ($response->isAlwaysAllowed()) {
    // no filter
} elseif ($response->isAlwaysDenied()) {
    // empty result
} else {
    applyFilter($response->getFilter());
}
```

`withActions(array)` needs Cerbos PDP v0.44.0 or later; `withAction(string)` is the older single-action form. The response also carries `getAction()`, `getActions()`, `hasValidationErrors()` and `getValidationErrors()`.

There is no PHP query plan adapter. Walk the filter AST yourself — node shapes in [api-shapes.md](api-shapes.md), and the rules for doing it safely in [query-plan.md](query-plan.md).

## JWT auxiliary data

```php
use Cerbos\Sdk\Builder\AuxData;

$request->withAuxData(AuxData::withJwt($token, "ks1"));
$request->withAuxData(AuxData::withJwts([...]));   // Cerbos\Sdk\Builder\AuxData\JWT::newInstance($token, $keySetId)
```

Available on both request builders. Semantics in [api-shapes.md](api-shapes.md).

## Laravel

```bash
composer require cerbos/cerbos-sdk-laravel
```

[`cerbos/cerbos-sdk-laravel`](https://github.com/cerbos/cerbos-sdk-laravel) auto-discovers `CerbosServiceProvider`, which binds `Cerbos\Sdk\CerbosClient` as a singleton — so you type-hint `CerbosClient` in a controller or gate and use the same API as above. `php artisan vendor:publish` writes `config/cerbos.php`:

```php
'host'        => env('CERBOS_HOST', '127.0.0.1'),
'port'        => env('CERBOS_PORT', '3593'),
'plaintext'   => env('CERBOS_PLAINTEXT', true),
'caCertPath'  => env('CERBOS_CA_CERT_PATH', ''),
'tlsCertPath' => env('CERBOS_TLS_CERT_PATH', ''),
'tlsKeyPath'  => env('CERBOS_TLS_KEY_PATH', ''),
```

The package reads the certificate files at those paths and hands the contents to the builder. Note `CERBOS_PLAINTEXT` defaults to `true`, the opposite of the bare SDK — set it to `false` and supply certificates for any deployment where the PDP is not a localhost sidecar.

The package ships no usage documentation of its own. A Laravel `Gate::define` that resolves the injected `CerbosClient` and returns `$response->find($id)->isAllowed($action)` is the natural integration point.
