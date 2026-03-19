package middleware

import (
	"fmt"
	"log/slog"
	"net/http"
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

		// Record Prometheus metrics
		statusLabel := fmt.Sprintf("%d", rc.statusCode)
		metrics.RequestsTotal.WithLabelValues(r.Method, r.URL.Path, statusLabel).Inc()
		metrics.LatencySeconds.WithLabelValues(r.Method, r.URL.Path).Observe(latency.Seconds())

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
