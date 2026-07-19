package publisher

import (
	"context"
	"errors"
	"log/slog"
	"sync/atomic"
	"time"

	"github.com/twmb/franz-go/pkg/kgo"
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
	key   string
	value []byte
}
type Kafka struct {
	client *kgo.Client
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
	k := &Kafka{client: c, topic: topic, queue: make(chan record, size), stop: make(chan struct{})}
	go k.run()
	return k, nil
}
func (k *Kafka) Enqueue(_ context.Context, key string, value []byte) error {
	if !k.Ready(context.Background()) {
		return ErrUnavailable
	}
	select {
	case k.queue <- record{key, append([]byte(nil), value...)}:
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
			k.client.Produce(context.Background(), &kgo.Record{Topic: k.topic, Key: []byte(r.key), Value: r.value}, func(_ *kgo.Record, err error) {
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
