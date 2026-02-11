from __future__ import annotations

import json

from .models import Disposition, ValidationResult


def generate_validation_json(result: ValidationResult) -> str:
    return json.dumps(result.model_dump(mode="json"), indent=2, default=str)


def generate_correction_email(result: ValidationResult) -> str:
    items = "\n".join([f"☐ {item}" for item in result.correction_items])
    if not items:
        items = "☐ Please provide a corrected certificate with complete information."

    return f"""Subject: Action Required: Tax Exemption Certificate for {result.customer_name} — Fleetio

Hi,

Thank you for submitting your tax exemption certificate. We've reviewed it
and need the following to complete validation:

{items}

Please submit an updated certificate at your earliest convenience.
Until we receive valid documentation, sales tax will be applied
to your invoices per state requirements.

If you have questions about which form to use:
- Multi-state form (38 states): MTC Uniform Certificate — mtc.gov
- Streamlined form (24 states): SST Certificate of Exemption — streamlinedsalestax.org

Thank you,
Fleetio Finance Team"""


def generate_review_request(result: ValidationResult) -> str:
    reason_lines = "\n".join([f"- {flag.message}" for flag in result.reasonableness_flags])
    if not reason_lines:
        reason_lines = "- Manual review requested by workflow."

    sst_member = "yes" if "SST" in result.seller_protection_standard.value else "no"
    resale_text = ""
    if result.resale_tier is not None:
        resale_text = f"\nResale Tier Assessment: Tier {result.resale_tier.value} ({result.resale_tier.name})\n"

    completeness = "complete" if not result.hard_fails else "incomplete"

    return f"""Subject: [REVIEW NEEDED] Tax Exemption Certificate — {result.customer_name}

Customer: {result.customer_name}
State: {result.state} | SST Member: {sst_member}
Form Type: {result.form_type.value}
Exemption Claimed: {result.exemption_category.value if result.exemption_category else 'Unknown'}
Entity Type Detected: {result.entity_type.value}
Seller Protection Standard: {result.seller_protection_standard.value}

⚠️ Flagged because:
{reason_lines}
{resale_text}
Certificate is otherwise {completeness}.
Reviewer should determine if exemption claim is reasonable
for this customer's business.

Confidence Score: {result.confidence_score}%"""


def generate_summary_line(result: ValidationResult) -> str:
    emoji = {
        Disposition.VALIDATED: "✅",
        Disposition.VALIDATED_WITH_NOTES: "✅⚠️",
        Disposition.NEEDS_CORRECTION: "❌",
        Disposition.NEEDS_HUMAN_REVIEW: "🔍",
    }[result.disposition]
    return (
        f"{emoji} {result.customer_name} | {result.state} | {result.form_type.value} | "
        f"{result.disposition.value} | {result.confidence_score}%"
    )

