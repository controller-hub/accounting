"""
Usage: python scripts/run_single.py path/to/cert.pdf

Extracts text from a certificate PDF and prints the results.
"""
import os
import sys

# Add project root to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ingest import extract_certificate


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_single.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    result = extract_certificate(pdf_path)

    print(f"\n{'=' * 60}")
    print("Certificate Extraction Results")
    print(f"{'=' * 60}")
    print(f"File: {pdf_path}")
    print(f"Extraction confidence: {result.extraction_confidence}")
    print(f"Signature detected: {result.signature_present}")
    print(f"Text length: {len(result.raw_text or '')} chars")
    print("\n--- Extracted Text (first 500 chars) ---")
    print((result.raw_text or "")[:500])
    print(f"\n{'=' * 60}")


if __name__ == "__main__":
    main()
