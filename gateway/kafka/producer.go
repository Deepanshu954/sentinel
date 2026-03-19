package kafka

import (
	"encoding/json"
	"log/slog"
	"sync"

	"github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

// APIEvent matches the api.events schema from SENTINEL_CONTEXT.md.
type APIEvent struct {
	Ts        int64  `json:"ts"`
	Endpoint  string `json:"endpoint"`
	Method    string `json:"method"`
	ClientID  string `json:"client_id"`
	LatencyMs int64  `json:"latency_ms"`
	Status    int    `json:"status"`
	BytesSent int    `json:"bytes_sent"`
}

const topic = "api.events"

// Producer wraps the confluent Kafka producer with async delivery reports.
type Producer struct {
	producer *kafka.Producer
	wg       sync.WaitGroup
	closed   chan struct{}
}

// NewProducer creates a Kafka producer connected to the given brokers.
// It starts a background goroutine to consume delivery reports.
func NewProducer(brokers string) (*Producer, error) {
	p, err := kafka.NewProducer(&kafka.ConfigMap{
		"bootstrap.servers":  brokers,
		"acks":               "1",
		"retries":            3,
		"linger.ms":          5,
		"compression.type":   "snappy",
		"delivery.timeout.ms": 10000,
	})
	if err != nil {
		return nil, err
	}

	prod := &Producer{
		producer: p,
		closed:   make(chan struct{}),
	}

	prod.wg.Add(1)
	go prod.deliveryReports()

	return prod, nil
}

// deliveryReports drains the Events channel, logging errors asynchronously.
func (p *Producer) deliveryReports() {
	defer p.wg.Done()
	for {
		select {
		case e, ok := <-p.producer.Events():
			if !ok {
				return
			}
			msg, ok := e.(*kafka.Message)
			if !ok {
				continue
			}
			if msg.TopicPartition.Error != nil {
				slog.Error("kafka delivery failed",
					"topic", *msg.TopicPartition.Topic,
					"error", msg.TopicPartition.Error,
				)
			}
		case <-p.closed:
			return
		}
	}
}

// PublishEvent serializes the event to JSON and produces it to api.events.
// Fire-and-forget: errors are logged via the delivery report goroutine.
func (p *Producer) PublishEvent(event APIEvent) {
	data, err := json.Marshal(event)
	if err != nil {
		slog.Error("failed to marshal api event", "error", err)
		return
	}

	topicName := topic
	err = p.producer.Produce(&kafka.Message{
		TopicPartition: kafka.TopicPartition{
			Topic:     &topicName,
			Partition: kafka.PartitionAny,
		},
		Key:   []byte(event.ClientID),
		Value: data,
	}, nil)
	if err != nil {
		slog.Error("failed to enqueue kafka message", "error", err)
	}
}

// Close flushes outstanding messages and shuts down the producer.
func (p *Producer) Close() {
	p.producer.Flush(5000)
	close(p.closed)
	p.producer.Close()
	p.wg.Wait()
}
