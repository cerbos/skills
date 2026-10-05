// Route extension: answers whether a user may view a document, using the PDP.
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

// Document catalogue: owning department and tenant of each document.
var documents = map[string]map[string]string{
	"eng-acme":   {"department": "engineering", "tenant": "acme"},
	"sales-acme": {"department": "sales", "tenant": "acme"},
	"eng-globex": {"department": "engineering", "tenant": "globex"},
}

type values struct {
	Values []string `json:"values"`
}

type httpRequest struct {
	Headers     map[string]values `json:"headers"`
	QueryParams map[string]values `json:"queryParams"`
}

// HTTP responses: Body is []byte, so encoding/json base64-encodes it as Synapse expects.
type httpResponse struct {
	Status  int               `json:"status"`
	Headers map[string]values `json:"headers"`
	Body    []byte            `json:"body"`
}

func first(m map[string]values, key string) string {
	if v, ok := m[key]; ok && len(v.Values) > 0 {
		return v.Values[0]
	}
	return ""
}

func jsonResponse(status int, body string) httpResponse {
	return httpResponse{
		Status:  status,
		Headers: map[string]values{"content-type": {Values: []string{"application/json"}}},
		Body:    []byte(body),
	}
}

//go:wasmexport handleHTTPRoute
func handleHTTPRoute() int32 {
	var req httpRequest
	if err := pdk.InputJSON(&req); err != nil {
		pdk.SetError(err)
		return 1
	}

	documentID := first(req.QueryParams, "id")
	document, found := documents[documentID]
	if !found {
		return output(map[string]any{"httpResponse": jsonResponse(404, `{"error": "unknown document"}`)})
	}

	userID := first(req.Headers, "X-User-Id")
	attr := map[string]string{"tenant": first(req.Headers, "X-Tenant")}
	if department, known := departments[userID]; known {
		attr["department"] = department
	}

	return output(map[string]any{"cerbosMapping": map[string]any{
		"checkRequest": map[string]any{
			"principal": map[string]any{"id": userID, "roles": []string{"employee"}, "attr": attr},
			"resources": []any{map[string]any{
				"resource": map[string]any{"id": documentID, "kind": "document", "attr": document},
				"actions":  []string{"view"},
			}},
		},
		"allowResponse": jsonResponse(200, `{"allowed": true}`),
		"denyResponse":  jsonResponse(403, `{"allowed": false}`),
	}})
}

func output(v any) int32 {
	data, err := json.Marshal(v)
	if err != nil {
		pdk.SetError(err)
		return 1
	}
	pdk.Output(data)
	return 0
}

func main() {}
