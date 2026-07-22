package publisher

import (
	"context"
	"errors"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/twmb/franz-go/pkg/kgo"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
)

type fakeClient struct {
	mu         sync.Mutex
	pingErr    error
	record     *kgo.Record
	callback   func(*kgo.Record, error)
	flushBlock chan struct{}
	closed     bool
}

func (f *fakeClient) Ping(context.Context) error { f.mu.Lock(); defer f.mu.Unlock(); return f.pingErr }
func (f *fakeClient) Produce(_ context.Context, r *kgo.Record, cb func(*kgo.Record, error)) {
	f.mu.Lock()
	f.record = r
	f.callback = cb
	f.mu.Unlock()
}
func (f *fakeClient) Flush(context.Context) error {
	if f.flushBlock != nil {
		<-f.flushBlock
	}
	return nil
}
func (f *fakeClient) Close() { f.mu.Lock(); f.closed = true; f.mu.Unlock() }

func TestAcceptedKeyAndCallbackPaths(t *testing.T) {
	c := &fakeClient{}
	p := newKafka(c, "topic", 1, true)
	if err := p.Enqueue(context.Background(), "capture-1", []byte("safe")); err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(time.Second)
	for {
		c.mu.Lock()
		cb, r := c.callback, c.record
		c.mu.Unlock()
		if cb != nil {
			if string(r.Key) != "capture-1" {
				t.Fatal(string(r.Key))
			}
			cb(r, errors.New("delivery"))
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("record not produced")
		}
		time.Sleep(time.Millisecond)
	}
	if p.DeliveryFailures() != 1 {
		t.Fatal("callback failure not counted")
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err := p.Close(ctx); err != nil {
		t.Fatal(err)
	}
}
func TestUnavailableQueueFullAndRecovery(t *testing.T) {
	c := &fakeClient{pingErr: errors.New("down")}
	p := newKafka(c, "topic", 1, false)
	if err := p.Enqueue(context.Background(), "a", nil); !errors.Is(err, ErrUnavailable) {
		t.Fatal(err)
	}
	c.mu.Lock()
	c.pingErr = nil
	c.mu.Unlock()
	if !p.Ready(context.Background()) {
		t.Fatal("readiness did not recover")
	}
	if err := p.Enqueue(context.Background(), "a", nil); err != nil {
		t.Fatal(err)
	}
	if err := p.Enqueue(context.Background(), "b", nil); !errors.Is(err, ErrFull) {
		t.Fatal(err)
	}
}
func TestBoundedShutdown(t *testing.T) {
	block := make(chan struct{})
	c := &fakeClient{flushBlock: block}
	p := newKafka(c, "topic", 1, false)
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	if err := p.Close(ctx); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatal(err)
	}
	close(block)
}

func TestTraceHeadersInjected(t *testing.T) {
	otel.SetTextMapPropagator(propagation.TraceContext{})
	traceID, _ := trace.TraceIDFromHex("00112233445566778899aabbccddeeff")
	spanID, _ := trace.SpanIDFromHex("0011223344556677")
	state, _ := trace.ParseTraceState("vendor=value")
	ctx := trace.ContextWithSpanContext(context.Background(), trace.NewSpanContext(
		trace.SpanContextConfig{TraceID: traceID, SpanID: spanID, TraceFlags: trace.FlagsSampled, TraceState: state},
	))
	c := &fakeClient{}
	p := newKafka(c, "topic", 1, true)
	if err := p.Enqueue(ctx, "capture-1", []byte("safe")); err != nil {
		t.Fatal(err)
	}
	deadline := time.Now().Add(time.Second)
	for {
		c.mu.Lock()
		record := c.record
		c.mu.Unlock()
		if record != nil {
			headers := map[string]string{}
			for _, header := range record.Headers {
				headers[header.Key] = string(header.Value)
			}
			if !strings.Contains(headers["traceparent"], traceID.String()) {
				t.Fatal(headers)
			}
			if headers["tracestate"] != "vendor=value" {
				t.Fatal(headers)
			}
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("record not produced")
		}
		time.Sleep(time.Millisecond)
	}
	ctxClose, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	_ = p.Close(ctxClose)
}

func TestKafkaHeaderCarrierContract(t *testing.T) {
	carrier := headerCarrier{
		{Key: "traceparent", Value: []byte("parent")},
		{Key: "tracestate", Value: []byte("vendor=value")},
	}
	if carrier.Get("traceparent") != "parent" || carrier.Get("missing") != "" {
		t.Fatal("carrier lookup failed")
	}
	keys := carrier.Keys()
	if len(keys) != 2 || keys[0] != "traceparent" || keys[1] != "tracestate" {
		t.Fatalf("unexpected keys: %v", keys)
	}
}

func TestProductionPublisherConstructionAndShutdown(t *testing.T) {
	p, err := NewKafka([]string{"127.0.0.1:1"}, "traceforge.capture.v1", 1)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	if err := p.Close(ctx); err != nil {
		t.Fatal(err)
	}
}
