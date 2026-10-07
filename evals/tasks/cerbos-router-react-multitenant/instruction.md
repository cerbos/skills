# Permissions design for Ledgerly

Ledgerly is our B2B invoicing product: a React app in `/workspace/web` and an
Express API in `/workspace/api` (see `/workspace/README.md`). Permissions are
currently `if` statements copied between React components and Express routes,
and it is going badly:

- People see **Edit**, **Approve** and **Delete** buttons they aren't allowed to
  use, and only find out when the click fails. The invoice list shows up to 500
  invoices, and hiding the buttons must not make that page noticeably slower.
- A security review found that editing and deleting an invoice are only
  "protected" by the React app hiding the buttons. Anyone with a token and
  `curl` can do it. The API has to enforce every rule itself.
- Customers want different rules. Our defaults: clerks edit draft invoices,
  approvers approve, finance admins do anything, viewers only read. Acme
  requires the `approver` role for invoices above $10,000 and forbids deleting
  invoices that have been sent. Globex lets clerks approve invoices up to $5,000.
  More customers will ask for their own variations, and we don't want a release
  each time one does.

We've decided to use Cerbos for authorization, but nobody on the team knows it
yet. Before anyone writes code, write `/workspace/DESIGN.md` for the team that:

1. recommends which parts of Cerbos to use and how they fit together across the
   React app, the API and our three environments,
2. explains why each part is the right fit for the problems above,
3. calls out the approaches we should avoid, and
4. lists the concrete next implementation steps, in order.

Do not implement anything yet; the design document is the deliverable. Cerbos
0.55.0 is installed in this sandbox if you want to try something; Docker is not
available.
