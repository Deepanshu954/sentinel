import os
import time
import base64
import json
import hmac
import hashlib

# Fallback basic secret if dotenv isn't present
secret = os.getenv("JWT_SECRET", "sentinel-super-secret-jwt-key-change-in-prod")
now = int(time.time())

# Raw Base64Url Implementation of JWT to guarantee execution without PyJWT pip requirements
header = {"alg": "HS256", "typ": "JWT"}
payload = {
    "sub": "demo-user",
    "client_id": "demo-client",
    "iat": now,
    "exp": now + 86400  # 24 hours
}

def base64url_encode(data):
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

header_b64 = base64url_encode(json.dumps(header).encode('utf-8'))
payload_b64 = base64url_encode(json.dumps(payload).encode('utf-8'))

# Create signature using HMAC-SHA256
signature = hmac.new(secret.encode('utf-8'), f"{header_b64}.{payload_b64}".encode('utf-8'), hashlib.sha256).digest()
signature_b64 = base64url_encode(signature)

token = f"{header_b64}.{payload_b64}.{signature_b64}"
print(token)
