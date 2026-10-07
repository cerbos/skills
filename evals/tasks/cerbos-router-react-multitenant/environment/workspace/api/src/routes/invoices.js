import { Router } from "express";
import { db } from "../db.js";

export const invoices = Router();

invoices.get("/", async (req, res) => {
  const rows = await db.query("select * from invoices where tenant_id = $1 order by created_at desc limit 500", [
    req.user.tenantId,
  ]);
  res.json(rows);
});

invoices.post("/:id/approve", async (req, res) => {
  const invoice = await db.one("select * from invoices where id = $1 and tenant_id = $2", [req.params.id, req.user.tenantId]);
  const isAdmin = req.user.roles.includes("finance_admin");
  if (!isAdmin && !req.user.roles.includes("approver")) return res.status(403).end();
  if (req.user.tenantId === "acme" && invoice.amount > 10_000 && !isAdmin) return res.status(403).end();
  await db.query("update invoices set status = 'approved', approved_by = $1 where id = $2", [req.user.id, invoice.id]);
  res.status(204).end();
});

// Security review: the UI hides these for viewers, but nothing checks here.
invoices.put("/:id", async (req, res) => {
  await db.query("update invoices set lines = $1 where id = $2 and tenant_id = $3", [req.body.lines, req.params.id, req.user.tenantId]);
  res.status(204).end();
});

invoices.delete("/:id", async (req, res) => {
  await db.query("delete from invoices where id = $1 and tenant_id = $2", [req.params.id, req.user.tenantId]);
  res.status(204).end();
});
