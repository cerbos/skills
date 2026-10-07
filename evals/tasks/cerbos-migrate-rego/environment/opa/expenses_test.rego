package expenses.authz_test

import rego.v1

import data.expenses.authz

draft := {"id": "e1", "owner": "u1", "department": "sales", "amount": 120, "status": "draft"}

submitted := {"id": "e2", "owner": "u1", "department": "sales", "amount": 4000, "status": "submitted"}

test_owner_edits_draft if {
	authz.allow with input as {"user": {"id": "u1", "roles": ["employee"], "department": "sales"}, "action": "edit", "resource": draft}
}

test_owner_cannot_edit_submitted if {
	not authz.allow with input as {"user": {"id": "u1", "roles": ["employee"], "department": "sales"}, "action": "edit", "resource": submitted}
}

test_manager_approves_within_limit if {
	authz.allow with input as {"user": {"id": "m1", "roles": ["manager"], "department": "sales"}, "action": "approve", "resource": submitted}
}

test_finance_exports if {
	authz.allow with input as {"user": {"id": "f1", "roles": ["finance"], "department": "finance"}, "action": "export", "resource": submitted}
}
