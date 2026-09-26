"""
Grafana Loki Log Handler.
Transports application logs directly to Loki (:3100) via standard HTTP push API.
"""
import os
import time
import threading
import logging
import httpx

logger = logging.getLogger(__name__)


class LokiHandler(logging.Handler):
    """Asynchronous logging handler that pushes log records to Grafana Loki."""

    def __init__(self, loki_url: str = None, service_name: str = "alphatracer-api"):
        super().__init__()
        self.loki_url = loki_url or os.getenv(
            "LOKI_URL", "http://loki:3100/loki/api/v1/push"
        )
        self.service_name = service_name
        self.enabled = os.getenv("ENABLE_LOKI", "true").lower() in ("true", "1")

    def emit(self, record):
        if not self.enabled:
            return

        try:
            log_entry = self.format(record)
            timestamp_ns = str(int(time.time() * 1e9))
            payload = {
                "streams": [
                    {
                        "stream": {
                            "service": self.service_name,
                            "level": record.levelname.lower(),
                        },
                        "values": [[timestamp_ns, log_entry]],
                    }
                ]
            }
            # Dispatch to background thread to ensure zero latency overhead on HTTP requests
            threading.Thread(
                target=self._push_to_loki, args=(payload,), daemon=True
            ).start()
        except Exception:
            self.handleError(record)

    def _push_to_loki(self, payload):
        try:
            httpx.post(self.loki_url, json=payload, timeout=2.0)
        except Exception:
            pass  # Non-blocking for application reliability if Loki is offline


def setup_loki_logging(service_name: str = "alphatracer-api"):
    """Attaches LokiHandler to root logger for centralized log streaming."""
    loki_url = os.getenv("LOKI_URL", "http://loki:3100/loki/api/v1/push")
    handler = LokiHandler(loki_url=loki_url, service_name=service_name)
    formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
    )
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)
    logger.info(f"Loki log forwarding attached -> {loki_url}")
