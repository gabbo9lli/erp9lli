import threading
import time
from typing import Dict, List, Tuple, Optional, Any

class Metric:
    def __init__(self, name: str, description: str, labels: Optional[List[str]] = None):
        self.name = name
        self.description = description
        self.labels = labels or []
        self._lock = threading.Lock()

    def _labels_to_key(self, labels: Dict[str, Any]) -> Tuple[Tuple[str, str], ...]:
        return tuple(sorted((k, str(v)) for k, v in labels.items() if k in self.labels))

    def _format_labels(self, key: Tuple[Tuple[str, str], ...]) -> str:
        if not key:
            return ""
        items = [f'{k}="{v}"' for k, v in key]
        return "{" + ",".join(items) + "}"

class Counter(Metric):
    def __init__(self, name: str, description: str, labels: Optional[List[str]] = None):
        super().__init__(name, description, labels)
        self._values: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def inc(self, amount: float = 1.0, **labels):
        key = self._labels_to_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def collect(self) -> List[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} counter"
        ]
        with self._lock:
            if not self._values:
                lines.append(f"{self.name} 0.0")
            else:
                for key, val in sorted(self._values.items()):
                    lines.append(f"{self.name}{self._format_labels(key)} {val}")
        return lines

class Gauge(Metric):
    def __init__(self, name: str, description: str, labels: Optional[List[str]] = None):
        super().__init__(name, description, labels)
        self._values: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def set(self, value: float, **labels):
        key = self._labels_to_key(labels)
        with self._lock:
            self._values[key] = float(value)

    def inc(self, amount: float = 1.0, **labels):
        key = self._labels_to_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def dec(self, amount: float = 1.0, **labels):
        key = self._labels_to_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) - amount

    def collect(self) -> List[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} gauge"
        ]
        with self._lock:
            if not self._values:
                lines.append(f"{self.name} 0.0")
            else:
                for key, val in sorted(self._values.items()):
                    lines.append(f"{self.name}{self._format_labels(key)} {val}")
        return lines

class Histogram(Metric):
    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def __init__(self, name: str, description: str, labels: Optional[List[str]] = None, buckets: Optional[Tuple[float, ...]] = None):
        super().__init__(name, description, labels)
        self.buckets = sorted(buckets or self.DEFAULT_BUCKETS)
        self._counts: Dict[Tuple[Tuple[str, str], ...], Dict[float, int]] = {}
        self._sums: Dict[Tuple[Tuple[str, str], ...], float] = {}
        self._totals: Dict[Tuple[Tuple[str, str], ...], int] = {}

    def observe(self, value: float, **labels):
        key = self._labels_to_key(labels)
        with self._lock:
            if key not in self._counts:
                self._counts[key] = {b: 0 for b in self.buckets}
                self._sums[key] = 0.0
                self._totals[key] = 0

            self._sums[key] += value
            self._totals[key] += 1
            for b in self.buckets:
                if value <= b:
                    self._counts[key][b] += 1

    def collect(self) -> List[str]:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} histogram"
        ]
        with self._lock:
            if not self._counts:
                lines.append(f"{self.name}_count 0")
                lines.append(f"{self.name}_sum 0.0")
            else:
                for key in sorted(self._counts.keys()):
                    base_labels = dict(key)
                    cum_count = 0
                    for b in self.buckets:
                        cum_count = self._counts[key][b]
                        b_labels = dict(base_labels)
                        b_labels["le"] = str(b)
                        lines.append(f"{self.name}_bucket{self._format_labels(tuple(sorted(b_labels.items())))} {cum_count}")
                    
                    inf_labels = dict(base_labels)
                    inf_labels["le"] = "+Inf"
                    lines.append(f"{self.name}_bucket{self._format_labels(tuple(sorted(inf_labels.items())))} {self._totals[key]}")
                    lines.append(f"{self.name}_count{self._format_labels(key)} {self._totals[key]}")
                    lines.append(f"{self.name}_sum{self._format_labels(key)} {round(self._sums[key], 6)}")
        return lines

class MetricsRegistry:
    def __init__(self):
        self._metrics: List[Metric] = []
        self._lock = threading.Lock()

    def register(self, metric: Metric) -> Metric:
        with self._lock:
            self._metrics.append(metric)
        return metric

    def generate_openmetrics_text(self) -> str:
        all_lines = []
        with self._lock:
            for m in self._metrics:
                all_lines.extend(m.collect())
                all_lines.append("")
        all_lines.append("# EOF\n")
        return "\n".join(all_lines)

registry = MetricsRegistry()

