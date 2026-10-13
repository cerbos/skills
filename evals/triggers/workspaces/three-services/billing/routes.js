const express = require("express");
const { can } = require("./permissions");

const router = express.Router();

router.post("/invoices/:id/void", async (req, res) => {
  const invoice = await req.db.invoices.find(req.params.id);
  if (!can(req.user, "invoice:void", invoice)) return res.sendStatus(403);
  await req.db.invoices.update(invoice.id, { status: "void" });
  res.sendStatus(204);
});

module.exports = router;
