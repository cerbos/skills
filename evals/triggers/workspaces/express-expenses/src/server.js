import express from "express";

const app = express();
app.use(express.json());

// In production this comes from the session; here it's a header for testing.
app.use((req, _res, next) => {
  req.user = JSON.parse(req.get("x-user") ?? "{}");
  next();
});

const expenses = new Map([
  ["exp-1", { id: "exp-1", team: "sales", amount: 1200, submittedBy: "sam", status: "pending" }],
  ["exp-2", { id: "exp-2", team: "sales", amount: 7500, submittedBy: "sam", status: "pending" }],
  ["exp-3", { id: "exp-3", team: "engineering", amount: 300, submittedBy: "ali", status: "pending" }],
]);

app.get("/expenses/:id", (req, res) => {
  const expense = expenses.get(req.params.id);
  if (!expense) return res.sendStatus(404);
  res.json(expense);
});

app.post("/expenses/:id/approve", (req, res) => {
  const expense = expenses.get(req.params.id);
  if (!expense) return res.sendStatus(404);

  // TODO: who is allowed to approve?
  expense.status = "approved";
  expense.approvedBy = req.user.id;
  res.json(expense);
});

app.listen(3000, () => console.log("expenses-api on :3000"));
