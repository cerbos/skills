# Cerbos skills

These skills build authorization with Cerbos. Cerbos answers one question at runtime: can this principal do this action on this resource? The rules live in policy files, so changing who can do what is a policy change rather than a release.

When a request is about who can access what, load the `cerbos` skill first, even if the user never names Cerbos. It maps the need onto the right Cerbos component and hands off to the skill that implements it. Load another `cerbos-*` skill directly only when the request already names its job, such as fixing a failing policy test.

Each skill links to docs.cerbos.dev for configuration details. Check the docs rather than guessing flags or field names.
