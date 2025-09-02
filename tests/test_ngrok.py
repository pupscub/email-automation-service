#!/usr/bin/env python3
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_ngrok_connectivity(ngrok_url: str) -> bool:
    try:
        r = requests.get(f"{ngrok_url}/webhook", timeout=10)
        logger.info(f"Ngrok webhook GET: {r.status_code}")
        tok = "ngrok-test-12345"
        r = requests.get(f"{ngrok_url}/webhook?validationToken={tok}", timeout=10)
        logger.info(f"Ngrok validation: {r.status_code} body={r.text}")
        return r.status_code == 200 and r.text == tok
    except requests.exceptions.RequestException as e:
        logger.exception(f"Ngrok connectivity failed: {e}")
        return False


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        logger.error("Usage: python -m tests.test_ngrok <https-url>")
        sys.exit(1)
    ok = test_ngrok_connectivity(sys.argv[1])
    logger.info(f"Ngrok test passed: {ok}")


