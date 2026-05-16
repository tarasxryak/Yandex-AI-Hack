package schema

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"
)

type Compact struct {
	QueryType        string      `json:"query_type,omitempty"`
	MutationType     string      `json:"mutation_type,omitempty"`
	SubscriptionType string      `json:"subscription_type,omitempty"`
	Queries          []Field     `json:"queries,omitempty"`
	Mutations        []Field     `json:"mutations,omitempty"`
	Subscriptions    []Field     `json:"subscriptions,omitempty"`
	Types            []Type      `json:"types,omitempty"`
	Inputs           []InputType `json:"inputs,omitempty"`
	Enums            []EnumType  `json:"enums,omitempty"`
	Scalars          []string    `json:"scalars,omitempty"`
}

type Field struct {
	Name              string       `json:"name"`
	Description       string       `json:"description,omitempty"`
	Type              string       `json:"type"`
	NamedType         string       `json:"named_type,omitempty"`
	Args              []InputValue `json:"args,omitempty"`
	Deprecated        bool         `json:"deprecated,omitempty"`
	DeprecationReason string       `json:"deprecation_reason,omitempty"`
}

type InputValue struct {
	Name         string `json:"name"`
	Description  string `json:"description,omitempty"`
	Type         string `json:"type"`
	NamedType    string `json:"named_type,omitempty"`
	DefaultValue string `json:"default_value,omitempty"`
	Required     bool   `json:"required,omitempty"`
}

type Type struct {
	Name        string   `json:"name"`
	Description string   `json:"description,omitempty"`
	Fields      []Field  `json:"fields,omitempty"`
	Interfaces  []string `json:"interfaces,omitempty"`
}

type InputType struct {
	Name        string       `json:"name"`
	Description string       `json:"description,omitempty"`
	Fields      []InputValue `json:"fields,omitempty"`
}

type EnumType struct {
	Name        string      `json:"name"`
	Description string      `json:"description,omitempty"`
	Values      []EnumValue `json:"values,omitempty"`
}

type EnumValue struct {
	Name              string `json:"name"`
	Description       string `json:"description,omitempty"`
	Deprecated        bool   `json:"deprecated,omitempty"`
	DeprecationReason string `json:"deprecation_reason,omitempty"`
}

type envelope struct {
	Data struct {
		Schema introspectionSchema `json:"__schema"`
	} `json:"data"`
}

type introspectionSchema struct {
	QueryType        typeName            `json:"queryType"`
	MutationType     typeName            `json:"mutationType"`
	SubscriptionType typeName            `json:"subscriptionType"`
	Types            []introspectionType `json:"types"`
}

type typeName struct {
	Name string `json:"name"`
}

type introspectionType struct {
	Kind        string               `json:"kind"`
	Name        string               `json:"name"`
	Description string               `json:"description"`
	Fields      []introspectionField `json:"fields"`
	InputFields []introspectionInput `json:"inputFields"`
	Interfaces  []typeRef            `json:"interfaces"`
	EnumValues  []introspectionEnum  `json:"enumValues"`
}

type introspectionField struct {
	Name              string               `json:"name"`
	Description       string               `json:"description"`
	Args              []introspectionInput `json:"args"`
	Type              typeRef              `json:"type"`
	IsDeprecated      bool                 `json:"isDeprecated"`
	DeprecationReason string               `json:"deprecationReason"`
}

type introspectionInput struct {
	Name         string  `json:"name"`
	Description  string  `json:"description"`
	Type         typeRef `json:"type"`
	DefaultValue string  `json:"defaultValue"`
}

type introspectionEnum struct {
	Name              string `json:"name"`
	Description       string `json:"description"`
	IsDeprecated      bool   `json:"isDeprecated"`
	DeprecationReason string `json:"deprecationReason"`
}

type typeRef struct {
	Kind   string   `json:"kind"`
	Name   string   `json:"name"`
	OfType *typeRef `json:"ofType"`
}

