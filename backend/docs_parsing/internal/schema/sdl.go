package schema

import (
	"strings"
)

func ToSDL(compact *Compact) string {
	if compact == nil {
		return ""
	}

	var b strings.Builder
	writeRootObject(&b, "type", compact.QueryType, compact.Queries)
	writeRootObject(&b, "type", compact.MutationType, compact.Mutations)
	writeRootObject(&b, "type", compact.SubscriptionType, compact.Subscriptions)

	for _, typ := range compact.Types {
		writeObject(&b, "type", typ.Name, typ.Description, typ.Fields)
	}
	for _, input := range compact.Inputs {
		writeInput(&b, input)
	}
	for _, enum := range compact.Enums {
		writeEnum(&b, enum)
	}
	for _, scalar := range compact.Scalars {
		if isBuiltInScalar(scalar) {
			continue
		}
		writeLine(&b, "scalar "+scalar)
	}

	return strings.TrimSpace(b.String()) + "\n"
}

func writeRootObject(b *strings.Builder, keyword string, name string, fields []Field) {
	if name == "" || len(fields) == 0 {
		return
	}
	writeObject(b, keyword, name, "", fields)
}

func writeObject(b *strings.Builder, keyword string, name string, description string, fields []Field) {
	if name == "" {
		return
	}
	writeDescription(b, description, "")
	writeLine(b, keyword+" "+name+" {")
	for _, field := range fields {
		writeDescription(b, field.Description, "  ")
		line := "  " + field.Name
		if len(field.Args) > 0 {
			line += "(" + formatArgs(field.Args) + ")"
		}
		line += ": " + field.Type
		if field.Deprecated {
			line += formatDeprecated(field.DeprecationReason)
		}
		writeLine(b, line)
	}
	writeLine(b, "}")
	writeLine(b, "")
}

func writeInput(b *strings.Builder, input InputType) {
	if input.Name == "" {
		return
	}
	writeDescription(b, input.Description, "")
	writeLine(b, "input "+input.Name+" {")
	for _, field := range input.Fields {
		writeDescription(b, field.Description, "  ")
		line := "  " + field.Name + ": " + field.Type
		if field.DefaultValue != "" {
			line += " = " + field.DefaultValue
		}
		writeLine(b, line)
	}
	writeLine(b, "}")
	writeLine(b, "")
}

func writeEnum(b *strings.Builder, enum EnumType) {
	if enum.Name == "" {
		return
	}
	writeDescription(b, enum.Description, "")
	writeLine(b, "enum "+enum.Name+" {")
	for _, value := range enum.Values {
		writeDescription(b, value.Description, "  ")
		line := "  " + value.Name
		if value.Deprecated {
			line += formatDeprecated(value.DeprecationReason)
		}
		writeLine(b, line)
	}
	writeLine(b, "}")
	writeLine(b, "")
}

func formatArgs(args []InputValue) string {
	parts := make([]string, 0, len(args))
	for _, arg := range args {
		part := arg.Name + ": " + arg.Type
		if arg.DefaultValue != "" {
			part += " = " + arg.DefaultValue
		}
		parts = append(parts, part)
	}

	return strings.Join(parts, ", ")
}

func formatDeprecated(reason string) string {
	if strings.TrimSpace(reason) == "" {
		return " @deprecated"
	}

	return ` @deprecated(reason: "` + escapeSDLString(reason) + `")`
}

func writeDescription(b *strings.Builder, description string, indent string) {
	description = strings.TrimSpace(description)
	if description == "" {
		return
	}
	writeLine(b, indent+`"""`)
	for _, line := range strings.Split(description, "\n") {
		writeLine(b, indent+escapeBlockStringLine(line))
	}
	writeLine(b, indent+`"""`)
}

func writeLine(b *strings.Builder, line string) {
	b.WriteString(line)
	b.WriteByte('\n')
}

func escapeSDLString(value string) string {
	value = strings.ReplaceAll(value, `\`, `\\`)
	return strings.ReplaceAll(value, `"`, `\"`)
}

func escapeBlockStringLine(value string) string {
	return strings.ReplaceAll(value, `"""`, `\"""`)
}

func isBuiltInScalar(name string) bool {
	switch name {
	case "ID", "String", "Int", "Float", "Boolean":
		return true
	default:
		return false
	}
}
