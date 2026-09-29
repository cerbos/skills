/// <reference path="../node_modules/@extism/js-pdk/dist/index.d.ts" />
// Route extension: answers whether a user may view a document, using the PDP.

// Principal directory: the authoritative source of each principal's department.
const departments: Record<string, string> = {
  alice: "engineering",
  bob: "sales",
};

// Document catalogue: owning department and tenant of each document.
const documents: Record<string, { department: string; tenant: string }> = {
  "eng-acme": { department: "engineering", tenant: "acme" },
  "sales-acme": { department: "sales", tenant: "acme" },
  "eng-globex": { department: "engineering", tenant: "globex" },
};

type Values = Record<string, { values?: string[] }>;

function first(values: Values | undefined, key: string): string {
  return values?.[key]?.values?.[0] ?? "";
}

// Synapse expects base64 response bodies.
function jsonResponse(status: number, body: string) {
  return {
    status,
    headers: { "content-type": { values: ["application/json"] } },
    body: btoa(body),
  };
}

export function handleHTTPRoute() {
  const req = JSON.parse(Host.inputString());
  const documentId = first(req.queryParams, "id");
  const document = documents[documentId];
  if (!document) {
    Host.outputString(JSON.stringify({ httpResponse: jsonResponse(404, '{"error": "unknown document"}') }));
    return;
  }

  const userId = first(req.headers, "X-User-Id");
  const attr: Record<string, string> = { tenant: first(req.headers, "X-Tenant") };
  if (userId in departments) {
    attr.department = departments[userId];
  }

  Host.outputString(JSON.stringify({
    cerbosMapping: {
      checkRequest: {
        principal: { id: userId, roles: ["employee"], attr },
        resources: [{ resource: { id: documentId, kind: "document", attr: document }, actions: ["view"] }],
      },
      allowResponse: jsonResponse(200, '{"allowed": true}'),
      denyResponse: jsonResponse(403, '{"allowed": false}'),
    },
  }));
}
