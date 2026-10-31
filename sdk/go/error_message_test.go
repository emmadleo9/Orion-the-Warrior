package openwa

import (
	"net/http"
	"testing"
)

// The message comes from any JSON object body that carries one, not only from a body that decodes
// as the whole Nest envelope, and an answer with no text names its status.
func TestAPIErrorMessageFromAnyBody(t *testing.T) {
	for _, tc := range []struct {
		name   string
		status int
		body   string
		header http.Header
		want   string
		kind   string
	}{
		{"envelope", 400, `{"statusCode":400,"message":"bad thing","error":"Bad Request"}`, nil, "bad thing", "Bad Request"},
		{"error is an object", 400, `{"statusCode":400,"message":"bad thing","error":{"x":1}}`, nil, "bad thing", ""},
		{"status code is a string", 400, `{"statusCode":"400","message":"bad thing","error":"Bad Request"}`, nil, "bad thing", "Bad Request"},
		{"no status code", 403, `{"message":"bad thing","error":"Forbidden"}`, nil, "bad thing", "Forbidden"},
		{"array with a non-string", 400, `{"statusCode":400,"message":["a",{"b":1}]}`, nil, "a", ""},
		{"array of strings", 400, `{"statusCode":400,"message":["a","b"],"error":"Bad Request"}`, nil, "a, b", "Bad Request"},
		{"empty body", 502, ``, nil, "Bad Gateway", ""},
		{"plain text", 502, `upstream down`, nil, "upstream down", ""},
		{"redirect", 301, ``, http.Header{"Location": {"https://example.com/x"}}, "Unexpected redirect (not followed; the API key is never re-sent to a redirect target)", ""},
	} {
		t.Run(tc.name, func(t *testing.T) {
			got := parseAPIError(tc.status, []byte(tc.body), "GET /x", tc.header)
			if got.Message != tc.want {
				t.Errorf("message = %q, want %q", got.Message, tc.want)
			}
			if got.Kind != tc.kind {
				t.Errorf("kind = %q, want %q", got.Kind, tc.kind)
			}
		})
	}
}
