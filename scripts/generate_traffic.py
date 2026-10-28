import argparse
import itertools
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class TrafficRequest:
    method: str
    path: str
    payload: dict | None = None


def build_requests(run_id: str, sequence: int) -> tuple[TrafficRequest, ...]:
    return (
        TrafficRequest("GET", "/"),
        TrafficRequest("GET", "/items/"),
        TrafficRequest(
            "POST",
            "/items/",
            {
                "name": f"traffic-{run_id}-{sequence}",
                "description": "Item de teste gerado para validar métricas.",
            },
        ),
        TrafficRequest("POST", "/items/", {"name": None}),
        TrafficRequest("GET", "/__traffic_test_not_found__"),
    )


def send_request(base_url: str, request: TrafficRequest) -> tuple[int | None, str | None]:
    try:
        response = requests.request(
            request.method,
            f"{base_url}{request.path}",
            json=request.payload,
            timeout=10,
        )
        return response.status_code, None
    except requests.RequestException as error:
        return None, str(error)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera tráfego limitado para popular métricas HTTP do app_v2."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="URL publicada da API (padrão: http://localhost:8001).",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=180,
        help="Duração máxima do teste em segundos (padrão: 180).",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=1.0,
        help="Pausa entre lotes concorrentes (padrão: 1.0).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Requisições concorrentes por lote (padrão: 4).",
    )
    args = parser.parse_args()
    if args.duration_seconds <= 0 or args.interval_seconds < 0 or args.workers <= 0:
        parser.error("duration-seconds e workers devem ser positivos; interval-seconds não pode ser negativo.")
    args.base_url = args.base_url.rstrip("/")
    return args


def main() -> int:
    args = parse_args()
    run_id = uuid.uuid4().hex[:8]
    request_sequence = itertools.count(1)
    operation_sequence = itertools.cycle(build_requests(run_id, 0))
    result_counts: Counter[str] = Counter()
    deadline = time.monotonic() + args.duration_seconds

    print(
        f"Gerando tráfego para {args.base_url} por até {args.duration_seconds}s "
        f"com {args.workers} workers. Pressione Ctrl+C para parar."
    )

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            while time.monotonic() < deadline:
                batch = []
                for _ in range(args.workers):
                    operation = next(operation_sequence)
                    if operation.method == "POST" and operation.payload and operation.payload.get("name"):
                        sequence = next(request_sequence)
                        operation = TrafficRequest(
                            operation.method,
                            operation.path,
                            {
                                **operation.payload,
                                "name": f"traffic-{run_id}-{sequence}",
                            },
                        )
                    batch.append(executor.submit(send_request, args.base_url, operation))

                for future in batch:
                    status_code, error = future.result()
                    result_counts[str(status_code) if status_code is not None else "connection_error"] += 1
                    if error:
                        print(f"Request failed: {error}")
                    elif status_code is not None and status_code >= 500:
                        print(f"Unexpected server response: HTTP {status_code}")

                remaining = deadline - time.monotonic()
                if remaining > 0:
                    time.sleep(min(args.interval_seconds, remaining))
    except KeyboardInterrupt:
        print("\nExecução interrompida pelo utilizador.")

    print(f"Resumo de status HTTP: {dict(result_counts)}")
    return 1 if result_counts["connection_error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
