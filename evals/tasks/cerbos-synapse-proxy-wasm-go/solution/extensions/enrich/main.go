// Proxy extension: sets the principal's department from an authoritative directory.
package main

import (
	"encoding/json"

	"github.com/extism/go-pdk"
)

// Principal directory: the authoritative source of each principal's department.
var departments = map[string]string{
	"alice": "engineering",
	"bob":   "sales",
}

//go:wasmexport augmentCheckRequest
func augmentCheckRequest() int32 {
	// A generic map round-trips every field the caller sent.
	var req map[string]any
	if err := json.Unmarshal(pdk.Input(), &req); err != nil {
		pdk.SetError(err)
		return 1
	}
	if principal, ok := req["principal"].(map[string]any); ok {
		attr, _ := principal["attr"].(map[string]any)
		if attr == nil {
			attr = map[string]any{}
		}
		id, _ := principal["id"].(string)
		if department, known := departments[id]; known {
			attr["department"] = department
		} else {
			delete(attr, "department") // unverified claim
		}
		principal["attr"] = attr
	}
	if err := pdk.OutputJSON(req); err != nil {
		pdk.SetError(err)
		return 1
	}
	return 0
}

func main() {}
