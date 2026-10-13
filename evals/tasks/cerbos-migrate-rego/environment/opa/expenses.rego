# Authorization for the expenses service.
#
# The gateway queries data.expenses.authz.allow with:
#   input.user     = {"id": string, "roles": [string], "department": string}
#   input.action   = "view" | "create" | "edit" | "submit" | "approve" | "delete" | "export"
#   input.resource = {"id": string, "owner": string, "department": string,
#                     "amount": number, "status": "draft" | "submitted" | "approved",
#                     "legal_hold": bool (optional; only set on expenses under legal hold)}
package expenses.authz

import rego.v1

default allow := false

# Evaluated top to bottom; the first branch whose body holds decides.
allow := false if {
	# Legal hold freezes an expense for everyone, admins included. Reading stays possible.
	input.resource.legal_hold == true
	input.action != "view"
} else := true if {
	"admin" in input.user.roles
} else := false if {
	# Contractors are confined to their own department, whatever other roles they hold.
	"contractor" in input.user.roles
	input.resource.department != input.user.department
} else := true if {
	granted_by_role
} else := true if {
	owner_may
} else := true if {
	may_approve
}

granted_by_role if {
	some role in input.user.roles
	input.action in data.role_grants[role]
}

owner_may if {
	input.resource.owner == input.user.id
	input.action == "view"
}

owner_may if {
	input.resource.owner == input.user.id
	input.action in {"edit", "submit", "delete"}
	input.resource.status == "draft"
}

may_approve if {
	input.action == "approve"
	input.resource.status == "submitted"
	input.resource.owner != input.user.id
	some role in input.user.roles
	input.resource.amount <= data.approval_limits[role]
}
