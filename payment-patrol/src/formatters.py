from __future__ import annotations

from datetime import date
from decimal import Decimal


def _money(value: str | Decimal) -> str:
    d = Decimal(str(value))
    return f"${d:,.2f}"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def build_cfo_blocks(cfo_summary: dict, run_date: date) -> list[dict]:
    return [
        {"type": "header", "text": {"type": "plain_text", "text": f"Payment Patrol CFO Summary - {run_date.isoformat()}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Total AR:* {_money(cfo_summary['total_ar'])}\n*Past Due:* {_pct(cfo_summary['pct_past_due'])}\n*DSO:* {cfo_summary['dso']:.1f}\n*CEI:* {cfo_summary['cei']:.1f}%"}},
        {"type": "divider"},
    ]


def build_controller_blocks(controller_detail: dict, run_date: date) -> list[dict]:
    return [
        {"type": "header", "text": {"type": "plain_text", "text": f"Payment Patrol Controller Detail - {run_date.isoformat()}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Intercompany AR:* {_money(controller_detail['intercompany_ar'])}"}},
        {"type": "divider"},
    ]


def build_action_blocks(action_plan: dict, run_date: date) -> list[dict]:
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Payment Patrol AR Action Plan - {run_date.isoformat()}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"Tier 1 remittance count: {len(action_plan.get('tier_1_remittance', []))}"}},
    ]
    if len(blocks) > 50:
        return blocks[:48] + [{"type": "section", "text": {"type": "mrkdwn", "text": "Full list posted to Google Sheets."}}]
    return blocks


def build_cx_blocks(cx_escalation: list[dict], run_date: date) -> list[dict]:
    return [
        {"type": "header", "text": {"type": "plain_text", "text": f"Payment Patrol CX Escalation - {run_date.isoformat()}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"Escalations: {len(cx_escalation)}"}},
    ]
