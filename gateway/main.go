package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/signal"
	"runtime/debug"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/redis/go-redis/v9"

	"github.com/Deepanshu954/sentinel/gateway/kafka"
	"github.com/Deepanshu954/sentinel/gateway/middleware"
)

func main() {
	// ── Structured JSON logging ──────────────────────────────────────────
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	slog.Info("sentinel gateway starting")

	// ── Configuration from environment ───────────────────────────────────
	port := envOr("PORT", "8080")
	targetURL := envOr("TARGET_URL", "http://localhost:9999")
	kafkaBrokers := envOr("KAFKA_BROKERS", "kafka:9092")
	redisAddr := envOr("REDIS_ADDR", "redis:6379")

	// ── Redis client (shared, thread-safe) ───────────────────────────────
	rdb := redis.NewClient(&redis.Options{
		Addr:         redisAddr,
		PoolSize:     20,
		MinIdleConns: 5,
		DialTimeout:  3 * time.Second,
		ReadTimeout:  2 * time.Second,
		WriteTimeout: 2 * time.Second,
	})
	defer rdb.Close()

	// ── Kafka producer ───────────────────────────────────────────────────
	kafkaProducer, err := kafka.NewProducer(kafkaBrokers)
	if err != nil {
		slog.Error("failed to create kafka producer", "error", err)
		os.Exit(1)
	}
	defer kafkaProducer.Close()
	slog.Info("kafka producer connected", "brokers", kafkaBrokers)

	// ── Reverse proxy ────────────────────────────────────────────────────
	target, err := url.Parse(targetURL)
	if err != nil {
		slog.Error("invalid TARGET_URL", "url", targetURL, "error", err)
		os.Exit(1)
	}
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		slog.Error("proxy error", "error", err, "target", targetURL)
		writeJSON(w, http.StatusBadGateway, map[string]string{
			"error":  "bad_gateway",
			"reason": "upstream service unavailable",
		})
	}

	// ── Routes ───────────────────────────────────────────────────────────
	mux := http.NewServeMux()

	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{
			"status":  "ok",
			"service": "sentinel-gateway",
		})
	})

	mux.Handle("GET /metrics", promhttp.Handler())

	// /api/* routes are proxied; publish Kafka event after response
	mux.HandleFunc("/api/", func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rc := &statusCapture{ResponseWriter: w, statusCode: http.StatusOK}

		proxy.ServeHTTP(rc, r)

		latencyMs := time.Since(start).Milliseconds()
		clientID := middleware.ClientIDFromContext(r.Context())

		kafkaProducer.PublishEvent(kafka.APIEvent{
			Ts:        time.Now().UnixMilli(),
			Endpoint:  r.URL.Path,
			Method:    r.Method,
			ClientID:  clientID,
			LatencyMs: latencyMs,
			Status:    rc.statusCode,
			BytesSent: rc.bytesWritten,
		})
	})

	// ── Middleware chain ─────────────────────────────────────────────────
	// Order: Recovery → Logging → Auth → RateLimit → Handler
	var handler http.Handler = mux
	handler = middleware.RateLimitMiddleware(rdb)(handler)
	handler = middleware.AuthMiddleware(handler)
	handler = middleware.LoggingMiddleware(handler)
	handler = recoveryMiddleware(handler)

	// ── HTTP server ──────────────────────────────────────────────────────
	srv := &http.Server{
		Addr:         ":" + port,
		Handler:      handler,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	// ── Graceful shutdown ────────────────────────────────────────────────
	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGTERM, syscall.SIGINT)

	go func() {
		slog.Info("listening", "addr", srv.Addr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("server error", "error", err)
			os.Exit(1)
		}
	}()

	<-stop
	slog.Info("shutdown signal received, draining connections")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		slog.Error("forced shutdown", "error", err)
	}

	slog.Info("sentinel gateway stopped")
}

// ── Helpers ──────────────────────────────────────────────────────────────────

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

// statusCapture captures the response status and bytes for Kafka events.
type statusCapture struct {
	http.ResponseWriter
	statusCode   int
	bytesWritten int
}

func (sc *statusCapture) WriteHeader(code int) {
	sc.statusCode = code
	sc.ResponseWriter.WriteHeader(code)
}

func (sc *statusCapture) Write(b []byte) (int, error) {
	n, err := sc.ResponseWriter.Write(b)
	sc.bytesWritten += n
	return n, err
}

// recoveryMiddleware catches panics and returns a 500 JSON response.
func recoveryMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				slog.Error("panic recovered",
					"error", rec,
					"stack", string(debug.Stack()),
				)
				writeJSON(w, http.StatusInternalServerError, map[string]string{
					"error":  "internal_server_error",
					"reason": "an unexpected error occurred",
				})
			}
		}()
		next.ServeHTTP(w, r)
	})
}
