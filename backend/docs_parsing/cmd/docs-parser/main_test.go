package main

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHeaderFlagsSet(t *testing.T) {
	headers := headerFlags{}
	if err := headers.Set("X-API-Key: secret"); err != nil {
		t.Fatalf("Set() error = %v", err)
	}
	if err := headers.Set(" Authorization : Bearer token "); err != nil {
		t.Fatalf("Set() error = %v", err)
	}

	if got := headers["X-API-Key"]; got != "secret" {
		t.Fatalf("X-API-Key = %q, want secret", got)
	}
	if got := headers["Authorization"]; got != "Bearer token" {
		t.Fatalf("Authorization = %q, want Bearer token", got)
	}
}

func TestHeaderFlagsRejectsInvalidFormat(t *testing.T) {
	headers := headerFlags{}
	if err := headers.Set("Authorization Bearer token"); err == nil {
		t.Fatal("Set() error is nil, want error")
	}
	if err := headers.Set(": value"); err == nil {
		t.Fatal("Set() error is nil, want error")
	}
}

func TestWriteJSONFormatsResponse(t *testing.T) {
	recorder := httptest.NewRecorder()
	writeJSON(recorder, http.StatusAccepted, map[string]any{
		"success": true,
		"nested":  map[string]string{"name": "Query"},
	})

	if recorder.Code != http.StatusAccepted {
		t.Fatalf("status = %d, want 202", recorder.Code)
	}
	if got := recorder.Header().Get("Content-Type"); got != "application/json" {
		t.Fatalf("Content-Type = %q, want application/json", got)
	}

	rawBody := recorder.Body.Bytes()
	var body map[string]any
	if err := json.NewDecoder(bytes.NewReader(rawBody)).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body["success"] != true {
		t.Fatalf("success = %#v, want true", body["success"])
	}
	if !bytes.Contains(rawBody, []byte("\n  ")) {
		t.Fatalf("response is not indented: %s", string(rawBody))
	}
}

func TestHealthzHandlerResponseShape(t *testing.T) {
	recorder := httptest.NewRecorder()
	writeJSON(recorder, http.StatusOK, map[string]string{"status": "ok"})

	if recorder.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", recorder.Code)
	}

	var body map[string]string
	if err := json.NewDecoder(recorder.Body).Decode(&body); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if body["status"] != "ok" {
		t.Fatalf("status body = %q, want ok", body["status"])
	}
}

func TestHeaderNames(t *testing.T) {
	names := headerNames(map[string]string{
		"Authorization": "Bearer token",
		"X-API-Key":     "secret",
	})

	if len(names) != 2 {
		t.Fatalf("len(headerNames) = %d, want 2", len(names))
	}
	seen := map[string]bool{}
	for _, name := range names {
		seen[name] = true
	}
	if !seen["Authorization"] || !seen["X-API-Key"] {
		t.Fatalf("headerNames = %#v", names)
	}
}
