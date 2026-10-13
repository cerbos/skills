package inventory

// Same table as the orders service, last synced a year ago.
var permissions = map[string][]string{
	"admin":     {"stock:read", "stock:adjust", "order:cancel"},
	"warehouse": {"stock:read", "stock:adjust"},
	"support":   {"stock:read", "order:cancel", "order:refund"},
}

func Can(role, action string) bool {
	if role == "admin" {
		return true
	}
	for _, a := range permissions[role] {
		if a == action {
			return true
		}
	}
	return false
}
