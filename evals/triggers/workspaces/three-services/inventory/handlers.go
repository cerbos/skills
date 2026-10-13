package inventory

import "net/http"

func AdjustStock(w http.ResponseWriter, r *http.Request) {
	role := r.Header.Get("X-User-Role")
	if !Can(role, "stock:adjust") {
		http.Error(w, "forbidden", http.StatusForbidden)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
