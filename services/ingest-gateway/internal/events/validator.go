package events

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"strings"

	jsonschema "github.com/santhosh-tekuri/jsonschema/v6"
)

type Event struct {
	SchemaVersion string `json:"schema_version"`
	CaptureID     string `json:"capture_id"`
}
type Validator struct{ schemas map[string]*jsonschema.Schema }

func Load(path string) (*Validator, error) {
	return LoadAll(map[string]string{"0.2.0": path})
}

func LoadAll(paths map[string]string) (*Validator, error) {
	schemas := make(map[string]*jsonschema.Schema, len(paths))
	for version, path := range paths {
		schema, err := compile(path)
		if err != nil {
			return nil, err
		}
		schemas[version] = schema
	}
	return &Validator{schemas: schemas}, nil
}

func compile(path string) (*jsonschema.Schema, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var document any
	if err := json.Unmarshal(data, &document); err != nil {
		return nil, err
	}
	c := jsonschema.NewCompiler()
	if err = c.AddResource("capture-event.json", document); err != nil {
		return nil, err
	}
	s, err := c.Compile("capture-event.json")
	if err != nil {
		return nil, err
	}
	return s, nil
}
func (v *Validator) Validate(data []byte) (Event, error) {
	var raw any
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	if err := dec.Decode(&raw); err != nil {
		return Event{}, fmt.Errorf("malformed JSON: %w", err)
	}
	if dec.Decode(&struct{}{}) == nil {
		return Event{}, fmt.Errorf("multiple JSON values")
	}
	var e Event
	if err := json.Unmarshal(data, &e); err != nil {
		return Event{}, fmt.Errorf("malformed JSON: %w", err)
	}
	schema, ok := v.schemas[e.SchemaVersion]
	if !ok {
		return Event{}, fmt.Errorf("unsupported capture-event schema_version %q", e.SchemaVersion)
	}
	if err := schema.Validate(raw); err != nil {
		return Event{}, fmt.Errorf("schema: %w", err)
	}
	if secret(data) {
		return Event{}, fmt.Errorf("known secret-bearing payload")
	}
	return e, nil
}
func secret(data []byte) bool {
	s := strings.ToLower(string(data))
	for _, term := range []string{"authorization", "cookie", "api_key", "api-key", "access_token", "access-token", "bearer "} {
		if strings.Contains(s, term) {
			return true
		}
	}
	return false
}
