package middleware

import (
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

func TestAuthMiddleware(t *testing.T) {
	secret := "test-secret"
	os.Setenv("JWT_SECRET", secret)
	defer os.Unsetenv("JWT_SECRET")

	// Helper to generate token
	generateToken := func(clientID string, expired bool) string {
		claims := jwt.MapClaims{
			"client_id": clientID,
		}
		if expired {
			claims["exp"] = time.Now().Add(-time.Hour).Unix()
		} else {
			claims["exp"] = time.Now().Add(time.Hour).Unix()
		}

		token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
		str, _ := token.SignedString([]byte(secret))
		return str
	}

	tests := []struct {
		name           string
		path           string
		authHeader     string
		expectedStatus int
		expectedClient string
	}{
		{
			name:           "Health Check Bypass",
			path:           "/health",
			authHeader:     "",
			expectedStatus: http.StatusOK,
			expectedClient: "anonymous",
		},
		{
			name:           "Metrics Bypass",
			path:           "/metrics",
			authHeader:     "",
			expectedStatus: http.StatusOK,
			expectedClient: "anonymous",
		},
		{
			name:           "Missing Header",
			path:           "/api",
			authHeader:     "",
			expectedStatus: http.StatusUnauthorized,
			expectedClient: "anonymous",
		},
		{
			name:           "Invalid Format",
			path:           "/api",
			authHeader:     "Basic dXNlcm5hbWU6cGFzc3dvcmQ=",
			expectedStatus: http.StatusUnauthorized,
			expectedClient: "anonymous",
		},
		{
			name:           "Invalid Signature",
			path:           "/api",
			authHeader:     "Bearer invalid.token.string",
			expectedStatus: http.StatusUnauthorized,
			expectedClient: "anonymous",
		},
		{
			name:           "Expired Token",
			path:           "/api",
			authHeader:     "Bearer " + generateToken("client123", true),
			expectedStatus: http.StatusUnauthorized,
			expectedClient: "anonymous",
		},
		{
			name:           "Valid Token",
			path:           "/api",
			authHeader:     "Bearer " + generateToken("client123", false),
			expectedStatus: http.StatusOK,
			expectedClient: "client123",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			req := httptest.NewRequest("GET", tc.path, nil)
			if tc.authHeader != "" {
				req.Header.Set("Authorization", tc.authHeader)
			}
			rr := httptest.NewRecorder()

			nextHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				clientID := ClientIDFromContext(r.Context())
				if clientID != tc.expectedClient {
					t.Errorf("expected clientID %s, got %s", tc.expectedClient, clientID)
				}
				w.WriteHeader(http.StatusOK)
			})

			handler := AuthMiddleware(nextHandler)
			handler.ServeHTTP(rr, req)

			if status := rr.Code; status != tc.expectedStatus {
				t.Errorf("handler returned wrong status code: got %v want %v",
					status, tc.expectedStatus)
			}
		})
	}
}
