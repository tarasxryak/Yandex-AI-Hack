package schema

import (
	"testing"
)

func TestFromIntrospectionBuildsCompactSchema(t *testing.T) {
	compact, err := FromIntrospection([]byte(testIntrospectionJSON()))
	if err != nil {
		t.Fatalf("FromIntrospection() error = %v", err)
	}

	if compact.QueryType != "Query" {
		t.Fatalf("QueryType = %q, want Query", compact.QueryType)
	}
	if len(compact.Queries) != 1 {
		t.Fatalf("len(Queries) = %d, want 1", len(compact.Queries))
	}
	query := compact.Queries[0]
	if query.Name != "user" || query.Type != "User" || query.NamedType != "User" {
		t.Fatalf("query = %#v", query)
	}
	if len(query.Args) != 1 || query.Args[0].Name != "id" || query.Args[0].Type != "ID!" || !query.Args[0].Required {
		t.Fatalf("query args = %#v", query.Args)
	}

	if len(compact.Types) != 1 || compact.Types[0].Name != "User" {
		t.Fatalf("Types = %#v", compact.Types)
	}
	if len(compact.Types[0].Fields) != 2 {
		t.Fatalf("User fields = %#v", compact.Types[0].Fields)
	}
	if compact.Types[0].Fields[1].Name != "orders" || compact.Types[0].Fields[1].Type != "[Order!]!" {
		t.Fatalf("orders field = %#v", compact.Types[0].Fields[1])
	}

	if len(compact.Enums) != 1 || compact.Enums[0].Name != "Role" {
		t.Fatalf("Enums = %#v", compact.Enums)
	}
	if len(compact.Inputs) != 1 || compact.Inputs[0].Name != "UserFilter" {
		t.Fatalf("Inputs = %#v", compact.Inputs)
	}
	if len(compact.Scalars) != 2 || compact.Scalars[0] != "ID" || compact.Scalars[1] != "String" {
		t.Fatalf("Scalars = %#v", compact.Scalars)
	}
}

func TestFromIntrospectionRejectsInvalidJSON(t *testing.T) {
	_, err := FromIntrospection([]byte(`not json`))
	if err == nil {
		t.Fatal("FromIntrospection() error is nil, want error")
	}
}

func testIntrospectionJSON() string {
	return `{
  "data": {
    "__schema": {
      "queryType": {"name": "Query"},
      "mutationType": {"name": "Mutation"},
      "subscriptionType": null,
      "types": [
        {
          "kind": "OBJECT",
          "name": "Query",
          "fields": [
            {
              "name": "user",
              "description": "Find user",
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
          "name": "Mutation",
          "fields": []
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
              "name": "orders",
              "type": {
                "kind": "NON_NULL",
                "ofType": {
                  "kind": "LIST",
                  "ofType": {
                    "kind": "NON_NULL",
                    "ofType": {"kind": "OBJECT", "name": "Order"}
                  }
                }
              }
            }
          ]
        },
        {
          "kind": "INPUT_OBJECT",
          "name": "UserFilter",
          "inputFields": [
            {
              "name": "search",
              "type": {"kind": "SCALAR", "name": "String"}
            }
          ]
        },
        {
          "kind": "ENUM",
          "name": "Role",
          "enumValues": [
            {"name": "ADMIN"},
            {"name": "USER"}
          ]
        },
        {"kind": "SCALAR", "name": "ID"},
        {"kind": "SCALAR", "name": "String"},
        {"kind": "OBJECT", "name": "__Type", "fields": []}
      ]
    }
  }
}`
}
