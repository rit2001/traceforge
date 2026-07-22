package httpapi

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"mime"
	"net/http"
	"strings"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/codes"
	"traceforge/ingest-gateway/internal/events"
	"traceforge/ingest-gateway/internal/publisher"
)

type API struct {
	validator        *events.Validator
	publisher        publisher.Publisher
	maxBody          int64
	requests         *prometheus.CounterVec
	accepted         prometheus.Counter
	rejected         prometheus.Counter
	queueFull        prometheus.Counter
	duration         prometheus.Histogram
	deliveryFailures prometheus.GaugeFunc
}

func New(v *events.Validator, p publisher.Publisher, maxBody int64, reg *prometheus.Registry) *API {
	a := &API{validator: v, publisher: p, maxBody: maxBody, requests: prometheus.NewCounterVec(prometheus.CounterOpts{Name: "traceforge_gateway_requests_total", Help: "HTTP requests"}, []string{"endpoint"}), rejected: prometheus.NewCounter(prometheus.CounterOpts{Name: "traceforge_gateway_rejected_events_total", Help: "Rejected events"}), queueFull: prometheus.NewCounter(prometheus.CounterOpts{Name: "traceforge_gateway_queue_full_total", Help: "Full queue"}), duration: prometheus.NewHistogram(prometheus.HistogramOpts{Name: "traceforge_gateway_http_duration_seconds", Help: "HTTP duration"})}
	a.accepted = prometheus.NewCounter(prometheus.CounterOpts{Name: "traceforge_gateway_accepted_events_total", Help: "Accepted events"})
	a.deliveryFailures = prometheus.NewGaugeFunc(
		prometheus.GaugeOpts{
			Name: "traceforge_gateway_delivery_failures_total",
			Help: "Asynchronous Kafka delivery failures",
		},
		func() float64 { return float64(p.DeliveryFailures()) },
	)
	reg.MustRegister(
		a.requests, a.accepted, a.rejected, a.queueFull, a.duration, a.deliveryFailures,
	)
	return a
}
func (a *API) Handler(reg *prometheus.Registry) http.Handler {
	m := http.NewServeMux()
	m.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) { jsonStatus(w, 200, "ok") })
	m.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		if !a.publisher.Ready(r.Context()) {
			jsonStatus(w, 503, "unready")
			return
		}
		jsonStatus(w, 200, "ready")
	})
	m.Handle("/metrics", promhttp.HandlerFor(reg, promhttp.HandlerOpts{}))
	m.Handle(
		"/v1/capture-events",
		otelhttp.NewHandler(
			http.HandlerFunc(a.capture),
			"capture.receive",
			otelhttp.WithSpanNameFormatter(func(string, *http.Request) string {
				return "capture.receive"
			}),
		),
	)
	return m
}
func (a *API) capture(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	defer func() { a.duration.Observe(time.Since(start).Seconds()) }()
	a.requests.WithLabelValues("capture").Inc()
	if r.Header.Get("Authorization") != "" || r.Header.Get("Cookie") != "" || unsafeQuery(r) {
		a.rejected.Inc()
		http.Error(w, "request contains prohibited secret material", 400)
		return
	}
	media, _, err := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if err != nil || media != "application/json" {
		a.rejected.Inc()
		http.Error(w, "content-type must be application/json", 415)
		return
	}
	body, err := io.ReadAll(io.LimitReader(r.Body, a.maxBody+1))
	if err != nil || int64(len(body)) > a.maxBody {
		a.rejected.Inc()
		http.Error(w, "request body exceeds limit", 413)
		return
	}
	validateContext, validateSpan := otel.Tracer("traceforge/ingest-gateway").Start(r.Context(), "capture.validate")
	event, err := a.validator.Validate(body)
	if err != nil {
		validateSpan.RecordError(errors.New("validation failed"))
		validateSpan.SetStatus(codes.Error, "validation failed")
	}
	validateSpan.End()
	if err != nil {
		a.rejected.Inc()
		slog.Warn("capture rejected", "reason", "validation")
		http.Error(w, "invalid capture event", 400)
		return
	}
	publishContext, publishSpan := otel.Tracer("traceforge/ingest-gateway").Start(validateContext, "capture.publish")
	err = a.publisher.Enqueue(publishContext, event.CaptureID, body)
	if err != nil {
		publishSpan.RecordError(err)
		publishSpan.SetStatus(codes.Error, "publish failed")
	}
	publishSpan.End()
	if err == publisher.ErrFull {
		a.queueFull.Inc()
		http.Error(w, "producer queue full", 429)
		return
	}
	if err != nil {
		http.Error(w, "gateway unavailable", 503)
		return
	}
	a.accepted.Inc()
	jsonStatus(w, 202, "accepted")
}
func unsafeQuery(r *http.Request) bool {
	for key := range r.URL.Query() {
		switch strings.ToLower(strings.ReplaceAll(key, "_", "-")) {
		case "token", "access-token", "api-key", "secret", "client-secret":
			return true
		}
	}
	return false
}
func jsonStatus(w http.ResponseWriter, code int, status string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_, _ = io.WriteString(w, `{"status":"`+status+`"}`)
}
func Shutdown(ctx context.Context, p publisher.Publisher) error { return p.Close(ctx) }
