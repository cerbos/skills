import type { Invoice, User } from "../types";

export function InvoiceRow({ invoice, user }: { invoice: Invoice; user: User }) {
  const isAdmin = user.roles.includes("finance_admin");
  // Acme: approvals above 10k need the approver role. TODO Globex rules.
  const canApprove =
    isAdmin ||
    (user.roles.includes("approver") && (user.tenantId !== "acme" || invoice.amount <= 10_000));

  return (
    <tr>
      <td>{invoice.number}</td>
      <td>{invoice.customerName}</td>
      <td>{invoice.amount.toLocaleString()}</td>
      <td>{invoice.status}</td>
      <td>
        <button>Edit</button>
        {canApprove && <button>Approve</button>}
        <button>Delete</button>
      </td>
    </tr>
  );
}
