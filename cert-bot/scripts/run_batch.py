"""
Usage:
  Batch from local PDFs:
    python scripts/run_batch.py --dir tests/fixtures/

  Batch from Avalara API:
    python scripts/run_batch.py --avalara --limit 100

  Batch from Avalara for specific customer:
    python scripts/run_batch.py --avalara --customer "ABC Fleet Services"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.output import generate_summary_line, generate_validation_json  # noqa: E402
from src.pipeline import validate_certificate  # noqa: E402
from src.report import generate_csv_export, generate_portfolio_report  # noqa: E402


def _write_portfolio_artifacts(results, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    report_path = output_dir / f"report_{timestamp}.md"
    report_path.write_text(generate_portfolio_report(results), encoding="utf-8")

    csv_path = output_dir / f"report_{timestamp}.csv"
    csv_path.write_text(generate_csv_export(results), encoding="utf-8")

    print(f"\nSaved portfolio report: {report_path}")
    print(f"Saved CSV export: {csv_path}")


def run_batch_local(directory: str, limit: int = None, output_dir: str = "output", state: str = None):
    """Process all PDFs in a directory and generate portfolio report outputs."""
    directory_path = Path(directory)
    if not directory_path.exists() or not directory_path.is_dir():
        raise SystemExit(f"Directory not found: {directory}")

    pdfs = sorted(directory_path.glob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(pdfs)
    for idx, pdf in enumerate(pdfs, start=1):
        print(f"Processing {idx}/{total}: {pdf.name}...")
        result = validate_certificate(str(pdf), state=state)
        if result.cert_id is None:
            result.cert_id = pdf.stem
        results.append(result)

        json_output = output_path / f"{pdf.stem}.json"
        json_output.write_text(generate_validation_json(result), encoding="utf-8")
        print(generate_summary_line(result))

    _write_portfolio_artifacts(results, output_path)


def _load_avalara_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "avalara_config.json"
    if not config_path.exists():
        raise SystemExit("Missing config/avalara_config.json. Create and populate Avalara credentials first.")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    for key in ["company_id", "username", "password"]:
        if not payload.get(key):
            raise SystemExit(f"Avalara config missing '{key}'.")
    return payload


def run_batch_avalara(
    limit: int = None,
    customer: str = None,
    output_dir: str = "output",
    state: str = None,
):
    """Pull certs from Avalara API, validate them, and emit report artifacts."""
    from src.avalara import AvalaraClient

    cfg = _load_avalara_config()
    client = AvalaraClient(cfg["username"], cfg["password"], int(cfg["company_id"]))

    certs = client.list_all_certificates(batch_size=100)
    if customer:
        customer_lower = customer.lower()
        certs = [
            cert
            for cert in certs
            if customer_lower in str(cert.get("customerName", "")).lower()
            or customer_lower in str(cert.get("customerCode", "")).lower()
        ]
    if limit:
        certs = certs[:limit]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = []
    with tempfile.TemporaryDirectory(prefix="certbot-avalara-") as temp_dir:
        for idx, cert in enumerate(certs, start=1):
            cert_id = cert.get("id")
            if cert_id is None:
                continue
            print(f"Processing {idx}/{len(certs)}: Avalara certificate {cert_id}...")

            temp_pdf = Path(temp_dir) / f"avalara_{cert_id}.pdf"
            client.download_certificate_pdf(int(cert_id), str(temp_pdf))

            result = validate_certificate(str(temp_pdf), state=state)
            result.avalara_cert_id = int(cert_id)
            result.cert_id = str(cert_id)
            if not result.customer_name or result.customer_name.lower() == "unknown":
                result.customer_name = cert.get("customerName") or cert.get("customerCode") or "Unknown"
            results.append(result)

            json_output = output_path / f"avalara_{cert_id}.json"
            json_output.write_text(generate_validation_json(result), encoding="utf-8")
            print(generate_summary_line(result))

    _write_portfolio_artifacts(results, output_path)


def main():
    parser = argparse.ArgumentParser(description="Batch certificate validation")
    parser.add_argument("--dir", dest="directory", help="Process all PDFs in directory")
    parser.add_argument("--avalara", action="store_true", help="Pull certs from Avalara API")
    parser.add_argument("--limit", type=int, default=None, help="Max certs to process")
    parser.add_argument("--customer", help="Filter by customer name")
    parser.add_argument("--output", default="output", help="Output directory for results")
    parser.add_argument("--state", help="Override state for all certs")

    args = parser.parse_args()

    if args.avalara:
        run_batch_avalara(limit=args.limit, customer=args.customer, output_dir=args.output, state=args.state)
        return

    if args.directory:
        run_batch_local(args.directory, limit=args.limit, output_dir=args.output, state=args.state)
        return

    raise SystemExit("Provide either --dir PATH or --avalara")


if __name__ == "__main__":
    main()
