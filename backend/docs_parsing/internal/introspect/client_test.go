package introspect

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestFetchPostsIntrospectionQueryToEndpoint(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("method = %s, want POST", r.Method)
		}
		if got := r.Header.Get("Content-Type"); got != "application/json" {
			t.Fatalf("Content-Type = %q, want application/json", got)
		}

		var body struct {
			Query         string `json:"query"`
			OperationName string `json:"operationName"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode request body: %v", err)
		}
		if body.OperationName != "IntrospectionQuery" {
			t.Fatalf("operationName = %q, want IntrospectionQuery", body.OperationName)
		}
		if !strings.Contains(body.Query, "__schema") {
			t.Fatalf("query does not contain __schema: %q", body.Query)
		}

		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(compactIntrospectionJSON()))
	}))
	defer server.Close()

	result := New().Fetch(context.Background(), server.URL, Options{})
	if !result.Success {
		t.Fatalf("Fetch().Success = false, result = %#v", result)
	}
	if result.Introspection != nil {
		t.Fatalf("Fetch().Introspection is set by default, want omitted")
	}
	if result.Schema == nil {
		t.Fatal("Fetch().Schema is nil, want compact schema")
	}
	if len(result.Schema.Queries) != 1 || result.Schema.Queries[0].Name != "user" {
		t.Fatalf("Fetch().Schema.Queries = %#v", result.Schema.Queries)
	}

	data, err := result.PrettyJSON()
	if err != nil {
		t.Fatalf("PrettyJSON() error = %v", err)
	}
	if got := string(data); !strings.Contains(got, `"success": true`) {
		t.Fatalf("PrettyJSON() = %s", got)
	}
	if got := string(data); !strings.Contains(got, `"schema": {`) || !strings.Contains(got, `"queries": [`) {
		t.Fatalf("PrettyJSON() missing compact schema: %s", got)
	}
}

func TestFetchSendsTokenAndHeaders(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer secret-token" {
			t.Fatalf("Authorization = %q, want Bearer secret-token", got)
		}
		if got := r.Header.Get("X-API-Key"); got != "secret-key" {
			t.Fatalf("X-API-Key = %q, want secret-key", got)
		}

		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(compactIntrospectionJSON()))
	}))
	defer server.Close()

	result := New().Fetch(context.Background(), server.URL, Options{
		Token: "secret-token",
		Headers: map[string]string{
			"X-API-Key": "secret-key",
		},
	})
	if !result.Success {
		t.Fatalf("Fetch().Success = false, result = %#v", result)
	}
}

func TestFetchIncludesRawIntrospectionWhenRequested(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(compactIntrospectionJSON()))
	}))
	defer server.Close()

	result := New().Fetch(context.Background(), server.URL, Options{IncludeRaw: true})
	if !result.Success {
		t.Fatalf("Fetch().Success = false, result = %#v", result)
	}
	if len(result.Introspection) == 0 {
		t.Fatal("Fetch().Introspection is empty, want raw response")
	}
	if result.Schema == nil {
		t.Fatal("Fetch().Schema is nil, want compact schema")
	}
}

func TestFetchClassifiesAuthRequired(t *testing.T) {
	tests := []struct {
		name       string
		statusCode int
		body       string
	}{
		{
			name:       "unauthorized",
			statusCode: http.StatusUnauthorized,
			body:       `{"errors":[{"message":"missing token"}]}`,
		},
		{
			name:       "forbidden",
			statusCode: http.StatusForbidden,
			body:       `{"errors":[{"message":"forbidden"}]}`,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(tt.statusCode)
				_, _ = w.Write([]byte(tt.body))
			}))
			defer server.Close()

			result := New().Fetch(context.Background(), server.URL, Options{})
			assertResult(t, result, false, "auth_required", tt.statusCode)
			if result.Hint == "" {
				t.Fatal("Fetch().Hint is empty, want retry hint")
			}
			if len(result.Response) == 0 {
				t.Fatal("Fetch().Response is empty, want upstream json")
			}
		})
	}
}

func TestFetchClassifiesGraphQLErrors(t *testing.T) {
	tests := []struct {
		name       string
		body       string
		wantStatus string
		wantHint   bool
	}{
		{
			name:       "introspection disabled",
			body:       `{"errors":[{"message":"GraphQL introspection is disabled"}]}`,
			wantStatus: "introspection_disabled",
			wantHint:   true,
		},
		{
			name:       "schema forbidden",
			body:       `{"errors":[{"message":"Cannot query field \"__schema\" on type \"Query\"."}]}`,
			wantStatus: "introspection_disabled",
			wantHint:   true,
		},
		{
			name:       "graphql auth message",
			body:       `{"errors":[{"message":"Authentication token is required"}]}`,
			wantStatus: "auth_required",
		},
		{
			name:       "generic graphql error",
			body:       `{"errors":[{"message":"Syntax Error: unexpected name"}]}`,
			wantStatus: "graphql_error",
		},
		{
			name:       "no schema no errors",
			body:       `{"data":{"viewer":{"id":"1"}}}`,
			wantStatus: "graphql_error",
		},
		{
			name:       "explicit null schema",
			body:       `{"data":{"__schema":null},"errors":[{"message":"Introspection is not allowed"}]}`,
			wantStatus: "introspection_disabled",
			wantHint:   true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Content-Type", "application/json")
				_, _ = w.Write([]byte(tt.body))
			}))
			defer server.Close()

			result := New().Fetch(context.Background(), server.URL, Options{})
			assertResult(t, result, false, tt.wantStatus, http.StatusOK)
			if tt.wantHint && result.Hint == "" {
				t.Fatal("Fetch().Hint is empty, want fallback hint")
			}
			if len(result.Response) == 0 {
				t.Fatal("Fetch().Response is empty, want upstream json")
			}
		})
	}
}

func TestFetchPrettyJSONForDisabledIntrospection(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"errors":[{"message":"GraphQL introspection is disabled"}]}`))
	}))
	defer server.Close()

	result := New().Fetch(context.Background(), server.URL, Options{})
	assertResult(t, result, false, "introspection_disabled", http.StatusOK)

	data, err := result.PrettyJSON()
	if err != nil {
		t.Fatalf("PrettyJSON() error = %v", err)
	}
	want := `{
  "success": false,
  "status": "introspection_disabled",
  "message": "GraphQL introspection is disabled by the server",
  "hint": "provide authorization if introspection is private, or import schema from SDL/docs instead",
  "http_status": 200,
  "endpoint": "` + server.URL + `",
  "response": {
    "errors": [
      {
        "message": "GraphQL introspection is disabled"
      }
    ]
  }
}
`
	if got := string(data); got != want {
		t.Fatalf("PrettyJSON() = %s", got)
	}
}

func TestFetchHandlesInvalidJSONResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`<html>not graphql</html>`))
	}))
	defer server.Close()

	result := New().Fetch(context.Background(), server.URL, Options{})
	assertResult(t, result, false, "invalid_response", http.StatusOK)
	if result.ResponseText != "<html>not graphql</html>" {
		t.Fatalf("Fetch().ResponseText = %q", result.ResponseText)
	}
}

func TestFetchHandlesHTTPErrorWithJSONBody(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"errors":[{"message":"upstream exploded"}]}`))
	}))
	defer server.Close()

	result := New().Fetch(context.Background(), server.URL, Options{})
	assertResult(t, result, false, "http_error", http.StatusInternalServerError)
	if len(result.Response) == 0 {
		t.Fatal("Fetch().Response is empty, want upstream json")
	}
}

func TestFetchHandlesHTTPErrorWithTextBody(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadGateway)
		_, _ = w.Write([]byte(`bad gateway`))
	}))
	defer server.Close()

	result := New().Fetch(context.Background(), server.URL, Options{})
	assertResult(t, result, false, "invalid_response", http.StatusBadGateway)
	if result.ResponseText != "bad gateway" {
		t.Fatalf("Fetch().ResponseText = %q", result.ResponseText)
	}
}

func TestFetchHandlesRequestCreationError(t *testing.T) {
	result := New().Fetch(context.Background(), "://bad-url", Options{})
	if result.Success {
		t.Fatal("Fetch().Success = true, want false")
	}
	if result.Status != "request_failed" {
		t.Fatalf("Fetch().Status = %q, want request_failed", result.Status)
	}
	if !strings.Contains(result.Message, "create introspection request") {
		t.Fatalf("Fetch().Message = %q", result.Message)
	}
}

func TestResultPrettyJSONFormatsNestedRawMessages(t *testing.T) {
	result := Result{
		Success:       true,
		Status:        "ok",
		Message:       "introspection fetched successfully",
		Introspection: json.RawMessage(`{"data":{"__schema":{"queryType":{"name":"Query"}}}}`),
	}

	data, err := result.PrettyJSON()
	if err != nil {
		t.Fatalf("PrettyJSON() error = %v", err)
	}
	got := string(data)
	if !strings.Contains(got, `"introspection": {`) || !strings.Contains(got, `"name": "Query"`) {
		t.Fatalf("PrettyJSON() = %s", got)
	}
}

func compactIntrospectionJSON() string {
	return `{
  "data": {
    "__schema": {
      "queryType": {"name": "Query"},
      "mutationType": null,
      "subscriptionType": null,
      "types": [
        {
          "kind": "OBJECT",
          "name": "Query",
          "fields": [
            {
              "name": "user",
              "args": [
                {
                  "name": "id",
                  "type": {"kind": "NON_NULL", "ofType": {"kind": "SCALAR", "name": "ID"}}
                }
              ],
              "type": {"kind": "OBJECT", "name": "User"}
            }
          ]
        },
        {
          "kind": "OBJECT",
          "name": "User",
          "fields": [
            {
              "name": "id",
              "type": {"kind": "NON_NULL", "ofType": {"kind": "SCALAR", "name": "ID"}}
            },
            {
              "name": "name",
              "type": {"kind": "SCALAR", "name": "String"}
            }
          ]
        },
        {"kind": "SCALAR", "name": "ID"},
        {"kind": "SCALAR", "name": "String"},
        {"kind": "OBJECT", "name": "__Schema", "fields": []}
      ]
    }
  }
}`
}

func TestFetchRejectsEmptyEndpoint(t *testing.T) {
	result := New().Fetch(context.Background(), " ", Options{})
	if result.Success {
		t.Fatal("Fetch().Success = true, want false")
	}
	if result.Status != "invalid_request" {
		t.Fatalf("Fetch().Status = %q, want invalid_request", result.Status)
	}
}

func assertResult(t *testing.T, result Result, wantSuccess bool, wantStatus string, wantHTTPStatus int) {
	t.Helper()

	if result.Success != wantSuccess {
		t.Fatalf("Fetch().Success = %t, want %t; result = %#v", result.Success, wantSuccess, result)
	}
	if result.Status != wantStatus {
		t.Fatalf("Fetch().Status = %q, want %q; result = %#v", result.Status, wantStatus, result)
	}
	if result.HTTPStatus != wantHTTPStatus {
		t.Fatalf("Fetch().HTTPStatus = %d, want %d; result = %#v", result.HTTPStatus, wantHTTPStatus, result)
	}
}
