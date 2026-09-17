# Query plans: filtering lists by permission

`PlanResources` answers "what would make this allowed?" rather than "is this allowed?". The PDP returns the condition a resource must satisfy, and your PEP pushes that condition into the data layer as a predicate. The database does the filtering.

Reach for it whenever the answer is a *list* the user is allowed to see: index pages, search results, exports, counts, dashboards.

## Why not just check the rows you fetched

Fetching a page and running `checkResources` over it looks simpler and breaks in four ways:

- **Pagination goes wrong.** `LIMIT 20` picks the page before authorization runs, so page 1 comes back with 6 rows, page 2 with 19, and there is no honest "next page". Compensating by over-fetching is guesswork.
- **Counts and aggregates are impossible.** `COUNT`, `SUM`, `GROUP BY` and `ORDER BY … LIMIT` cannot be computed over a set you have not yet filtered.
- **The batch ceiling bites.** 50 resources per `CheckResources` request by default, so a list of 500 becomes ten round trips, and the naive per-row loop becomes 500.
- **You pay for rows nobody may see.** Read, transfer, and deserialisation costs scale with the unauthorized set, which is usually the larger one.

One `PlanResources` call per (principal, kind, action) replaces all of it, and the cost does not grow with the size of the list.

## Handle all three kinds

```
KIND_ALWAYS_ALLOWED  → run the query with no authorization predicate
KIND_ALWAYS_DENIED   → return an empty result without touching the database
KIND_CONDITIONAL     → add the translated predicate to the query
```

This is where most integration bugs live, and both failure modes are serious: treating `ALWAYS_ALLOWED` as "no condition, so nothing matches" silently blinds your admins, and treating `ALWAYS_DENIED` as "no condition, so no filter" leaks the whole table. Write the three-way branch explicitly, and make the default arm deny.

Some SDKs make this trap easy to fall into. The Java SDK's `getCondition()` returns a populated `Optional` even on an unconditional plan (it is the protobuf default instance), so check `isConditional()` first rather than `getCondition().isPresent()`.

## What ends up in the plan

The PDP partially evaluates the policy against what you sent:

- Conditions over **principal attributes** are resolved during planning and never appear in the AST.
- Conditions over **resource attributes** become `request.resource.attr.<name>` variables — unless you supplied that attribute in `resource.attr`, in which case they are resolved too.

So send in `resource.attr` only what is genuinely constant across the whole set you are about to query (the tenant you are scoped to, say). Leave out anything that varies per row: those are exactly the columns you want to filter on.

A rule whose condition references a resource attribute your schema has no column for cannot be pushed down. That is a policy design signal, not an adapter bug.

## Mapping variables to columns

Every adapter works the same way: a **mapper** from `request.resource.attr.<name>` to a column, field or path in your store. The mapper is the contract between policy vocabulary and schema vocabulary — one entry for every attribute any condition can mention. A missing entry throws or, worse in a hand-rolled adapter, drops the predicate and widens access.

Set `includeMeta` / `includeMetadata` on the request and log `meta.filterDebug` (`metadata.conditionString` in the JS SDK). It renders the AST as readable CEL and tells you immediately which paths the mapper has to cover.

Keep the mapper next to the model it maps, and revisit it whenever a policy condition gains a new attribute.

## Reference adapters

