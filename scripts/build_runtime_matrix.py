#!/usr/bin/env python3
"""Aggregate per-framework compatibility evidence without voting on semantics."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "generated" / "runtime"
LEGACY_REPORTS = [
    ROOT / "generated" / "amplifier-full-diagnostic" / "compatibility-report.json",
    ROOT / "generated" / "claude-code-full-strict" / "compatibility-report.json",
    ROOT / "generated" / "codex-full-strict" / "compatibility-report.json",
    ROOT / "generated" / "afm-full-diagnostic" / "compatibility-report.json",
]


def entry_findings(report: dict) -> dict[str, str]:
    findings = {
        finding["feature"]: finding["status"]
        for finding in report["findings"]
        if finding["agent"] == report["source_entry"]
    }
    # The earlier static compiler reported these together. Its finding detail
    # explicitly states that both name and discovery description were emitted.
    if "identity" in findings:
        findings["name"] = findings["identity"]
        findings["description"] = findings["identity"]
        del findings["identity"]
    return findings


def main() -> None:
    runtime_reports = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(RUNTIME.glob("*/compatibility.json"))
    ]
    if len(runtime_reports) != 8:
        raise SystemExit(f"expected 8 runtime reports, found {len(runtime_reports)}")
    legacy_reports = [json.loads(path.read_text(encoding="utf-8")) for path in LEGACY_REPORTS]
    reports = [*runtime_reports, *legacy_reports]
    findings_by_target = {
        report["target"]: entry_findings(report)
        for report in reports
    }
    features = sorted({feature for findings in findings_by_target.values() for feature in findings})
    matrix = {
        "source_fixture": "examples/research-team/lead.agent.md",
        "source_fixture_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((ROOT / "examples" / "research-team").rglob("*"))
            if path.is_file()
        },
        "targets": [report["target"] for report in reports],
        "features": {
            feature: {
                target: findings.get(feature, "not-declared")
                for target, findings in findings_by_target.items()
            }
            for feature in features
        },
        "strict_outcomes": {
            report["target"]: (
                report["strict_mode"]["outcome"]
                if "strict_mode" in report
                else ("rejected" if report["has_blocking_loss"] else "accepted")
            )
            for report in reports
        },
        "evidence_kind": {
            report["target"]: (
                "runtime" if "strict_mode" in report else "static-lowering"
            )
            for report in reports
        },
    }
    (RUNTIME / "matrix.json").write_text(
        json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    headers = ["semantic", *matrix["targets"]]
    rows = [
        [feature, *(matrix["features"][feature][target] for target in matrix["targets"])]
        for feature in matrix["features"]
    ]
    markdown = [
        "# Generated compatibility matrix",
        "",
        "Evidence kind: "
        + ", ".join(
            f"{target}={matrix['evidence_kind'][target]}" for target in matrix["targets"]
        ),
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
        "",
        "Generated from individual compatibility reports by `scripts/build_runtime_matrix.py`.",
        "",
    ]
    (RUNTIME / "matrix.md").write_text("\n".join(markdown), encoding="utf-8")
    print(f"generated matrix for {len(reports)} targets and {len(features)} source semantics")


if __name__ == "__main__":
    main()
