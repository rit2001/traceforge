package config

import (
	"os"
	"strconv"
	"time"
)

type Config struct {
	Address, Brokers, Topic, SchemaPath string
	MaxBody                             int64
	QueueSize                           int
	Shutdown                            time.Duration
}

func Load() Config {
	return Config{Address: value("GATEWAY_ADDRESS", ":8080"), Brokers: value("KAFKA_BOOTSTRAP_SERVERS", "kafka:19092"), Topic: value("KAFKA_TOPIC", "traceforge.capture.v1"), SchemaPath: value("CAPTURE_EVENT_SCHEMA", "/schemas/capture-event-v0.schema.json"), MaxBody: int64(number("MAX_BODY_BYTES", 1<<20)), QueueSize: number("PRODUCER_QUEUE_SIZE", 256), Shutdown: 5 * time.Second}
}
func value(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
func number(key string, fallback int) int {
	v, err := strconv.Atoi(os.Getenv(key))
	if err != nil || v < 1 {
		return fallback
	}
	return v
}
