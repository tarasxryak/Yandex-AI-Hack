package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"docs-parser/internal/introspect"
)

type headerFlags map[string]string

func (h headerFlags) String() string {
	return fmt.Sprint(map[string]string(h))
}

func (h headerFlags) Set(value string) error {
	name, headerValue, ok := strings.Cut(value, ":")
	if !ok || strings.TrimSpace(name) == "" {
		return fmt.Errorf(`header must use "Name: value" format`)
	}

	h[strings.TrimSpace(name)] = strings.TrimSpace(headerValue)
	return nil
}

func main() {
	endpoint := flag.String("endpoint", "", "GraphQL endpoint URL to introspect")
	token := flag.String("token", "", "Bearer token for GraphQL introspection")
	includeRaw := flag.Bool("include-raw", false, "include raw GraphQL introspection response")
	serve := flag.String("serve", "", "HTTP address to serve parser API, for example :8080")
	out := flag.String("out", "", "output JSON file path, stdout when empty")
	headers := headerFlags{}
	flag.Var(headers, "header", `extra GraphQL request header, for example -header "X-API-Key: secret"`)
	flag.Parse()

	if *serve != "" {
		if err := serveAPI(*serve); err != nil {
			fmt.Fprintf(os.Stderr, "serve api: %v\n", err)
			os.Exit(1)
		}
		return
	}

	if *endpoint == "" {
		fmt.Fprintln(os.Stderr, `usage: docs-parser (-endpoint https://example.com/graphql [-token token] [-header "Name: value"] | -serve :8080) [-out result.json]`)
		os.Exit(2)
	}

	data := fetchData(context.Background(), *endpoint, introspect.Options{
		Token:      *token,
		Headers:    headers,
		IncludeRaw: *includeRaw,
	})

	if *out == "" {
		_, _ = os.Stdout.Write(data)
		return
	}

	if err := os.WriteFile(*out, data, 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write output: %v\n", err)
		os.Exit(1)
	}
}

func fetchData(ctx context.Context, endpoint string, opts introspect.Options) []byte {
	result := introspect.New().Fetch(ctx, endpoint, opts)
	data, err := result.PrettyJSON()
	if err != nil {
		fmt.Fprintf(os.Stderr, "encode introspection result: %v\n", err)
		os.Exit(1)
	}

	return data
}

type introspectRequest struct {
	Endpoint   string            `json:"endpoint"`
	Token      string            `json:"token,omitempty"`
	Headers    map[string]string `json:"headers,omitempty"`
	IncludeRaw bool              `json:"include_raw,omitempty"`
}

func serveAPI(addr string) error {
	client := introspect.New()
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
			return
		}

		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("/introspect", func(w http.ResponseWriter, r *http.Request) {
		startedAt := time.Now()
		setCORSHeaders(w)
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			log.Printf("request method=%s path=%s status=204 duration=%s", r.Method, r.URL.Path, time.Since(startedAt))
			return
		}
		if r.Method != http.MethodPost {
			writeJSON(w, http.StatusMethodNotAllowed, map[string]string{"error": "method not allowed"})
			log.Printf("request method=%s path=%s status=405 duration=%s", r.Method, r.URL.Path, time.Since(startedAt))
			return
		}

		var req introspectRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json request"})
			log.Printf("introspect invalid_json remote=%s duration=%s", r.RemoteAddr, time.Since(startedAt))
			return
		}

		log.Printf(
			"introspect started endpoint=%q remote=%s token=%t headers=%v",
			req.Endpoint,
			r.RemoteAddr,
			strings.TrimSpace(req.Token) != "",
			headerNames(req.Headers),
		)

		result := client.Fetch(r.Context(), req.Endpoint, introspect.Options{
			Token:      req.Token,
			Headers:    req.Headers,
			IncludeRaw: req.IncludeRaw,
		})
		writeJSON(w, http.StatusOK, result)
		log.Printf(
			"introspect finished endpoint=%q success=%t status=%s upstream_status=%d duration=%s",
			req.Endpoint,
			result.Success,
			result.Status,
			result.HTTPStatus,
			time.Since(startedAt),
		)
	})

	log.Printf("docs-parser api listening addr=%s", addr)
	return http.ListenAndServe(addr, mux)
}

func setCORSHeaders(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	encoder := json.NewEncoder(w)
	encoder.SetIndent("", "  ")
	_ = encoder.Encode(value)
}

func headerNames(headers map[string]string) []string {
	names := make([]string, 0, len(headers))
	for name := range headers {
		names = append(names, name)
	}

	return names
}
