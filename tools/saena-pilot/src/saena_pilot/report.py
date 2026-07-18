"""Preflight/audit report assembly and rendering (JSON + human text).

Reports are written ONLY into the run store (`~/.saena/pilot-runs/<run-id>/`
or `$SAENA_PILOT_HOME`) — never into either repository. Every report passes
the secret-shape guard before serialization.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from saena_pilot.models import BoundaryReport, BundleInfo
from saena_pilot.secretguard import guard_tree

REPORT_SCHEMA_VERSION = "saena.pilot-report/v1"


def build_report(
    *,
    mode: str,
    run_id: str,
    rapid7_sha: str,
    boundary: BoundaryReport,
    domain: str,
    bundle: BundleInfo,
    contract: dict[str, Any],
    contract_questions: list[str],
    reconciliation: dict[str, Any],
    discovery: dict[str, Any],
    suggested_human_actions: list[str],
) -> dict[str, Any]:
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "mode": mode,
        "run_id": run_id,
        "binding": {
            "rapid7_sha": rapid7_sha,
            "customer_sha": boundary.head_sha,
            "domain": domain,
        },
        "boundary": boundary.to_dict(),
        "bundle": bundle.to_dict(),
        "contract": contract,
        "contract_complete": not contract_questions,
        "contract_questions": contract_questions,
        "stricter_rules_reconciliation": reconciliation,
        "discovery": discovery,
        "suggested_human_actions": suggested_human_actions,
    }
    guard_tree(report, path="report")
    return report


def render_human(report: dict[str, Any]) -> str:
    lines = [
        f"saena-pilot {report['mode']} report — run {report['run_id']}",
        "",
        f"  RAPID-7 HEAD:  {report['binding']['rapid7_sha']}",
        f"  customer HEAD: {report['binding']['customer_sha']}",
        f"  domain:        {report['binding']['domain']}",
        "",
        "boundary findings:",
    ]
    findings = report["boundary"]["findings"]
    if not findings:
        lines.append("  (none)")
    else:
        for finding in findings:
            lines.append(f"  [{finding['severity']}] {finding['code']}: {finding['detail']}")
    lines.append("")
    bundle = report["bundle"]
    lines.append(
        f"skill bundle: {bundle['bundle_name']} — {len(bundle['skill_names'])} skill(s), "
        f"manifest sha256 {bundle['manifest_sha256'][:12]}… (validated)"
    )
    lines.append("")
    if report["contract_complete"]:
        lines.append("action contract: COMPLETE")
    else:
        lines.append("action contract: INCOMPLETE — open questions:")
        lines.extend(f"  {question}" for question in report["contract_questions"])
    lines.append("")
    lines.append("stricter-rules reconciliation:")
    rule_files = report["stricter_rules_reconciliation"]["rule_files"]
    if not rule_files:
        lines.append("  no customer CLAUDE.md/AGENTS.md files found")
    else:
        for entry in rule_files:
            lines.append(
                f"  {entry['path']} ({entry['size_bytes']} bytes, sha256 {entry['sha256'][:12]}…)"
            )
    lines.append(f"  policy: {report['stricter_rules_reconciliation']['policy']}")
    lines.append("")
    discovery = report["discovery"]
    lines.append(
        f"discovery: framework={discovery['framework']} status={discovery['status']} — "
        f"{discovery['detail']}"
    )
    if report["suggested_human_actions"]:
        lines.append("")
        lines.append("suggested external/operational actions (HUMAN decision only):")
        lines.extend(f"  - {action}" for action in report["suggested_human_actions"])
    return "\n".join(lines)


def write_report(run_directory: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    """Write `report-<mode>.json` + `.txt` into the run store."""
    mode = report["mode"]
    json_path = run_directory / f"report-{mode}.json"
    text_path = run_directory / f"report-{mode}.txt"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    text_path.write_text(render_human(report) + "\n", encoding="utf-8")
    return json_path, text_path
