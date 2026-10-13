# Fix how our authorization policies get to production

Freightline's `shipments-api` has used Cerbos for a year: the open-source PDP
runs as a sidecar in every API pod in our dev, staging and prod Kubernetes
clusters, and the policies live in git next to the API. Background is in
`/workspace/README.md`; the build, deploy and PDP config are under
`/workspace/deploy` and `/workspace/.github`, and last quarter's incident is in
`/workspace/docs/incident-2026-08-14.md`.

The policies themselves are fine. The way they reach production is not:

- The policies are copied into the sidecar image when the API is built, so a
  one-line policy fix means a full API release.
- The three environments drift: each runs whichever image was last promoted
  there, and nobody can say which policy version is live where.
- A bad policy reached prod in August because nothing tests the policies before
  they ship.
- Rolling that back took 47 minutes, because it meant a redeploy.

We want to keep using Cerbos and keep the policies in git with pull-request
review. Write `/workspace/DESIGN.md` for the platform team that:

1. recommends how policy changes should get from git to the PDPs in each
   environment,
2. explains why it fixes each of the problems above,
3. says what changes for the running PDPs and the API, and what stays the same,
   and
4. lists the concrete next steps, in order.

Do not implement anything yet; the design document is the deliverable. Cerbos
0.55.0 is installed in this sandbox if you want to try something; Docker is not
available.
