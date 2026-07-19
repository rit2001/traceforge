package publisher

import (
	"context"
	"errors"
	"log/slog"
	"sync/atomic"
	"time"

	"github.com/twmb/franz-go/pkg/kgo"
	"go.opentelemetry.io/otel"
)

var ErrFull = errors.New("producer queue full")
var ErrUnavailable = errors.New("producer unavailable")

type Publisher interface {
	Enqueue(context.Context, string, []byte) error
	Ready(context.Context) bool
	Close(context.Context) error
	DeliveryFailures() uint64
}
type record struct {
	key     string
	value   []byte
	headers []kgo.RecordHeader
}
type headerCarrier []kgo.RecordHeader

func (c *headerCarrier) Get(key string) string {
	for _, h := range *c {
		if h.Key == key {
			return string(h.Value)
		}
	}
	return ""
}
func (c *headerCarrier) Set(key, value string) {
	*c = append(*c, kgo.RecordHeader{Key: key, Value: []byte(value)})
}
func (c *headerCarrier) Keys() []string {
	keys := make([]string, 0, len(*c))
	for _, h := range *c {
		keys = append(keys, h.Key)
	}
	return keys
}

type client interface {
	Ping(context.Context) error
	Produce(context.Context, *kgo.Record, func(*kgo.Record, error))
	Flush(context.Context) error
	Close()
}
type Kafka struct {
	client client
	topic  string
	queue  chan record
	stop   chan struct{}
	failed atomic.Uint64
}

func NewKafka(brokers []string, topic string, size int) (*Kafka, error) {
	c, err := kgo.NewClient(kgo.SeedBrokers(brokers...), kgo.AllowAutoTopicCreation())
	if err != nil {
		return nil, err
	}
	return newKafka(c, topic, size, true), nil
}
func newKafka(c client, topic string, size int, start bool) *Kafka {
	k := &Kafka{client: c, topic: topic, queue: make(chan record, size), stop: make(chan struct{})}
	if start {
		go k.run()
	}
	return k
}
func (k *Kafka) Enqueue(ctx context.Context, key string, value []byte) error {
	if !k.Ready(context.Background()) {
		return ErrUnavailable
	}
	carrier := headerCarrier{}
	otel.GetTextMapPropagator().Inject(ctx, &carrier)
	select {
	case k.queue <- record{key: key, value: append([]byte(nil), value...), headers: carrier}:
		return nil
	default:
		return ErrFull
	}
}
func (k *Kafka) Ready(ctx context.Context) bool {
	ctx, cancel := context.WithTimeout(ctx, 500*time.Millisecond)
	defer cancel()
	return k.client.Ping(ctx) == nil
}
func (k *Kafka) run() {
	for {
		select {
		case r := <-k.queue:
			k.client.Produce(context.Background(), &kgo.Record{Topic: k.topic, Key: []byte(r.key), Value: r.value, Headers: r.headers}, func(_ *kgo.Record, err error) {
				if err != nil {
					k.failed.Add(1)
					slog.Error("Kafka delivery failed", "error_type", "delivery")
				}
			})
		case <-k.stop:
			return
		}
	}
}
func (k *Kafka) Close(ctx context.Context) error {
	close(k.stop)
	done := make(chan struct{})
	go func() { k.client.Flush(ctx); k.client.Close(); close(done) }()
	select {
	case <-done:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}
func (k *Kafka) DeliveryFailures() uint64 { return k.failed.Load() }
