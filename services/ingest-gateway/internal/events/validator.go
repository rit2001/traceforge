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
	CaptureID string `json:"capture_id"`
}
type Validator struct{ schema *jsonschema.Schema }

func Load(path string) (*Validator, error) {
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
	return &Validator{schema: s}, nil
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
	if err := v.schema.Validate(raw); err != nil {
		return Event{}, fmt.Errorf("schema: %w", err)
	}
	if secret(data) {
		return Event{}, fmt.Errorf("known secret-bearing payload")
	}
	var e Event
	_ = json.Unmarshal(data, &e)
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
