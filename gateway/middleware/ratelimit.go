package middleware

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/Deepanshu954/sentinel/gateway/metrics"
)

// RateLimitMiddleware enforces per-client token-bucket rate limiting via Redis.
// Uses INCR + EXPIRE 60s pattern. Fails open if Redis is unavailable.
func RateLimitMiddleware(rdb *redis.Client) func(http.Handler) http.Handler {
	limit := 1000
	if v := os.Getenv("RATE_LIMIT_PER_MIN"); v != "" {
		if parsed, err := strconv.Atoi(v); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Skip rate limiting for health and metrics
			if r.URL.Path == "/health" || r.URL.Path == "/metrics" {
				next.ServeHTTP(w, r)
				return
			}

			clientID := ClientIDFromContext(r.Context())
			key := fmt.Sprintf("ratelimit:%s", clientID)

			ctx := r.Context()
			allowed, err := checkRateLimit(ctx, rdb, key, limit)
			if err != nil {
				// Fail open — let the request through but log warning
				slog.Warn("redis rate limit check failed, allowing request",
					"client_id", clientID,
					"error", err,
				)
				next.ServeHTTP(w, r)
				return
			}

			if !allowed {
				metrics.RateLimitedTotal.WithLabelValues(clientID).Inc()
				slog.Warn("rate limit exceeded", "client_id", clientID, "limit", limit)
				w.Header().Set("Content-Type", "application/json")
				w.Header().Set("Retry-After", "60")
				w.WriteHeader(http.StatusTooManyRequests)
				json.NewEncoder(w).Encode(map[string]interface{}{
					"error":       "rate_limit_exceeded",
					"retry_after": 60,
				})
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// checkRateLimit performs INCR on the key and sets a 60s TTL on first use.
// Returns true if the request is allowed.
func checkRateLimit(ctx context.Context, rdb *redis.Client, key string, limit int) (bool, error) {
	count, err := rdb.Incr(ctx, key).Result()
	if err != nil {
		return false, err
	}

	// On first increment, set the 60s expiry window.
	if count == 1 {
		if err := rdb.Expire(ctx, key, time.Minute).Err(); err != nil {
			slog.Warn("failed to set expire on rate limit key", "key", key, "error", err)
		}
	}

	return count <= int64(limit), nil
}
