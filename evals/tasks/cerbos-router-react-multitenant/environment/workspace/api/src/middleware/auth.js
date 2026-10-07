import { createRemoteJWKSet, jwtVerify } from "jose";

const jwks = createRemoteJWKSet(new URL(process.env.OKTA_JWKS_URL));

// Verifies the Okta access token and sets req.user = { id, tenantId, roles }.
export async function authenticate(req, res, next) {
  try {
    const token = req.header("authorization")?.replace(/^Bearer /, "");
    const { payload } = await jwtVerify(token, jwks, { audience: "api://ledgerly" });
    req.user = { id: payload.sub, tenantId: payload.tenant_id, roles: payload.roles ?? [] };
    next();
  } catch {
    res.status(401).json({ error: "unauthenticated" });
  }
}
