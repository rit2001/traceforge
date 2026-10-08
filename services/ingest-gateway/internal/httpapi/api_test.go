package httpapi

import (
	"bytes"
	"context"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/prometheus/client_golang/prometheus"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	"go.opentelemetry.io/otel/sdk/trace/tracetest"
	"traceforge/ingest-gateway/internal/events"
	"traceforge/ingest-gateway/internal/publisher"
)

type fakePublisher struct {
	err      error
	ready    bool
	key      string
	value    []byte
	failures uint64
	closed   bool
}

func (f *fakePublisher) Enqueue(_ context.Context, key string, value []byte) error {
	f.key = key
	f.value = append([]byte(nil), value...)
	return f.err
}
func (f *fakePublisher) Ready(context.Context) bool  { return f.ready }
func (f *fakePublisher) Close(context.Context) error { f.closed = true; return nil }
func (f *fakePublisher) DeliveryFailures() uint64    { return f.failures }
func fixture(t *testing.T, name string) []byte {
	t.Helper()
	p := filepath.Join("..", "..", "..", "..", "schemas", "fixtures", "capture-events", name)
	b, e := os.ReadFile(p)
	if e != nil {
		t.Fatal(e)
	}
	return b
}
func api(t *testing.T, p *fakePublisher, max int64) (http.Handler, *prometheus.Registry) {
	t.Helper()
	v, e := events.LoadAll(map[string]string{
		"0.2.0": filepath.Join("..", "..", "..", "..", "schemas", "capture-event-v0.schema.json"),
		"0.3.0": filepath.Join("..", "..", "..", "..", "schemas", "capture-event-v0.3.schema.json"),
	})
	if e != nil {
		t.Fatal(e)
	}
	r := prometheus.NewRegistry()
	return New(v, p, max, r).Handler(r), r
}
func request(t *testing.T, h http.Handler, body []byte, content string) *httptest.ResponseRecorder {
	t.Helper()
	r := httptest.NewRequest(http.MethodPost, "/v1/capture-events", bytes.NewReader(body))
	if content != "" {
		r.Header.Set("Content-Type", content)
	}
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	return w
}
func TestValidAcceptedAndCaptureIDKey(t *testing.T) {
	p := &fakePublisher{ready: true}
	h, _ := api(t, p, 4096)
	w := request(t, h, fixture(t, "valid.json"), "application/json")
	if w.Code != 202 || p.key != "capture-1" {
		t.Fatalf("code=%d key=%q", w.Code, p.key)
	}
}

