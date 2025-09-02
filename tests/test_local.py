#!/usr/bin/env python3
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_local_app(base_url: str = "http://localhost:8000") -> bool:
    try:
        r = requests.get(f"{base_url}/", timeout=5)
        logger.info(f"Root: {r.status_code}")
        r = requests.get(f"{base_url}/webhook", timeout=5)
        logger.info(f"Webhook GET: {r.status_code}")
        tok = "test-token-123"
        r = requests.get(f"{base_url}/webhook?validationToken={tok}", timeout=5)
        logger.info(f"Validation: {r.status_code} body={r.text}")
        r = requests.get(f"{base_url}/health", timeout=5)
        logger.info(f"Health: {r.status_code} {r.json() if r.ok else ''}")
        return True
    except requests.exceptions.RequestException as e:
        logger.exception(f"Local app test failed: {e}")
        return False


if __name__ == "__main__":
    ok = test_local_app()
    logger.info(f"Local test passed: {ok}")


