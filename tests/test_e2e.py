#!/usr/bin/env python3
import logging
import subprocess
import time
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def start_ngrok() -> tuple[subprocess.Popen, str | None]:
    proc = subprocess.Popen(["ngrok", "http", "8000"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3)
    try:
        r = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5)
        for t in r.json().get("tunnels", []):
            if t.get("proto") == "https":
                return proc, t.get("public_url")
    except Exception:
        pass
    return proc, None


def run_e2e(base_url: str = "http://localhost:8000") -> bool:
    logger.info("Starting E2E test...")
    proc, public_url = start_ngrok()
    if not public_url:
        logger.error("No ngrok https public URL found")
        proc.terminate()
        return False
    logger.info(f"ngrok URL: {public_url}")

    try:
        # Start monitoring with URL
        r = requests.post(f"{base_url}/webhook/start_with_url", json={"webhook_url": public_url}, timeout=20)
        logger.info(f"start_with_url: {r.status_code} {r.text}")
        # Send test email to self
        r = requests.post(f"{base_url}/debug/send_test_email", json={"subject": "E2E Test", "body": "<p>E2E</p>"}, timeout=20)
        logger.info(f"send_test_email: {r.status_code} {r.text}")
        # Poll recent drafts
        for _ in range(12):
            time.sleep(5)
            rr = requests.get(f"{base_url}/ui/recent-drafts", timeout=10)
            items = rr.json().get("items", []) if rr.ok else []
            if items:
                logger.info("Draft detected. E2E success.")
                return True
        logger.error("E2E failed: No drafts within timeout")
        return False
    finally:
        proc.terminate()


if __name__ == "__main__":
    ok = run_e2e()
    logger.info(f"E2E result: {ok}")