Documented, published, and covered in the [Cerbos docs](https://docs.cerbos.dev/cerbos/latest/recipes/query-plan-adapters/index.md?utm_campaign=brand_cerbos&utm_source=agent_skills&utm_medium=skill&utm_content=cerbos-pep-integration):

| Package | Language | Target | Entry point | Result |
|---|---|---|---|---|
| `@cerbos/orm-prisma` | TypeScript | Prisma (PostgreSQL, MySQL, SQLite, SQL Server, MongoDB) | `queryPlanToPrisma({ queryPlan, mapper })` | `{ kind, filters }` → a `where` argument |
| `@cerbos/orm-drizzle` | TypeScript | Drizzle (PostgreSQL, MySQL, SQLite, PlanetScale) | `queryPlanToDrizzle({ queryPlan, mapper })` | `{ kind, filter }` → `.where(...)` |
| `@cerbos/orm-mongoose` | TypeScript | MongoDB via Mongoose | `queryPlanToMongoose({ queryPlan, mapper })` | `{ kind, filters }` → `Model.find(...)` |
| `@cerbos/orm-convex` | TypeScript | Convex | `queryPlanToConvex({ queryPlan, mapper, allowPostFilter })` | `{ kind, filter, postFilter }` |
| `@cerbos/langchain-chromadb` | TypeScript | ChromaDB via LangChain.js | `queryPlanToChromaDB({ queryPlan, fieldNameMapper })` | `{ kind, filters }` → a `Where` filter |
| `cerbos-sqlalchemy` | Python | SQLAlchemy 1.4 / 2.0 | `get_query(plan, Table, attr_map, joins?)` | a `Select` you can extend |

All of them require a Cerbos client from the same language's SDK, and all of them export a `PlanKind` enum for the three-way branch.

Further reference implementations live in [`cerbos/query-plan-adapters`](https://github.com/cerbos/query-plan-adapters) but are not yet in the docs, so check their state before depending on them. Verified as of writing: Go adapters for [Ent](https://github.com/cerbos/query-plan-adapters/tree/main/ent) and [pgx](https://github.com/cerbos/query-plan-adapters/tree/main/pgx) resolve from the module proxy at `github.com/cerbos/query-plan-adapters/{ent,pgx}` with no tagged release; a Spring Data JPA adapter (`dev.cerbos:cerbos-spring-data`, translating a plan into a JPA `Specification`), an Elasticsearch adapter, and a Ruby ActiveRecord adapter are present in the repo but not published to Maven Central or RubyGems. Read the adapter's own README before wiring one in.

Cerbos ships these as reference implementations — the docs say so explicitly. Forking one to fit your schema is an expected outcome, not a failure.

### Mapper shapes differ

Each adapter names things its own way; copying a mapper between them will not work.

```typescript
// Prisma / Mongoose — objects, with relations
mapper: {
  "request.resource.attr.ownerId": { field: "ownerId" },
  "request.resource.attr.tags": { relation: { name: "tags", type: "many", field: "name" } },
}
```

```typescript
// Drizzle — straight to column objects
mapper: { "request.resource.attr.status": resources.status }
```

```typescript
// LangChain / ChromaDB — plain strings, via fieldNameMapper
fieldNameMapper: { "request.resource.attr.department": "department" }
```

```python
# SQLAlchemy — to ORM columns, with joins as a fourth argument
attr_map = {"request.resource.attr.owner_id": User.id}
query = get_query(plan, Contact, attr_map, [(User, Contact.owner_id == User.id)])
```

Prisma, Drizzle, Mongoose and ChromaDB also accept a **function** mapper (`(attr) => …`) for schemas where stripping the `request.resource.attr.` prefix is the whole rule.

### Operator coverage is not uniform

The policies you write determine which stores can express them.

- **Prisma** is the broadest: scalars (`and or not eq ne lt gt lte gte in startsWith endsWith contains isSet`) plus relation operators (`is isNot some none every exists exists_one all filter except hasIntersection`) and arbitrarily nested relations.
- **Drizzle** covers logic, comparison, strings, `isSet`, and the collection operators via correlated `EXISTS` subqueries.
- **Mongoose** maps onto `$and/$or/$nor`, `$eq/$ne/$lt/$lte/$gt/$gte`, `$in`, `$elemMatch`, and escaped regexes for string operators. `exists_one` behaves as "at least one", not "exactly one".
- **SQLAlchemy** supports `and or not eq ne lt gt le ge in`. Anything else you attach yourself with `query.where(...)`, and `operator_override_fns` lets you swap an operator's implementation for a dialect-specific one.
- **Convex** pushes only logic, comparison, `in` and `isSet` to the database; string and collection operators fall back to a JavaScript `postFilter`. That post-filter runs *after* rows are read, which reintroduces the problem the query plan solves — hence `allowPostFilter` defaults to off and the adapter throws instead. Leaving it off is a useful tripwire.
- **ChromaDB** stores flat scalar metadata, so string, existence and collection operators throw. `not` is handled by inverting the inner operator and De Morgan's law, because Chroma has no `$not`.

When an adapter cannot express a condition, the honest fixes are to reshape the policy or to denormalise the attribute into a column — not to fetch everything and filter in memory.

## Writing your own adapter

The AST is small; walking it is a day's work. Node shapes and the operator list are in [api-shapes.md](api-shapes.md). Four rules:

1. Branch on the three kinds before you look at the condition.
2. Resolve variables through an explicit allowlist — your mapper — and never interpolate a `variable` name into SQL. The names come from policy, and an unmapped name must be an error.
3. **Fail closed.** An operator you do not handle raises; it never silently drops the predicate, because a dropped predicate grants access.
4. Bind `lambda` correctly: its first operand is the loop variable, its second the body, and the body's references to that variable are scoped to the collection being filtered.

Test it against policies, not against hand-written ASTs: change a condition, re-plan, assert on the rows.

## Combining with your own filters

`AND` the authorization predicate with the application's own filters — never `OR`, and never let a user-supplied filter replace it.

```typescript
await prisma.contact.findMany({ where: { AND: [plan.filters, { archived: false }] } });
```

```typescript
await Model.find({ $and: [filters ?? {}, { archived: false }] });
```

```python
query = get_query(plan, Contact, attr_map).where(Contact.archived.is_(False))
```

## Caching

A plan depends on the principal, the resource kind, the actions, and any resource attributes you sent — not on the rows. Caching it per request is free and worthwhile when one handler runs several queries over the same kind. Caching across requests means caching an authorization decision: give it a short TTL, key it on everything that went into the request, and be sure you can explain what happens in the window after a policy or role changes.
