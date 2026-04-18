// demo-backend is a lightweight HTTP service used as the scaling target
// for Sentinel's local autoscaling demo. It simulates realistic API behavior:
// - Normal: 10-50ms latency, 200 OK
// - Under load: latency increases to 200-500ms
// - Near capacity: occasional 503 errors (5-10%)
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"sync/atomic"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	activeRequests int64

	reqTotal = prometheus.NewCounterVec(
		prometheus.CounterOpts{
			Name: "demo_backend_requests_total",
			Help: "Total requests processed",
		},
		[]string{"status"},
	)
	reqLatency = prometheus.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "demo_backend_latency_seconds",
			Help:    "Request latency in seconds",
			Buckets: []float64{0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0},
		},
	)
	activeGauge = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "demo_backend_active_requests",
			Help: "Currently active requests",
		},
	)
)

func init() {
	prometheus.MustRegister(reqTotal, reqLatency, activeGauge)
}

func main() {
	port := envOr("PORT", "8081")

	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]string{"status": "ok", "service": "demo-backend"})
	})

	mux.Handle("/metrics", promhttp.Handler())

	mux.HandleFunc("/api/", handleAPI)

	log.Printf("demo-backend starting on :%s", port)
	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
	}
	log.Fatal(srv.ListenAndServe())
}

func handleAPI(w http.ResponseWriter, r *http.Request) {
	start := time.Now()
	active := atomic.AddInt64(&activeRequests, 1)
	activeGauge.Set(float64(active))
	defer func() {
		atomic.AddInt64(&activeRequests, -1)
		activeGauge.Dec()
	}()

	// Simulate load-dependent latency
	// Base latency: 10-50ms
	// Under load (>50 concurrent): add 50-200ms
	// Near capacity (>100 concurrent): add 200-500ms + error chance
	baseMs := 10 + rand.Intn(40)
	loadMs := 0

	if active > 100 {
		// Near capacity: high latency + error chance
		loadMs = 200 + rand.Intn(300)
		errorChance := float64(active-100) / 200.0 // 0→50% over 100→300 concurrent
		if errorChance > 0.5 {
			errorChance = 0.5
		}
		if rand.Float64() < errorChance {
			time.Sleep(time.Duration(baseMs+loadMs) * time.Millisecond)
			latency := time.Since(start).Seconds()
			reqLatency.Observe(latency)
			reqTotal.WithLabelValues("503").Inc()
			writeJSON(w, 503, map[string]string{
				"error":  "service_overloaded",
				"reason": fmt.Sprintf("active_connections=%d exceeds capacity", active),
			})
			return
		}
	} else if active > 50 {
		// Under pressure: moderate latency increase
		loadMs = 50 + rand.Intn(150)
	}

	sleepMs := baseMs + loadMs
	time.Sleep(time.Duration(sleepMs) * time.Millisecond)

	latency := time.Since(start).Seconds()
	reqLatency.Observe(latency)
	reqTotal.WithLabelValues("200").Inc()

	writeJSON(w, 200, map[string]interface{}{
		"status":     "processed",
		"latency_ms": sleepMs,
		"active":     active,
		"timestamp":  time.Now().UnixMilli(),
	})
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
