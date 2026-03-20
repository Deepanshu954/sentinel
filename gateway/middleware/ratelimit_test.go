package middleware

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

func TestRateLimitMiddleware(t *testing.T) {
	s, err := miniredis.Run()
	if err != nil {
		t.Fatalf("failed to start miniredis: %v", err)
	}
	defer s.Close()

	rdb := redis.NewClient(&redis.Options{
		Addr: s.Addr(),
	})

	os.Setenv("RATE_LIMIT_PER_MIN", "2")
	defer os.Unsetenv("RATE_LIMIT_PER_MIN")

	nextHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	})

	handler := RateLimitMiddleware(rdb)(nextHandler)

	tests := []struct {
		name           string
		path           string
		clientID       string
		expectedStatus int
	}{
		{
			name:           "Health Check Bypass 1",
			path:           "/health",
			clientID:       "client1",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "Health Check Bypass 2",
			path:           "/health",
			clientID:       "client1",
			expectedStatus: http.StatusOK, // shouldn't consume quota
		},
		{
			name:           "API Request 1 (Success)",
			path:           "/api",
			clientID:       "client1",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "API Request 2 (Success)",
			path:           "/api",
			clientID:       "client1",
			expectedStatus: http.StatusOK,
		},
		{
			name:           "API Request 3 (Rate Limited)",
			path:           "/api",
			clientID:       "client1",
			expectedStatus: http.StatusTooManyRequests,
		},
		{
			name:           "Another Client (Success)",
			path:           "/api",
			clientID:       "client2",
			expectedStatus: http.StatusOK,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", tc.path, nil)
			ctx := context.WithValue(req.Context(), clientIDKey, tc.clientID)
			req = req.WithContext(ctx)

			rr := httptest.NewRecorder()
			handler.ServeHTTP(rr, req)

			if status := rr.Code; status != tc.expectedStatus {
				t.Errorf("handler returned wrong status code for %s: got %v want %v",
					tc.name, status, tc.expectedStatus)
			}
		})
	}
}
