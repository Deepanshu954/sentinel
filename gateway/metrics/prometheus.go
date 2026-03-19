package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// RequestsTotal counts total requests by method, endpoint, and HTTP status.
var RequestsTotal = promauto.NewCounterVec(
	prometheus.CounterOpts{
		Name: "sentinel_gateway_requests_total",
		Help: "Total number of HTTP requests processed by the gateway.",
	},
	[]string{"method", "endpoint", "status"},
)

// LatencySeconds observes request latency in seconds.
var LatencySeconds = promauto.NewHistogramVec(
	prometheus.HistogramOpts{
		Name:    "sentinel_gateway_latency_seconds",
		Help:    "Histogram of request latency in seconds.",
		Buckets: []float64{.005, .01, .025, .05, .1, .25, .5, 1, 2.5},
	},
	[]string{"method", "endpoint"},
)

// RateLimitedTotal counts rate-limited requests by client_id.
var RateLimitedTotal = promauto.NewCounterVec(
	prometheus.CounterOpts{
		Name: "sentinel_gateway_rate_limited_total",
		Help: "Total number of requests rejected by rate limiting.",
	},
	[]string{"client_id"},
)
