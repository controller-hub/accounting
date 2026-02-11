"""
Usage: python scripts/run_single.py <pdf_path> [--state XX]

Runs full validation pipeline on a single certificate.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.output import (  # noqa: E402
    generate_correction_email,
    generate_review_request,
    generate_summary_line,
    generate_validation_json,
)
from src.pipeline import validate_certificate  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/run_single.py <pdf_path> [--state XX]")

    pdf_path = sys.argv[1]
    state = None
    if "--state" in sys.argv:
        idx = sys.argv.index("--state")
        if idx + 1 >= len(sys.argv):
            raise SystemExit("--state provided without value")
        state = sys.argv[idx + 1]

    result = validate_certificate(pdf_path, state=state)

    print(generate_summary_line(result))
    print()
    print(generate_validation_json(result))

    if result.correction_email_needed:
        print("\n--- CORRECTION EMAIL DRAFT ---")
        print(generate_correction_email(result))

    if result.human_review_needed:
        print("\n--- HUMAN REVIEW REQUEST ---")
        print(generate_review_request(result))


if __name__ == "__main__":
    main()
