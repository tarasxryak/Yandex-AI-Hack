package introspect

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"docs-parser/internal/schema"
)

const query = `
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      ...FullType
    }
    directives {
      name
      description
      locations
      args {
        ...InputValue
      }
    }
  }
}

fragment FullType on __Type {
  kind
  name
  description
  fields(includeDeprecated: true) {
    name
    description
    args {
      ...InputValue
    }
    type {
      ...TypeRef
    }
    isDeprecated
    deprecationReason
  }
  inputFields {
    ...InputValue
  }
  interfaces {
    ...TypeRef
  }
  enumValues(includeDeprecated: true) {
    name
    description
    isDeprecated
    deprecationReason
  }
  possibleTypes {
    ...TypeRef
  }
}

fragment InputValue on __InputValue {
  name
  description
  type {
    ...TypeRef
  }
  defaultValue
}

fragment TypeRef on __Type {
  kind
  name
  ofType {
    kind
    name
    ofType {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
      }
    }
  }
}
`

type Client struct {
	httpClient *http.Client
}

type Options struct {
	Token      string
	Headers    map[string]string
	IncludeRaw bool
}

type Result struct {
	Success       bool            `json:"success"`
	Status        string          `json:"status"`
	Message       string          `json:"message"`
	Hint          string          `json:"hint,omitempty"`
	HTTPStatus    int             `json:"http_status,omitempty"`
	Endpoint      string          `json:"endpoint,omitempty"`
	Schema        *schema.Compact `json:"schema,omitempty"`
	Introspection json.RawMessage `json:"introspection,omitempty"`
	Response      json.RawMessage `json:"response,omitempty"`
	ResponseText  string          `json:"response_text,omitempty"`
}

func New() *Client {
	return &Client{
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (c *Client) Fetch(ctx context.Context, endpoint string, opts Options) Result {
	if strings.TrimSpace(endpoint) == "" {
		return Result{
			Success: false,
			Status:  "invalid_request",
			Message: "endpoint is required",
		}
	}

	body, err := json.Marshal(map[string]string{
		"query":         query,
		"operationName": "IntrospectionQuery",
	})
	if err != nil {
		return requestFailed(endpoint, fmt.Errorf("encode introspection request: %w", err))
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return requestFailed(endpoint, fmt.Errorf("create introspection request: %w", err))
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", "docs-parser/0.1")
	if strings.TrimSpace(opts.Token) != "" {
		req.Header.Set("Authorization", "Bearer "+strings.TrimSpace(opts.Token))
	}
	for name, value := range opts.Headers {
		if strings.TrimSpace(name) == "" {
			continue
		}
		req.Header.Set(name, value)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return requestFailed(endpoint, fmt.Errorf("send introspection request: %w", err))
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return requestFailed(endpoint, fmt.Errorf("read introspection response: %w", err))
	}

	if resp.StatusCode == http.StatusUnauthorized || resp.StatusCode == http.StatusForbidden {
		result := Result{
			Success:    false,
			Status:     "auth_required",
			Message:    "GraphQL endpoint requires authorization for introspection",
			Hint:       `retry with token or header, for example -token "$TOKEN" or -header "Authorization: Bearer $TOKEN"`,
			HTTPStatus: resp.StatusCode,
			Endpoint:   endpoint,
		}
		attachResponse(&result, data)
		return result
	}

	if !json.Valid(data) {
		return Result{
			Success:      false,
			Status:       "invalid_response",
			Message:      "introspection response is not valid json",
			HTTPStatus:   resp.StatusCode,
			Endpoint:     endpoint,
			ResponseText: strings.TrimSpace(string(data)),
		}
	}

	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		result := Result{
			Success:    false,
			Status:     "http_error",
			Message:    "GraphQL endpoint returned non-success status",
			HTTPStatus: resp.StatusCode,
			Endpoint:   endpoint,
		}
		attachResponse(&result, data)
		return result
	}

	var envelope struct {
		Data struct {
			Schema json.RawMessage `json:"__schema"`
		} `json:"data"`
		Errors []struct {
			Message string `json:"message"`
		} `json:"errors"`
	}
	if err := json.Unmarshal(data, &envelope); err != nil {
		return requestFailed(endpoint, fmt.Errorf("decode introspection response: %w", err))
	}

	if len(envelope.Data.Schema) > 0 && string(envelope.Data.Schema) != "null" {
		compact, err := schema.FromIntrospection(data)
		if err != nil {
			return Result{
				Success:    false,
				Status:     "preprocess_failed",
				Message:    err.Error(),
				HTTPStatus: resp.StatusCode,
				Endpoint:   endpoint,
				Response:   cloneRawMessage(data),
			}
		}

		result := Result{
			Success:    true,
			Status:     "ok",
			Message:    "introspection fetched and preprocessed successfully",
			HTTPStatus: resp.StatusCode,
			Endpoint:   endpoint,
			Schema:     compact,
		}
		if opts.IncludeRaw {
			result.Introspection = cloneRawMessage(data)
		}

		return result
	}

	result := Result{
		Success:    false,
		Status:     classifyGraphQLError(envelope.Errors),
		Message:    "GraphQL endpoint did not return introspection schema",
		HTTPStatus: resp.StatusCode,
		Endpoint:   endpoint,
		Response:   cloneRawMessage(data),
	}
	if result.Status == "introspection_disabled" {
		result.Message = "GraphQL introspection is disabled by the server"
		result.Hint = "provide authorization if introspection is private, or import schema from SDL/docs instead"
	}

	return result
}

func (r Result) PrettyJSON() ([]byte, error) {
	data, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return nil, fmt.Errorf("encode introspection result: %w", err)
	}

	return append(data, '\n'), nil
}

func requestFailed(endpoint string, err error) Result {
	return Result{
		Success:  false,
		Status:   "request_failed",
		Message:  err.Error(),
		Endpoint: endpoint,
	}
}

func attachResponse(result *Result, data []byte) {
	if len(data) == 0 {
		return
	}
	if json.Valid(data) {
		result.Response = cloneRawMessage(data)
		return
	}
	result.ResponseText = strings.TrimSpace(string(data))
}

func cloneRawMessage(data []byte) json.RawMessage {
	cloned := make([]byte, len(data))
	copy(cloned, data)
	return cloned
}

func classifyGraphQLError(errors []struct {
	Message string `json:"message"`
}) string {
	for _, graphqlErr := range errors {
		message := strings.ToLower(graphqlErr.Message)
		if strings.Contains(message, "introspection") &&
			(strings.Contains(message, "disabled") ||
				strings.Contains(message, "not allowed") ||
				strings.Contains(message, "disallow") ||
				strings.Contains(message, "forbidden")) {
			return "introspection_disabled"
		}
		if strings.Contains(message, "__schema") || strings.Contains(message, "__type") {
			return "introspection_disabled"
		}
		if strings.Contains(message, "unauthorized") ||
			strings.Contains(message, "unauthenticated") ||
			strings.Contains(message, "authentication") ||
			strings.Contains(message, "token") {
			return "auth_required"
		}
	}

	return "graphql_error"
}
