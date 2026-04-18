from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.analysis.providers import list_analyzer_providers, select_best_provider


@dataclass
class BenchmarkRow:
    path: str
    provider: str
    runtime_ms: float
    status: str


def benchmark_paths(
    paths: Iterable[str],
    provider_name: Optional[str] = None,
) -> Dict[str, Any]:
    rows: List[BenchmarkRow] = []
    available = {k: asdict(v) for k, v in list_analyzer_providers().items()}

    provider = select_best_provider(provider_name)

    for raw_path in paths:
        path = str(Path(raw_path))
        started = time.perf_counter()
        result = provider.analyze(path)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        rows.append(
            BenchmarkRow(
                path=path,
                provider=result.get("provider", provider.name),
                runtime_ms=elapsed_ms,
                status=result.get("status", "unknown"),
            )
        )

    return {
        "provider_selected": provider.name,
        "providers": available,
        "rows": [asdict(r) for r in rows],
        "summary": {
            "count": len(rows),
            "avg_runtime_ms": round(sum(r.runtime_ms for r in rows) / len(rows), 3) if rows else 0.0,
        },
    }


def benchmark_to_json(
    paths: Iterable[str],
    provider_name: Optional[str] = None,
) -> str:
    return json.dumps(benchmark_paths(paths, provider_name=provider_name), indent=2, ensure_ascii=False)