func TestPortableExecutionSpanEventAccepted(t *testing.T) {
	p := &fakePublisher{ready: true}
	h, _ := api(t, p, 4096)
	w := request(t, h, fixture(t, "valid-v0.3-execution-span.json"), "application/json")
	if w.Code != 202 || p.key != "capture-span-1" {
		t.Fatalf("code=%d key=%q", w.Code, p.key)
	}
}
func TestMalformedJSON(t *testing.T) {
	h, _ := api(t, &fakePublisher{ready: true}, 4096)
	if w := request(t, h, []byte("{"), "application/json"); w.Code != 400 {
		t.Fatal(w.Code)
	}
}
func TestUnknownAndSchemaFailure(t *testing.T) {
	h, _ := api(t, &fakePublisher{ready: true}, 4096)
	for _, n := range []string{"invalid-unknown-field.json", "invalid-sequence.json"} {
		if w := request(t, h, fixture(t, n), "application/json"); w.Code != 400 {
			t.Fatal(n, w.Code)
		}
	}
}
func TestContentTypeAndBodyLimit(t *testing.T) {
	h, _ := api(t, &fakePublisher{ready: true}, 8)
	if w := request(t, h, fixture(t, "valid.json"), "text/plain"); w.Code != 415 {
		t.Fatal(w.Code)
	}
	if w := request(t, h, fixture(t, "valid.json"), "application/json"); w.Code != 413 {
		t.Fatal(w.Code)
	}
}
func TestSecretPayloadRejectedAndNotLogged(t *testing.T) {
	var logs bytes.Buffer
	old := slog.Default()
	slog.SetDefault(slog.New(slog.NewJSONHandler(&logs, nil)))
	defer slog.SetDefault(old)
	h, _ := api(t, &fakePublisher{ready: true}, 4096)
	body := bytes.Replace(fixture(t, "valid.json"), []byte(`"safe":true`), []byte(`"api_key":"synthetic-secret"`), 1)
	if w := request(t, h, body, "application/json"); w.Code != 400 {
		t.Fatal(w.Code)
	}
	if strings.Contains(logs.String(), "synthetic-secret") {
		t.Fatal("secret logged")
	}
}
func TestSecretHeaderAndQueryRejected(t *testing.T) {
	h, _ := api(t, &fakePublisher{ready: true}, 4096)
	for _, target := range []string{
		"/v1/capture-events?api_key=synthetic",
		"/v1/capture-events",
	} {
		r := httptest.NewRequest(http.MethodPost, target, bytes.NewReader(fixture(t, "valid.json")))
		r.Header.Set("Content-Type", "application/json")
		if target == "/v1/capture-events" {
			r.Header.Set("Authorization", "Bearer synthetic")
		}
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != 400 {
			t.Fatal(target, w.Code)
		}
	}
}
func TestQueueFullAndUnavailable(t *testing.T) {
	for _, tc := range []struct {
		err  error
		code int
	}{{publisher.ErrFull, 429}, {publisher.ErrUnavailable, 503}} {
		h, _ := api(t, &fakePublisher{ready: true, err: tc.err}, 4096)
		if w := request(t, h, fixture(t, "valid.json"), "application/json"); w.Code != tc.code {
			t.Fatal(w.Code)
		}
	}
}
func TestHealthReadinessMetricsAndShutdown(t *testing.T) {
	p := &fakePublisher{ready: false}
	h, _ := api(t, p, 4096)
	for _, tc := range []struct {
		path string
		code int
	}{{"/healthz", 200}, {"/readyz", 503}, {"/metrics", 200}} {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, httptest.NewRequest("GET", tc.path, nil))
		if w.Code != tc.code {
			t.Fatal(tc.path, w.Code)
		}
	}
	p.ready = true
	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest("GET", "/readyz", nil))
	if w.Code != 200 {
		t.Fatal(w.Code)
	}
	if err := Shutdown(context.Background(), p); err != nil || !p.closed {
		t.Fatal(err)
	}
}
func TestAsyncDeliveryFailureMetricBoundary(t *testing.T) {
	p := &fakePublisher{ready: true, failures: 1}
	h, _ := api(t, p, 4096)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, httptest.NewRequest("GET", "/metrics", nil))
	if !strings.Contains(w.Body.String(), "traceforge_gateway_delivery_failures_total 1") {
		t.Fatal("delivery failure metric missing")
	}
}

func TestExpectedSpansAndNoPayloadAttributes(t *testing.T) {
	recorder := tracetest.NewSpanRecorder()
	provider := sdktrace.NewTracerProvider(sdktrace.WithSpanProcessor(recorder))
	previous := otel.GetTracerProvider()
	otel.SetTracerProvider(provider)
	otel.SetTextMapPropagator(propagation.TraceContext{})
	defer otel.SetTracerProvider(previous)
	p := &fakePublisher{ready: true}
	h, _ := api(t, p, 4096)
	r := httptest.NewRequest(
		http.MethodPost,
		"/v1/capture-events",
		bytes.NewReader(fixture(t, "valid.json")),
	)
	r.Header.Set("Content-Type", "application/json")
	r.Header.Set(
		"traceparent",
		"00-00112233445566778899aabbccddeeff-0011223344556677-01",
	)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 202 {
		t.Fatal(w.Code)
	}
	names := map[string]bool{}
	for _, span := range recorder.Ended() {
		names[span.Name()] = true
		if span.Name() == "capture.receive" && span.SpanContext().TraceID().String() != "00112233445566778899aabbccddeeff" {
			t.Fatal("HTTP trace context was not extracted")
		}
		for _, attribute := range span.Attributes() {
			if strings.Contains(attribute.Value.AsString(), "safe") {
				t.Fatal("payload in span")
			}
		}
	}
	for _, name := range []string{"capture.receive", "capture.validate", "capture.publish"} {
		if !names[name] {
			t.Fatalf("missing span %s: %v", name, names)
		}
	}
}

var _ = errors.New
var _ io.Reader