# Catalogo Metriche erp9lli
http_requests_total = registry.register(Counter(
    "erp9lli_http_requests_total",
    "Conteggio totale chiamate HTTP",
    labels=["method", "endpoint", "status"]
))

http_request_duration_seconds = registry.register(Histogram(
    "erp9lli_http_request_duration_seconds",
    "Latenza chiamate HTTP in secondi",
    labels=["method", "endpoint"]
))

http_requests_in_progress = registry.register(Gauge(
    "erp9lli_http_requests_in_progress",
    "Richieste attualmente in elaborazione",
    labels=["method", "endpoint"]
))

ws_connections_active = registry.register(Gauge(
    "erp9lli_websocket_active_connections",
    "Numero di client live collegati contemporaneamente su /ws"
))

ws_broadcast_total = registry.register(Counter(
    "erp9lli_websocket_broadcast_total",
    "Messaggi broadcast emessi su WebSocket",
    labels=["action"]
))

rq_queue_jobs_count = registry.register(Gauge(
    "erp9lli_rq_queue_jobs_count",
    "Numero di job in attesa nelle code Redis",
    labels=["queue"]
))

rq_failed_jobs_count = registry.register(Gauge(
    "erp9lli_rq_failed_jobs_count",
    "Numero di job falliti nelle code Redis",
    labels=["queue"]
))

orders_created_total = registry.register(Counter(
    "erp9lli_orders_created_total",
    "Totale ordini clienti inseriti"
))

invoices_created_total = registry.register(Counter(
    "erp9lli_invoices_created_total",
    "Totale fatture e note di credito emesse",
    labels=["tipo_documento"]
))

pos_sales_created_total = registry.register(Counter(
    "erp9lli_pos_sales_created_total",
    "Totale vendite al banco registrate",
    labels=["metodo_pagamento"]
))

migration_runs_total = registry.register(Counter(
    "erp9lli_migration_runs_total",
    "Esecuzioni del modulo di migrazione",
    labels=["status"]
))

def get_metrics_summary() -> dict:
    total_reqs = 0.0
    status_2xx = 0
    status_4xx = 0
    status_5xx = 0

    with http_requests_total._lock:
        for k, v in http_requests_total._values.items():
            total_reqs += v
            lbl_dict = dict(k)
            st = lbl_dict.get("status", "")
            if st.startswith("2"):
                status_2xx += int(v)
            elif st.startswith("4"):
                status_4xx += int(v)
            elif st.startswith("5"):
                status_5xx += int(v)

    total_duration_sec = 0.0
    total_samples = 0
    with http_request_duration_seconds._lock:
        for k, s in http_request_duration_seconds._sums.items():
            total_duration_sec += s
        for k, cnt in http_request_duration_seconds._totals.items():
            total_samples += cnt

    avg_latency_ms = round((total_duration_sec / max(1, total_samples)) * 1000, 2) if total_samples > 0 else 0.0
    success_rate = round((status_2xx / max(1, total_reqs)) * 100, 1) if total_reqs > 0 else 100.0

    active_ws = 0
    with ws_connections_active._lock:
        for v in ws_connections_active._values.values():
            active_ws = int(v)

    total_broadcasts = 0
    with ws_broadcast_total._lock:
        for v in ws_broadcast_total._values.values():
            total_broadcasts += int(v)

    total_orders = sum(orders_created_total._values.values()) if orders_created_total._values else 0
    total_invoices = sum(invoices_created_total._values.values()) if invoices_created_total._values else 0
    total_pos = sum(pos_sales_created_total._values.values()) if pos_sales_created_total._values else 0

    queues = {"critical": 0, "emails": 0, "reports": 0, "default": 0, "total_pending": 0, "total_failed": 0}
    try:
        from services.event_dispatcher import get_redis_connection
        r_conn = get_redis_connection()
        if r_conn:
            from rq import Queue
            for q_name in ["critical", "emails", "reports", "default"]:
                q = Queue(q_name, connection=r_conn)
                cnt = len(q)
                queues[q_name] = cnt
                queues["total_pending"] += cnt
    except Exception:
        pass

    return {
        "http": {
            "total_requests": int(total_reqs),
            "avg_latency_ms": avg_latency_ms,
            "success_rate_pct": success_rate,
            "status_2xx": status_2xx,
            "status_4xx": status_4xx,
            "status_5xx": status_5xx
        },
        "websockets": {
            "active_clients": active_ws,
            "total_broadcasts": total_broadcasts
        },
        "queues_rq": queues,
        "business_totals": {
            "orders": int(total_orders),
            "invoices": int(total_invoices),
            "pos_sales": int(total_pos)
        }
    }

