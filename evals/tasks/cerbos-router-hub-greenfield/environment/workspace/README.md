# Rosterly

Shift scheduling for multi-site clinics. Five engineers, seed-funded, first
paying customers in pilot.

- `api/` — `schedules-api`, TypeScript on Fastify (Node 22). Runs on AWS ECS
  Fargate in `staging` and `prod` (3 tasks in prod). Postgres on RDS. Users
  sign in with Auth0; the access token carries `sub`, `org_id`,
  `location_ids` and `roles` (`staff`, `manager`, `org_admin`).
- `infra/` — the ECS task definition.
- `docs/permissions.md` — the access rules product has signed off.
- `docs/roadmap.md` — what is coming in the next year.

There is no authorization yet beyond "signed in and in the right org"
(`api/src/routes/shifts.ts`).
