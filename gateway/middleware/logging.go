package middleware

import (
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/Deepanshu954/sentinel/gateway/metrics"
)

// responseCapture wraps http.ResponseWriter to capture status code and bytes written.
type responseCapture struct {
	http.ResponseWriter
	statusCode   int
	bytesWritten int
}

func newResponseCapture(w http.ResponseWriter) *responseCapture {
	return &responseCapture{ResponseWriter: w, statusCode: http.StatusOK}
}

func (rc *responseCapture) WriteHeader(code int) {
	rc.statusCode = code
	rc.ResponseWriter.WriteHeader(code)
}

func (rc *responseCapture) Write(b []byte) (int, error) {
	n, err := rc.ResponseWriter.Write(b)
	rc.bytesWritten += n
	return n, err
}

// LoggingMiddleware logs every request with structured JSON fields:
// method, path, status, latency_ms, client_id, bytes.
// Also records Prometheus request count and latency histogram.
func LoggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rc := newResponseCapture(w)

		next.ServeHTTP(rc, r)

		latency := time.Since(start)
		clientID := ClientIDFromContext(r.Context())

		// Normalize route to prevent unbounded Prometheus label cardinality.
		// Raw paths like /api/products/123 would create infinite time series.
		route := normalizeRoute(r.URL.Path)

		// Record Prometheus metrics
		statusLabel := fmt.Sprintf("%d", rc.statusCode)
		metrics.RequestsTotal.WithLabelValues(r.Method, route, statusLabel).Inc()
		metrics.LatencySeconds.WithLabelValues(r.Method, route).Observe(latency.Seconds())

		slog.Info("request completed",
			"method", r.Method,
			"path", r.URL.Path,
			"status", rc.statusCode,
			"latency_ms", latency.Milliseconds(),
			"client_id", clientID,
			"bytes", rc.bytesWritten,
		)
	})
}

// normalizeRoute collapses raw URL paths into bounded route labels
// to prevent Prometheus cardinality explosion. Maps all /api/* paths
// to a single "/api/*" label, and keeps /health and /metrics as-is.
func normalizeRoute(path string) string {
	switch {
	case path == "/health" || path == "/metrics":
		return path
	case strings.HasPrefix(path, "/api/"):
		return "/api/*"
	default:
		return "/other"
	}
}
