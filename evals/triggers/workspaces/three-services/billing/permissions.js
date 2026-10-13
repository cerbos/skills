// Copied from the orders service, then edited.
const PERMISSIONS = {
  admin: ["invoice:read", "invoice:create", "invoice:void", "order:refund"],
  support: ["invoice:read", "order:refund"],
  finance: ["invoice:read", "invoice:create", "invoice:void"],
  customer: ["invoice:read"],
};

function can(user, action, invoice) {
  if (user.isSuperuser) return true;
  const allowed = PERMISSIONS[user.role] || [];
  if (!allowed.includes(action)) return false;
  if (user.role === "customer" && invoice) return invoice.customerId === user.id;
  return true;
}

module.exports = { can };
