# Cert Validation Bot

Automated tax exemption certificate validation for Fleetio.

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. (For OCR fallback) Install Tesseract: `sudo apt install tesseract-ocr`
3. (For Avalara) Populate `config/avalara_config.json` with credentials

## Usage

### Single Certificate
```bash
python scripts/run_single.py path/to/cert.pdf
python scripts/run_single.py cert.pdf --state TX
python scripts/run_single.py cert.pdf --save --email
```

### Batch (Local PDFs)
```bash
python scripts/run_batch.py --dir path/to/cert_pdfs/
python scripts/run_batch.py --dir certs/ --limit 50 --output results/
```

### Batch (Avalara API)
```bash
python scripts/run_batch.py --avalara --limit 100
python scripts/run_batch.py --avalara --customer "ABC Fleet"
```

### Portfolio Report
```bash
python scripts/generate_report.py --input output/ --output reports/
```

## Config Files

All state rules live in JSON config files under `config/`. Update these
when state rules change — no code changes required.

| File | Contents |
|---|---|
| `state_rules.json` | SaaS taxability, expiration rules, seller protection |
| `mtc_restrictions.json` | MTC resale-only state matrix |
| `reasonableness_rules.json` | SaaS exemption validity, resale tiers |
| `form_templates.json` | Form identification patterns |
| `avalara_config.json` | API credentials (DO NOT COMMIT) |

## Quarterly Rule Updates

1. Run the quarterly research prompt (see `perplexity-cert-bot-quarterly-review-prompt.md`)
2. Update the relevant JSON config file
3. Run tests: `pytest tests/`
4. No code changes needed for rule updates

## Dispositions

| Code | Meaning | Action |
|---|---|---|
| VALIDATED | All checks pass | Mark exempt |
| VALIDATED_WITH_NOTES | Passes with minor observations | Accept; note for record |
| NEEDS_CORRECTION | Specific issues found | Send correction email |
| NEEDS_HUMAN_REVIEW | Judgment call needed | Route to review queue |
