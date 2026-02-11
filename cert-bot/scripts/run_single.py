"""
Usage: python scripts/run_single.py <pdf_path> [--state XX] [--save] [--email] [--review]

Runs full validation pipeline on a single certificate.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.output import (  # noqa: E402
    generate_correction_email,
    generate_review_request,
    generate_summary_line,
    generate_validation_json,
)
from src.pipeline import validate_certificate  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a single certificate PDF")
    parser.add_argument("pdf_path", help="Path to certificate PDF")
    parser.add_argument("--state", help="Override state code")
    parser.add_argument("--save", action="store_true", help="Save result JSON to output/")
    parser.add_argument("--email", action="store_true", help="Save correction email draft to output/")
    parser.add_argument("--review", action="store_true", help="Save human review request to output/")
    args = parser.parse_args()

    result = validate_certificate(args.pdf_path, state=args.state)

    print(generate_summary_line(result))
    print()
    result_json = generate_validation_json(result)
    print(result_json)

    output_dir = Path("output")
    if args.save or args.email or args.review:
        output_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(args.pdf_path).stem
    if args.save:
        json_path = output_dir / f"{stem}.json"
        json_path.write_text(result_json, encoding="utf-8")
        print(f"\nSaved validation JSON: {json_path}")

    if result.correction_email_needed:
        email_text = generate_correction_email(result)
        print("\n--- CORRECTION EMAIL DRAFT ---")
        print(email_text)
        if args.email:
            email_path = output_dir / f"{stem}_correction_email.txt"
            email_path.write_text(email_text, encoding="utf-8")
            print(f"Saved correction email: {email_path}")

    if result.human_review_needed:
        review_text = generate_review_request(result)
        print("\n--- HUMAN REVIEW REQUEST ---")
        print(review_text)
        if args.review:
            review_path = output_dir / f"{stem}_review_request.txt"
            review_path.write_text(review_text, encoding="utf-8")
            print(f"Saved review request: {review_path}")


if __name__ == "__main__":
    main()
