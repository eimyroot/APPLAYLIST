from __future__ import annotations

import argparse
from pathlib import Path

from core.analysis.benchmark import benchmark_to_json


def main() -> int:
    parser = argparse.ArgumentParser(description="APPLAYLIST analyzer provider benchmark")
    parser.add_argument("paths", nargs="+", help="Audio file paths")
    parser.add_argument("--provider", default=None, help="Preferred provider: librosa|essentia")
    parser.add_argument("--out", default=None, help="Optional output JSON path")
    args = parser.parse_args()

    payload = benchmark_to_json(args.paths, provider_name=args.provider)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(f"[ok] wrote {out_path}")
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
