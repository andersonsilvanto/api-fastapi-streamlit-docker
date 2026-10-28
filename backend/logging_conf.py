import json
import logging
import os
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

from opensearchpy import OpenSearch, helpers
from pythonjsonlogger import jsonlogger


LOG_FIELDS = (
    "timestamp",
    "level",
    "logger",
    "message",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "client_ip",
    "user_agent",
)


class StructuredJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["message"] = record.getMessage()
        for field in LOG_FIELDS:
            if field not in log_record:
                log_record[field] = getattr(record, field, None)


class OpenSearchHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self._index = os.getenv("OPENSEARCH_INDEX", "logs-app-v2")
        self._host = os.getenv("OPENSEARCH_HOST", "opensearch")
        self._port = int(os.getenv("OPENSEARCH_PORT", "9200"))
        self._scheme = os.getenv("OPENSEARCH_SCHEME", "http").lower()
        self._username = os.getenv("OPENSEARCH_USER", "")
        self._password = os.getenv("OPENSEARCH_PASSWORD", "")
        self._records: queue.Queue[str] = queue.Queue(maxsize=5000)
        self._thread = threading.Thread(
            target=self._send_records,
            name="opensearch-log-sender",
            daemon=True,
        )
        self._thread.start()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._records.put_nowait(self.format(record))
        except queue.Full:
            self._write_fallback(self.format(record))
        except Exception:
            self.handleError(record)

    @staticmethod
    def _write_fallback(serialized_record: str) -> None:
        sys.stdout.write(serialized_record + "\n")
        sys.stdout.flush()

    def _create_client(self) -> OpenSearch:
        options: dict[str, Any] = {
            "hosts": [{"host": self._host, "port": self._port}],
            "use_ssl": self._scheme == "https",
            "verify_certs": self._scheme == "https",
            "timeout": 3,
            "max_retries": 0,
        }
        if self._username and self._password:
            options["http_auth"] = (self._username, self._password)
        return OpenSearch(**options)

    def _send_batch(self, client: OpenSearch, records: list[str]) -> None:
        actions = [
            {"_index": self._index, "_source": json.loads(serialized)}
            for serialized in records
        ]
        for attempt in range(3):
            try:
                helpers.bulk(client, actions, request_timeout=5)
                return
            except Exception:
                if attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
        for serialized in records:
            self._write_fallback(serialized)

    def _send_records(self) -> None:
        client = self._create_client()
        while True:
            try:
                first_record = self._records.get(timeout=1)
            except queue.Empty:
                continue

            batch = [first_record]
            while len(batch) < 100:
                try:
                    batch.append(self._records.get_nowait())
                except queue.Empty:
                    break

            try:
                self._send_batch(client, batch)
            except Exception:
                for serialized in batch:
                    self._write_fallback(serialized)
            finally:
                for _ in batch:
                    self._records.task_done()


def setup_logging() -> None:
    formatter = StructuredJsonFormatter()
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(stream_handler)

    loggers = (
        "uvicorn",
        "uvicorn.access",
        "fastapi",
        "sqlalchemy.engine",
        "opensearch",
        "urllib3",
    )
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(logging.WARNING if logger_name == "sqlalchemy.engine" else logging.INFO)

    logging.getLogger("opensearch").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    if os.getenv("OPENSEARCH_ENABLED", "false").strip().lower() in {"1", "true", "yes"}:
        opensearch_handler = OpenSearchHandler()
        opensearch_handler.setFormatter(formatter)
        root_logger.addHandler(opensearch_handler)
