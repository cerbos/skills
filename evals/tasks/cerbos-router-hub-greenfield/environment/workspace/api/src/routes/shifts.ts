import type { FastifyInstance } from "fastify";
import { db } from "../db.js";

// TODO(authz): only checks the org today. See docs/permissions.md.
export default async function shifts(app: FastifyInstance) {
  app.addHook("preHandler", app.authenticate);

  app.get("/shifts/:id", async (req, reply) => {
    const shift = await db.shifts.get(req.params.id);
    if (!shift || shift.orgId !== req.user.org_id) return reply.code(404).send();
    return shift;
  });

  app.put("/shifts/:id", async (req, reply) => {
    const shift = await db.shifts.get(req.params.id);
    if (!shift || shift.orgId !== req.user.org_id) return reply.code(404).send();
    return db.shifts.update(shift.id, req.body);
  });

  app.post("/locations/:locationId/schedule/publish", async (req) => {
    return db.schedules.publish(req.params.locationId, req.user.org_id);
  });

  app.post("/shifts/:id/swap-requests/:swapId/approve", async (req) => {
    return db.swaps.approve(req.params.swapId, req.user.sub);
  });
}
