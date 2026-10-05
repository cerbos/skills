// Documents API. Every request that changes a document is authorized by the
// Cerbos service PDP before it runs.
import express from "express";
import { HTTP } from "@cerbos/http";

const port = Number(process.env.PORT ?? 3001);
const cerbos = new HTTP(process.env.CERBOS_URL ?? "http://localhost:3592");

const users = {
  alice: { id: "alice", name: "Alice (member, Engineering)", roles: ["member"], department: "engineering" },
  bob: { id: "bob", name: "Bob (member, Finance)", roles: ["member"], department: "finance" },
  carol: { id: "carol", name: "Carol (admin)", roles: ["admin"], department: "engineering" },
};

let documents = [
  { id: "doc-1", title: "Q3 roadmap", owner: "alice", department: "engineering", status: "published" },
  { id: "doc-2", title: "Incident review draft", owner: "alice", department: "engineering", status: "draft" },
  { id: "doc-3", title: "Budget 2027", owner: "bob", department: "finance", status: "published" },
  { id: "doc-4", title: "Vendor shortlist", owner: "bob", department: "finance", status: "draft" },
  { id: "doc-5", title: "Onboarding guide", owner: "carol", department: "engineering", status: "published" },
];

function toPrincipal(user) {
  return { id: user.id, roles: user.roles, attr: { department: user.department } };
}

function toResource(doc) {
  return {
    kind: "document",
    id: doc.id,
    attr: { owner: doc.owner, department: doc.department, status: doc.status },
  };
}

async function allowed(user, doc, action) {
  return cerbos.isAllowed({ principal: toPrincipal(user), resource: toResource(doc), action });
}

const app = express();
app.use(express.json());

// Demo authentication: the gateway sets X-User-Id from the session.
app.use("/api", (req, res, next) => {
  if (req.path === "/users") return next();
  const user = users[req.header("x-user-id") ?? ""];
  if (!user) return res.status(401).json({ error: "Not signed in" });
  req.user = user;
  next();
});

app.get("/api/users", (_req, res) => {
  res.json(Object.values(users).map(({ id, name }) => ({ id, name })));
});

app.get("/api/me", (req, res) => {
  res.json(req.user);
});

app.get("/api/documents", async (req, res, next) => {
  try {
    const result = await cerbos.checkResources({
      principal: toPrincipal(req.user),
      resources: documents.map((doc) => ({ resource: toResource(doc), actions: ["view"] })),
    });
    res.json(documents.filter((doc) => result.isAllowed({ resource: { kind: "document", id: doc.id }, action: "view" })));
  } catch (error) {
    next(error);
  }
});

app.put("/api/documents/:id", async (req, res, next) => {
  try {
    const doc = documents.find((d) => d.id === req.params.id);
    if (!doc) return res.status(404).json({ error: "Not found" });
    if (!(await allowed(req.user, doc, "edit"))) {
      return res.status(403).json({ error: "You cannot edit this document" });
    }
    if (typeof req.body?.title === "string" && req.body.title.trim()) {
      doc.title = req.body.title.trim();
    }
    res.json(doc);
  } catch (error) {
    next(error);
  }
});

app.delete("/api/documents/:id", async (req, res, next) => {
  try {
    const doc = documents.find((d) => d.id === req.params.id);
    if (!doc) return res.status(404).json({ error: "Not found" });
    if (!(await allowed(req.user, doc, "delete"))) {
      return res.status(403).json({ error: "You cannot delete this document" });
    }
    documents = documents.filter((d) => d.id !== doc.id);
    res.status(204).end();
  } catch (error) {
    next(error);
  }
});

app.listen(port, () => {
  console.log(`Documents API listening on http://localhost:${port}`);
});