func FromIntrospection(raw []byte) (*Compact, error) {
	var env envelope
	if err := json.Unmarshal(raw, &env); err != nil {
		return nil, fmt.Errorf("decode introspection schema: %w", err)
	}

	byName := make(map[string]introspectionType, len(env.Data.Schema.Types))
	for _, typ := range env.Data.Schema.Types {
		if typ.Name == "" || strings.HasPrefix(typ.Name, "__") {
			continue
		}
		byName[typ.Name] = typ
	}

	compact := &Compact{
		QueryType:        env.Data.Schema.QueryType.Name,
		MutationType:     env.Data.Schema.MutationType.Name,
		SubscriptionType: env.Data.Schema.SubscriptionType.Name,
	}

	if queryType, ok := byName[compact.QueryType]; ok {
		compact.Queries = convertFields(queryType.Fields)
	}
	if mutationType, ok := byName[compact.MutationType]; ok {
		compact.Mutations = convertFields(mutationType.Fields)
	}
	if subscriptionType, ok := byName[compact.SubscriptionType]; ok {
		compact.Subscriptions = convertFields(subscriptionType.Fields)
	}

	for _, typ := range env.Data.Schema.Types {
		if typ.Name == "" || strings.HasPrefix(typ.Name, "__") || isRootOperationType(typ.Name, compact) {
			continue
		}

		switch typ.Kind {
		case "OBJECT", "INTERFACE":
			compact.Types = append(compact.Types, Type{
				Name:        typ.Name,
				Description: strings.TrimSpace(typ.Description),
				Fields:      convertFields(typ.Fields),
				Interfaces:  convertTypeNames(typ.Interfaces),
			})
		case "INPUT_OBJECT":
			compact.Inputs = append(compact.Inputs, InputType{
				Name:        typ.Name,
				Description: strings.TrimSpace(typ.Description),
				Fields:      convertInputs(typ.InputFields),
			})
		case "ENUM":
			compact.Enums = append(compact.Enums, EnumType{
				Name:        typ.Name,
				Description: strings.TrimSpace(typ.Description),
				Values:      convertEnums(typ.EnumValues),
			})
		case "SCALAR":
			compact.Scalars = append(compact.Scalars, typ.Name)
		}
	}

	sort.Slice(compact.Types, func(i, j int) bool { return compact.Types[i].Name < compact.Types[j].Name })
	sort.Slice(compact.Inputs, func(i, j int) bool { return compact.Inputs[i].Name < compact.Inputs[j].Name })
	sort.Slice(compact.Enums, func(i, j int) bool { return compact.Enums[i].Name < compact.Enums[j].Name })
	sort.Strings(compact.Scalars)

	return compact, nil
}

func convertFields(fields []introspectionField) []Field {
	result := make([]Field, 0, len(fields))
	for _, field := range fields {
		result = append(result, Field{
			Name:              field.Name,
			Description:       strings.TrimSpace(field.Description),
			Type:              field.Type.String(),
			NamedType:         field.Type.NamedType(),
			Args:              convertInputs(field.Args),
			Deprecated:        field.IsDeprecated,
			DeprecationReason: strings.TrimSpace(field.DeprecationReason),
		})
	}

	return result
}

func convertInputs(inputs []introspectionInput) []InputValue {
	result := make([]InputValue, 0, len(inputs))
	for _, input := range inputs {
		result = append(result, InputValue{
			Name:         input.Name,
			Description:  strings.TrimSpace(input.Description),
			Type:         input.Type.String(),
			NamedType:    input.Type.NamedType(),
			DefaultValue: input.DefaultValue,
			Required:     input.Type.Kind == "NON_NULL",
		})
	}

	return result
}

func convertEnums(values []introspectionEnum) []EnumValue {
	result := make([]EnumValue, 0, len(values))
	for _, value := range values {
		result = append(result, EnumValue{
			Name:              value.Name,
			Description:       strings.TrimSpace(value.Description),
			Deprecated:        value.IsDeprecated,
			DeprecationReason: strings.TrimSpace(value.DeprecationReason),
		})
	}

	return result
}

func convertTypeNames(types []typeRef) []string {
	result := make([]string, 0, len(types))
	for _, typ := range types {
		if name := typ.NamedType(); name != "" {
			result = append(result, name)
		}
	}

	return result
}

func isRootOperationType(name string, compact *Compact) bool {
	return name == compact.QueryType || name == compact.MutationType || name == compact.SubscriptionType
}

func (t typeRef) String() string {
	switch t.Kind {
	case "NON_NULL":
		if t.OfType == nil {
			return "!"
		}
		return t.OfType.String() + "!"
	case "LIST":
		if t.OfType == nil {
			return "[]"
		}
		return "[" + t.OfType.String() + "]"
	default:
		return t.Name
	}
}

func (t typeRef) NamedType() string {
	if t.Name != "" {
		return t.Name
	}
	if t.OfType == nil {
		return ""
	}

	return t.OfType.NamedType()
}
