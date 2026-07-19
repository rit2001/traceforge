package main

import (
	"context"
	"errors"
	"github.com/prometheus/client_golang/prometheus"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"
	"traceforge/ingest-gateway/internal/config"
	"traceforge/ingest-gateway/internal/events"
	"traceforge/ingest-gateway/internal/httpapi"
	"traceforge/ingest-gateway/internal/publisher"
)

func main() {
	cfg := config.Load()
	slog.SetDefault(slog.New(slog.NewJSONHandler(os.Stdout, nil)))
	v, err := events.Load(cfg.SchemaPath)
	if err != nil {
		slog.Error("schema unavailable", "error_type", "schema")
		os.Exit(1)
	}
	p, err := publisher.NewKafka(strings.Split(cfg.Brokers, ","), cfg.Topic, cfg.QueueSize)
	if err != nil {
		slog.Error("publisher unavailable", "error_type", "publisher")
		os.Exit(1)
	}
	reg := prometheus.NewRegistry()
	api := httpapi.New(v, p, cfg.MaxBody, reg)
	srv := &http.Server{Addr: cfg.Address, Handler: api.Handler(reg), ReadHeaderTimeout: 5 * time.Second}
	go func() {
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			slog.Error("server failed", "error_type", "http")
		}
	}()
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
	ctx, cancel := context.WithTimeout(context.Background(), cfg.Shutdown)
	defer cancel()
	_ = srv.Shutdown(ctx)
	_ = httpapi.Shutdown(ctx, p)
}
