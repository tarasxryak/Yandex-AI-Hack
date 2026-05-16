package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"docs-parser/internal/parser"
)

func main() {
	pageURL := flag.String("url", "", "HTML page URL to parse")
	out := flag.String("out", "", "output JSON file path, stdout when empty")
	flag.Parse()

	if *pageURL == "" {
		fmt.Fprintln(os.Stderr, "usage: docs-parser -url https://example.com/docs/page [-out page.json]")
		os.Exit(2)
	}

	p := parser.New()
	page, err := p.ParseURL(context.Background(), *pageURL)
	if err != nil {
		fmt.Fprintf(os.Stderr, "parse page: %v\n", err)
		os.Exit(1)
	}

	data, err := json.MarshalIndent(page, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "encode json: %v\n", err)
		os.Exit(1)
	}
	data = append(data, '\n')

	if *out == "" {
		_, _ = os.Stdout.Write(data)
		return
	}

	if err := os.WriteFile(*out, data, 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write output: %v\n", err)
		os.Exit(1)
	}
}
