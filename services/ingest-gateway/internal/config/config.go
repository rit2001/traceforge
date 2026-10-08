package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	Address, Brokers, Topic, SchemaPath, SchemaPathV03 string
	MaxBody                                            int64
	QueueSize                                          int
	Shutdown                                           time.Duration
}

func Load() (Config, error) {
	maxBody, err := number("MAX_BODY_BYTES", 1<<20)
	if err != nil {
		return Config{}, err
	}
	queueSize, err := number("PRODUCER_QUEUE_SIZE", 256)
	if err != nil {
		return Config{}, err
	}
	return Config{Address: value("GATEWAY_ADDRESS", ":8080"), Brokers: value("KAFKA_BOOTSTRAP_SERVERS", "kafka:19092"), Topic: value("KAFKA_TOPIC", "traceforge.capture.v1"), SchemaPath: value("CAPTURE_EVENT_SCHEMA", "/schemas/capture-event-v0.schema.json"), SchemaPathV03: value("CAPTURE_EVENT_SCHEMA_V03", "/schemas/capture-event-v0.3.schema.json"), MaxBody: int64(maxBody), QueueSize: queueSize, Shutdown: 5 * time.Second}, nil
}
func value(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
func number(key string, fallback int) (int, error) {
	raw := os.Getenv(key)
	if raw == "" {
		return fallback, nil
	}
	v, err := strconv.Atoi(raw)
	if err != nil || v < 1 {
		return 0, fmt.Errorf("%s must be a positive integer", key)
	}
	return v, nil
}
