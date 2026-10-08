package events

import (
	"os"
	"path/filepath"
	"testing"
)

func repository(t *testing.T, parts ...string) string {
	t.Helper()
	base := []string{"..", "..", "..", ".."}
	return filepath.Join(append(base, parts...)...)
}

func TestSchemaLoadFailures(t *testing.T) {
	if _, err := Load(filepath.Join(t.TempDir(), "missing.json")); err == nil {
		t.Fatal("missing schema accepted")
	}
	invalid := filepath.Join(t.TempDir(), "invalid.json")
	if err := os.WriteFile(invalid, []byte(`{"type":`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(invalid); err == nil {
		t.Fatal("malformed schema accepted")
	}
	uncompilable := filepath.Join(t.TempDir(), "uncompilable.json")
	if err := os.WriteFile(uncompilable, []byte(`{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"not-a-type"}`), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := Load(uncompilable); err == nil {
		t.Fatal("invalid schema compiled")
	}
}

func TestSharedContractFixtures(t *testing.T) {
	v, err := Load(repository(t, "schemas", "capture-event-v0.schema.json"))
	if err != nil {
		t.Fatal(err)
	}
	dir := repository(t, "schemas", "fixtures", "capture-events")
	valid, _ := os.ReadFile(filepath.Join(dir, "valid.json"))
	if _, err := v.Validate(valid); err != nil {
		t.Fatal(err)
	}
	invalid, err := filepath.Glob(filepath.Join(dir, "invalid-*.json"))
	if err != nil || len(invalid) == 0 {
		t.Fatal("negative fixtures missing")
	}
	for _, path := range invalid {
		body, _ := os.ReadFile(path)
		if _, err := v.Validate(body); err == nil {
			t.Fatalf("accepted %s", path)
		}
	}
}

func TestMalformedMultipleAndSecretValues(t *testing.T) {
	v, err := Load(repository(t, "schemas", "capture-event-v0.schema.json"))
	if err != nil {
		t.Fatal(err)
	}
	for _, body := range [][]byte{[]byte("{"), []byte("{} {}")} {
		if _, err := v.Validate(body); err == nil {
			t.Fatal("invalid JSON accepted")
		}
	}
	valid, _ := os.ReadFile(repository(t, "schemas", "fixtures", "capture-events", "valid.json"))
	secret := append([]byte(nil), valid...)
	secret = append(secret[:len(secret)-2], []byte(`,"api_key":"synthetic"}}`)...)
	if _, err := v.Validate(secret); err == nil {
		t.Fatal("secret accepted")
	}
}

func TestVersionDispatchAcceptsPortableExecutionSpanEvent(t *testing.T) {
	v, err := LoadAll(map[string]string{
		"0.2.0": repository(t, "schemas", "capture-event-v0.schema.json"),
		"0.3.0": repository(t, "schemas", "capture-event-v0.3.schema.json"),
	})
	if err != nil {
		t.Fatal(err)
	}
	body := []byte(`{"schema_version":"0.3.0","event_id":"event-1","capture_id":"capture-1","sequence":1,"event_type":"execution_span_recorded","occurred_at":"2026-07-19T12:00:00Z","producer":{"name":"fixture","version":"0.3.0"},"payload":{"execution_span_id":"root","parent_execution_span_id":null,"sequence":1,"kind":"agent","name":"root","component":"fixture"}}`)
	if _, err := v.Validate(body); err != nil {
		t.Fatal(err)
	}
	body = []byte(`{"schema_version":"0.2.0","event_id":"event-1","capture_id":"capture-1","sequence":1,"event_type":"execution_span_recorded","occurred_at":"2026-07-19T12:00:00Z","producer":{"name":"fixture","version":"0.2.0"},"payload":{"execution_span_id":"root"}}`)
	if _, err := v.Validate(body); err == nil {
		t.Fatal("0.2 event accepted a 0.3-only event_type")
	}
}

func TestVersionDispatchRejectsUnsupportedVersion(t *testing.T) {
	v, err := LoadAll(map[string]string{
		"0.2.0": repository(t, "schemas", "capture-event-v0.schema.json"),
		"0.3.0": repository(t, "schemas", "capture-event-v0.3.schema.json"),
	})
	if err != nil {
		t.Fatal(err)
	}
	body := []byte(`{"schema_version":"0.4.0","event_id":"event-1","capture_id":"capture-1","sequence":1,"event_type":"capture_started","occurred_at":"2026-07-19T12:00:00Z","producer":{"name":"fixture","version":"0.4.0"},"payload":{}}`)
	if _, err := v.Validate(body); err == nil {
		t.Fatal("unsupported version accepted")
	}
}

func TestGatewayDoesNotReinterpretExecutionSpanTreeSemantics(t *testing.T) {
	v, err := LoadAll(map[string]string{
		"0.2.0": repository(t, "schemas", "capture-event-v0.schema.json"),
		"0.3.0": repository(t, "schemas", "capture-event-v0.3.schema.json"),
	})
	if err != nil {
		t.Fatal(err)
	}
	body := []byte(`{"schema_version":"0.3.0","event_id":"event-2","capture_id":"capture-1","sequence":2,"event_type":"execution_span_recorded","occurred_at":"2026-07-19T12:00:00Z","producer":{"name":"fixture","version":"0.3.0"},"payload":{"execution_span_id":"child","parent_execution_span_id":"unknown-parent","sequence":2,"kind":"step","name":"child","component":"fixture"}}`)
	if _, err := v.Validate(body); err != nil {
		t.Fatalf("gateway applied Python-owned tree semantics: %v", err)
	}
}
