/// <reference path="../node_modules/@extism/js-pdk/dist/index.d.ts" />
// Proxy extension: sets the principal's department from an authoritative directory.

// Principal directory: the authoritative source of each principal's department.
const departments: Record<string, string> = {
  alice: "engineering",
  bob: "sales",
};

export function augmentCheckRequest() {
  const req = JSON.parse(Host.inputString());
  const principal = req.principal;
  if (principal) {
    const attr = principal.attr ?? {};
    const department = departments[principal.id];
    if (department) {
      attr.department = department;
    } else {
      delete attr.department; // unverified claim
    }
    principal.attr = attr;
  }
  Host.outputString(JSON.stringify(req));
}
