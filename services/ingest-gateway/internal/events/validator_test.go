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
