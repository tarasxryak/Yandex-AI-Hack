package parser

import (
	"strings"
	"testing"
)

func TestParse(t *testing.T) {
	html := `
		<html>
			<head>
				<title> Test docs </title>
				<meta name="description" content=" Docs page ">
			</head>
			<body>
				<nav><a href="/nav">Navigation</a></nav>
				<main>
					<h1 id="intro"> Intro </h1>
					<p> First paragraph. </p>
					<pre><code>go test ./...</code></pre>
					<a href="/docs/next">Next page</a>
				</main>
			</body>
		</html>
	`

	page, err := Parse(strings.NewReader(html), "https://example.com/docs/start")
	if err != nil {
		t.Fatalf("Parse() error = %v", err)
	}

	if page.Title != "Test docs" {
		t.Fatalf("Title = %q, want %q", page.Title, "Test docs")
	}
	if page.Description != "Docs page" {
		t.Fatalf("Description = %q, want %q", page.Description, "Docs page")
	}
	if len(page.Headings) != 1 {
		t.Fatalf("len(Headings) = %d, want 1", len(page.Headings))
	}
	if page.Headings[0].Level != 1 || page.Headings[0].ID != "intro" || page.Headings[0].Text != "Intro" {
		t.Fatalf("Headings[0] = %#v", page.Headings[0])
	}
	if len(page.Blocks) != 2 {
		t.Fatalf("len(Blocks) = %d, want 2", len(page.Blocks))
	}
	if page.Blocks[1].Type != "code" || page.Blocks[1].Text != "go test ./..." {
		t.Fatalf("Blocks[1] = %#v", page.Blocks[1])
	}
	if len(page.Links) != 1 {
		t.Fatalf("len(Links) = %d, want 1", len(page.Links))
	}
	if page.Links[0].Href != "https://example.com/docs/next" {
		t.Fatalf("Links[0].Href = %q, want %q", page.Links[0].Href, "https://example.com/docs/next")
	}
}
