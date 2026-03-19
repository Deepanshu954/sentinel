#!/usr/bin/env python3
"""
Generate a signed JWT for Sentinel gateway testing.

Usage:
    python scripts/generate_jwt.py                         # default client_id = "test-user"
    python scripts/generate_jwt.py --client-id user-abc    # custom client_id
    python scripts/generate_jwt.py --expired               # generate an already-expired token

Reads JWT_SECRET from .env file or falls back to the default dev secret.
"""

import argparse
import json
import hmac
import hashlib
import base64
import time
import os
import re


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _load_secret() -> str:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                match = re.match(r"^JWT_SECRET=(.+)$", line.strip())
                if match:
                    return match.group(1)
    # Fallback to the default dev secret from .env.example
    return "sentinel-super-secret-jwt-key-change-in-prod"


def generate_jwt(client_id: str, secret: str, expired: bool = False) -> str:
    header = {"alg": "HS256", "typ": "JWT"}

    now = int(time.time())
    payload = {
        "client_id": client_id,
        "iat": now,
        "exp": now - 3600 if expired else now + 86400,  # expired: 1h ago, valid: 24h from now
        "iss": "sentinel-dev",
    }

    segments = [
        _b64url(json.dumps(header, separators=(",", ":")).encode()),
        _b64url(json.dumps(payload, separators=(",", ":")).encode()),
    ]

    signing_input = f"{segments[0]}.{segments[1]}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64url(signature))

    return ".".join(segments)


def main():
    parser = argparse.ArgumentParser(description="Generate JWT for Sentinel gateway testing")
    parser.add_argument("--client-id", default="test-user", help="client_id claim (default: test-user)")
    parser.add_argument("--expired", action="store_true", help="generate an already-expired token")
    args = parser.parse_args()

    secret = _load_secret()
    token = generate_jwt(args.client_id, secret, args.expired)

    print(f"\n{'EXPIRED ' if args.expired else ''}JWT for client_id={args.client_id!r}:\n")
    print(token)
    print(f"\nCurl header:\n  -H 'Authorization: Bearer {token}'\n")


if __name__ == "__main__":
    main()
