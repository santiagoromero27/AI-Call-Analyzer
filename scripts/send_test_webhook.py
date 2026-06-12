#!/usr/bin/env python3
"""POST a sample Moja webhook payload to the local server.

Usage:
  python scripts/send_test_webhook.py
  python scripts/send_test_webhook.py --url http://localhost:8000/webhooks/moja \
      --secret changeme \
      --recording-url https://example.com/call.mp3 \
      --publisher facebook_leads \
      --buyer default
"""
import argparse
import json

import requests

DEFAULT_URL = "http://localhost:8000/webhooks/moja"
DEFAULT_SECRET = "changeme"

# Replace recording_url with any publicly accessible audio file for a real test.
SAMPLE_PAYLOAD = {
    "call_id": "test_001",
    "recording_url": "https://www2.cs.uic.edu/~i101/SoundFiles/BabyElephantWalk60.wav",
    "publisher": "test_publisher",
    "buyer": "default",
    "duration": 60,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a test Moja webhook")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--secret", default=DEFAULT_SECRET)
    parser.add_argument("--recording-url", default=None, help="Override recording_url")
    parser.add_argument("--publisher", default=None)
    parser.add_argument("--buyer", default=None)
    parser.add_argument("--call-id", default=None)
    args = parser.parse_args()

    payload = dict(SAMPLE_PAYLOAD)
    if args.recording_url:
        payload["recording_url"] = args.recording_url
    if args.publisher:
        payload["publisher"] = args.publisher
    if args.buyer:
        payload["buyer"] = args.buyer
    if args.call_id:
        payload["call_id"] = args.call_id

    headers = {
        "X-Webhook-Secret": args.secret,
        "Content-Type": "application/json",
    }

    print(f"→ POST {args.url}")
    print(f"  Payload: {json.dumps(payload, indent=2)}")

    resp = requests.post(args.url, json=payload, headers=headers, timeout=10)
    print(f"\n← {resp.status_code}  {resp.text}")


if __name__ == "__main__":
    main()
