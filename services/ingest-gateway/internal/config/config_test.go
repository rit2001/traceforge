package config

import "testing"

func TestDefaults(t *testing.T) {
	t.Setenv("GATEWAY_ADDRESS", "")
	t.Setenv("KAFKA_BOOTSTRAP_SERVERS", "")
	t.Setenv("KAFKA_TOPIC", "")
	t.Setenv("CAPTURE_EVENT_SCHEMA", "")
	t.Setenv("CAPTURE_EVENT_SCHEMA_V03", "")
	t.Setenv("MAX_BODY_BYTES", "")
	t.Setenv("PRODUCER_QUEUE_SIZE", "")
	cfg, err := Load()
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Address != ":8080" || cfg.Brokers != "kafka:19092" || cfg.MaxBody != 1<<20 || cfg.QueueSize != 256 || cfg.SchemaPathV03 != "/schemas/capture-event-v0.3.schema.json" {
		t.Fatalf("unexpected defaults: %+v", cfg)
	}
}

func TestOverridesAndInvalidNumbers(t *testing.T) {
	t.Setenv("GATEWAY_ADDRESS", "127.0.0.1:9999")
	t.Setenv("CAPTURE_EVENT_SCHEMA_V03", "/tmp/capture-event-v0.3.schema.json")
	t.Setenv("MAX_BODY_BYTES", "42")
	t.Setenv("PRODUCER_QUEUE_SIZE", "7")
	cfg, err := Load()
	if err != nil || cfg.Address != "127.0.0.1:9999" || cfg.SchemaPathV03 != "/tmp/capture-event-v0.3.schema.json" || cfg.MaxBody != 42 || cfg.QueueSize != 7 {
		t.Fatalf("cfg=%+v err=%v", cfg, err)
	}
	for _, value := range []string{"zero", "0", "-1"} {
		t.Setenv("MAX_BODY_BYTES", value)
		if _, err := Load(); err == nil {
			t.Fatalf("accepted %q", value)
		}
	}
}
