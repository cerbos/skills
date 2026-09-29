# Ticket access exceptions

Use the installed `cerbos-policy` skill. Requirements below are confirmed; proceed
with implementation. Cerbos 0.55.0 is installed directly in this sandbox. Docker
is unavailable inside the sandbox, so use the native `cerbos` binary for
compilation and tests.

`/workspace/policies/resource_policies/ticket.yaml` controls support tickets
(resource kind `ticket`, version `default`). Agents and managers view and update
tickets of their own team (principals and tickets have a string `team`
attribute), managers close their team's tickets, and principals with the
`reporter` role export ticket data for SLA reports. Keep these rules; change
the ticket policy only as the MFA requirement below needs.

Two changes are confirmed:

1. **External auditor.** An audit firm's consultant signs in as principal
   `ext-auditor-7`, and our identity provider gives them the `reporter` role.
   Their principal record always carries `engagement_ends`, an RFC 3339
   timestamp. Define this user's exceptions in a principal policy at
   `/workspace/policies/principal_policies/ext-auditor-7.yaml` (version
   `default`, no scope):
   - While the engagement is active, they may `view` any ticket, whatever its
     team. Access ends at `engagement_ends`: they may view before that instant,
     not at or after it.
   - They may never `export` tickets, even though the `reporter` role allows it.
     Other reporters keep export.

   Nothing else changes for them.
2. **MFA for closing.** The support app forwards the caller's identity-provider
   token to Cerbos as a single JWT (`auxData.jwt`). Its `amr` claim is a list of
   authentication methods (RFC 8176); a session that passed multi-factor
   authentication includes `"mfa"`. A manager may close a team ticket only when
   the token shows MFA. Requests with no token, or with a token whose `amr` is
   missing or lacks `"mfa"`, cannot close tickets.

Add no other policy files.

Write native Cerbos tests in `resource_policies/ticket_test.yaml`, with fixtures
inline or under `resource_policies/testdata/`. The tests must not depend on
today's date, and must actively cover:

- the auditor viewing tickets shortly before the engagement ends, and being
  denied once it has ended;
- the auditor denied `export`, while another reporter may export;
- a manager closing a team ticket with an MFA token, and being denied with a
  token that lacks MFA.

Compile and run the tests in normal and strict evaluation modes. The bundle must
be self-contained.
