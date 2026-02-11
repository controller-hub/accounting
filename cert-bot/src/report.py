from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from .models import Disposition, ValidationResult
from .validate import find_duplicates


def _pct(part: int, whole: int) -> str:
    if whole == 0:
        return "0.0%"
    return f"{(part / whole) * 100:.1f}%"


def _disposition_label(disposition: Disposition) -> str:
    return {
        Disposition.VALIDATED: "✅ Validated",
        Disposition.VALIDATED_WITH_NOTES: "✅⚠️ Validated with Notes",
        Disposition.NEEDS_CORRECTION: "❌ Needs Correction",
        Disposition.NEEDS_HUMAN_REVIEW: "🔍 Needs Human Review",
    }[disposition]


def generate_portfolio_report(results: list[ValidationResult]) -> str:
    """Generate a comprehensive markdown portfolio summary report."""
    total = len(results)
    dispositions = Counter(r.disposition for r in results)
    validated_total = dispositions[Disposition.VALIDATED] + dispositions[Disposition.VALIDATED_WITH_NOTES]

    lines: list[str] = []
    lines.append(f"# Portfolio Validation Report ({datetime.utcnow().date().isoformat()})")
    lines.append("")

    lines.append("## 1. EXECUTIVE SUMMARY")
    lines.append("")
    lines.append(f"- Total certs processed: **{total}**")
    lines.append(
        f"- Overall portfolio health (validated incl. notes): **{_pct(validated_total, total)}**"
    )
    lines.append("- Disposition counts:")
    for disposition in Disposition:
        count = dispositions[disposition]
        lines.append(f"  - {_disposition_label(disposition)}: {count} ({_pct(count, total)})")
    lines.append("")

    lines.append("## 2. DISPOSITION BREAKDOWN")
    lines.append("")
    lines.append("| Disposition | Count | % |")
    lines.append("|---|---:|---:|")
    for disposition in Disposition:
        count = dispositions[disposition]
        lines.append(f"| {_disposition_label(disposition)} | {count} | {_pct(count, total)} |")
    lines.append("")

    issue_counter: Counter[str] = Counter()
    issue_examples: dict[str, str] = {}
    for result in results:
        for check in result.checks:
            if check.passed:
                continue
            issue_counter[check.message] += 1
            issue_examples.setdefault(check.message, result.customer_name)

    lines.append("## 3. TOP ISSUES (by frequency)")
    lines.append("")
    lines.append("| Issue | Count | Example |")
    lines.append("|---|---:|---|")
    for message, count in issue_counter.most_common(10):
        lines.append(f"| {message} | {count} | {issue_examples.get(message, '')} |")
    if not issue_counter:
        lines.append("| None | 0 | - |")
    lines.append("")

    soon = date.today() + timedelta(days=90)
    lines.append("## 4. EXPIRATION ALERTS")
    lines.append("")
    lines.append("| Customer | State | Expires | Form | Action |")
    lines.append("|---|---|---|---|---|")
    expiring = sorted(
        [r for r in results if r.expiration_date and date.today() <= r.expiration_date <= soon],
        key=lambda r: r.expiration_date,
    )
    for result in expiring:
        action = result.renewal_action or "Queue renewal"
        lines.append(
            f"| {result.customer_name} | {result.state} | {result.expiration_date} | {result.form_type.value} | {action} |"
        )
    if not expiring:
        lines.append("| None | - | - | - | - |")
    lines.append("")

    duplicates = find_duplicates([r.model_dump(mode="json") for r in results])
    by_id = {str(r.cert_id): r for r in results if r.cert_id is not None}
    lines.append("## 5. DUPLICATE CANDIDATES")
    lines.append("")
    lines.append("| Customer | State | Cert 1 Date | Cert 2 Date | Recommendation |")
    lines.append("|---|---|---|---|---|")
    for cert1, cert2 in duplicates:
        r1 = by_id.get(str(cert1))
        r2 = by_id.get(str(cert2))
        customer = (r1 or r2).customer_name if (r1 or r2) else cert1
        state = (r1 or r2).state if (r1 or r2) else "UNKNOWN"
        d1 = str(r1.validated_at.date()) if r1 else "-"
        d2 = str(r2.validated_at.date()) if r2 else "-"
        lines.append(f"| {customer} | {state} | {d1} | {d2} | Keep older cert; archive duplicate. |")
    if not duplicates:
        lines.append("| None | - | - | - | - |")
    lines.append("")

    lines.append("## 6. STATE BREAKDOWN")
    lines.append("")
    lines.append("| State | Total | Valid | Corrections | Review | Health |")
    lines.append("|---|---:|---:|---:|---:|---|")
    by_state: dict[str, list[ValidationResult]] = defaultdict(list)
    for result in results:
        by_state[result.state].append(result)
    for state_key in sorted(by_state):
        state_results = by_state[state_key]
        state_total = len(state_results)
        valid = sum(
            1
            for r in state_results
            if r.disposition in {Disposition.VALIDATED, Disposition.VALIDATED_WITH_NOTES}
        )
        corrections = sum(1 for r in state_results if r.disposition == Disposition.NEEDS_CORRECTION)
        review = sum(1 for r in state_results if r.disposition == Disposition.NEEDS_HUMAN_REVIEW)
        health_pct = (valid / state_total * 100) if state_total else 0
        icon = "🟢" if health_pct >= 85 else "🟡" if health_pct >= 65 else "🔴"
        lines.append(
            f"| {state_key} | {state_total} | {valid} | {corrections} | {review} | {icon} {health_pct:.0f}% |"
        )
    if not by_state:
        lines.append("| N/A | 0 | 0 | 0 | 0 | 🔴 0% |")
    lines.append("")

    lines.append("## 7. ENTITY TYPE BREAKDOWN")
    lines.append("")
    lines.append("| Entity Type | Count | Valid % |")
    lines.append("|---|---:|---:|")
    by_entity: dict[str, list[ValidationResult]] = defaultdict(list)
    for result in results:
        by_entity[result.entity_type.value].append(result)
    for entity, entity_results in sorted(by_entity.items()):
        count = len(entity_results)
        valid = sum(
            1
            for r in entity_results
            if r.disposition in {Disposition.VALIDATED, Disposition.VALIDATED_WITH_NOTES}
        )
        lines.append(f"| {entity} | {count} | {_pct(valid, count)} |")
    if not by_entity:
        lines.append("| N/A | 0 | 0.0% |")
    lines.append("")

    lines.append("## 8. CUSTOMERS WITH ZERO VALID COVERAGE")
    lines.append("")
    by_customer: dict[str, list[ValidationResult]] = defaultdict(list)
    for result in results:
        by_customer[result.customer_name].append(result)
    zero_valid = []
    for customer, customer_results in by_customer.items():
        any_valid = any(
            r.disposition in {Disposition.VALIDATED, Disposition.VALIDATED_WITH_NOTES}
            for r in customer_results
        )
        if not any_valid:
            zero_valid.append(customer)
    for customer in sorted(zero_valid):
        lines.append(f"- {customer}")
    if not zero_valid:
        lines.append("- None")
    lines.append("")

    lines.append("## 9. RECOMMENDATIONS")
    lines.append("")
    lines.append("- Prioritize high-frequency correction items from the Top Issues table.")
    lines.append("- Launch renewal outreach for all certificates in the 90-day expiration window.")
    lines.append("- Review duplicate candidates and archive newer redundant records.")

    return "\n".join(lines)


def generate_csv_export(results: list[ValidationResult]) -> str:
    """Generate a CSV export of all results for spreadsheet analysis."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "cert_id",
            "customer_name",
            "state",
            "form_type",
            "entity_type",
            "disposition",
            "confidence_score",
            "expiration_date",
            "correction_needed",
            "human_review_needed",
            "hard_fail_count",
            "soft_flag_count",
            "notes",
        ]
    )

    for result in results:
        notes = " | ".join(flag.message for flag in result.soft_flags)
        writer.writerow(
            [
                result.cert_id or "",
                result.customer_name,
                result.state,
                result.form_type.value,
                result.entity_type.value,
                result.disposition.value,
                result.confidence_score,
                result.expiration_date.isoformat() if result.expiration_date else "",
                str(result.correction_email_needed).lower(),
                str(result.human_review_needed).lower(),
                len(result.hard_fails),
                len(result.soft_flags),
                notes,
            ]
        )

    return output.getvalue()
