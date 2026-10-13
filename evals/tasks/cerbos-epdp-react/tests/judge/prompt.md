You are grading a coding agent's change to a React + Express application in your
working directory. The browser app is in `app/src/`, the Express API in
`app/server/`, Cerbos policies and PDP configuration in `cerbos/`. Ignore
`node_modules/` and `dist/`; they are dependencies and build output.

Context the agent was given: the Cerbos Hub deployment `acme-docs-prod` has ID
`F5D3RW8KJ2HQ`; its embedded PDP (ePDP) rule `docs-ui` has rule ID
`B7XK2M9QPL4R`, public access, filtered to the `document` resource. The service
PDP's Hub client credential lives in `cerbos/.env` and is for server-side use
only.

Read the code, then decide each criterion strictly from what the code does. A
criterion passes only when every part of it holds; when the code is ambiguous or
a part is missing, it fails. Do not run the app, install packages, or modify
files.

{criteria}
