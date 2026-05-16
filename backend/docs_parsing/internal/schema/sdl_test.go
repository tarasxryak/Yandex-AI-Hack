package schema

import (
	"strings"
	"testing"
)

func TestToSDL(t *testing.T) {
	compact := &Compact{
		QueryType: "Query",
		Queries: []Field{
			{
				Name:        "user",
				Description: "Find user",
				Type:        "User",
				Args: []InputValue{
					{Name: "id", Type: "ID!"},
					{Name: "filter", Type: "UserFilter"},
				},
			},
		},
		Types: []Type{
			{
				Name:        "User",
				Description: "Application user",
				Fields: []Field{
					{Name: "id", Type: "ID!"},
					{Name: "name", Type: "String"},
					{Name: "oldName", Type: "String", Deprecated: true, DeprecationReason: "Use name"},
				},
			},
		},
		Inputs: []InputType{
			{
				Name: "UserFilter",
				Fields: []InputValue{
					{Name: "search", Type: "String", DefaultValue: `"rick"`},
				},
			},
		},
		Enums: []EnumType{
			{
				Name: "Role",
				Values: []EnumValue{
					{Name: "ADMIN"},
					{Name: "USER"},
				},
			},
		},
		Scalars: []string{"ID", "String", "DateTime"},
	}

	sdl := ToSDL(compact)
	wantParts := []string{
		"type Query {",
		`  user(id: ID!, filter: UserFilter): User`,
		"type User {",
		`  oldName: String @deprecated(reason: "Use name")`,
		"input UserFilter {",
		`  search: String = "rick"`,
		"enum Role {",
		"scalar DateTime",
	}
	for _, want := range wantParts {
		if !strings.Contains(sdl, want) {
			t.Fatalf("SDL missing %q:\n%s", want, sdl)
		}
	}
	if strings.Contains(sdl, "scalar ID") || strings.Contains(sdl, "scalar String") {
		t.Fatalf("SDL includes built-in scalar:\n%s", sdl)
	}
}

func TestToSDLNil(t *testing.T) {
	if got := ToSDL(nil); got != "" {
		t.Fatalf("ToSDL(nil) = %q, want empty", got)
	}
}
