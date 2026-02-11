from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import ValidationResult  # noqa: E402
from src.report import generate_csv_export, generate_portfolio_report  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate portfolio report from output JSON files")
    parser.add_argument("--input", default="output", help="Directory containing result JSON files")
    parser.add_argument("--output", default="output", help="Directory to write report and CSV")
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        raise SystemExit(f"Input directory does not exist: {input_dir}")

    results = []
    for file_path in sorted(input_dir.glob("*.json")):
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        results.append(ValidationResult.model_validate(payload))

    if not results:
        raise SystemExit(f"No JSON result files found in {input_dir}")

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "portfolio_report.md"
    report_path.write_text(generate_portfolio_report(results), encoding="utf-8")

    csv_path = output_dir / "portfolio_report.csv"
    csv_path.write_text(generate_csv_export(results), encoding="utf-8")

    print(f"Saved markdown report: {report_path}")
    print(f"Saved CSV export: {csv_path}")


if __name__ == "__main__":
    main()
