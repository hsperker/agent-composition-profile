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
    return {
        finding["feature"]: finding["status"]
        for finding in report["findings"]
        if finding["agent"] == report["source_entry"]
    }


def module_outcomes(report: dict) -> dict[str, str]:
    return {module: value["outcome"] for module, value in report["modules"].items()}


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
        "modules": {report["target"]: module_outcomes(report) for report in reports},
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
    modules = sorted({module for outcomes in matrix["modules"].values() for module in outcomes})
    module_headers = ["module", *matrix["targets"]]
    module_rows = [
        [module, *(matrix["modules"][target].get(module, "not-declared") for target in matrix["targets"])]
        for module in modules
    ]
    markdown = [
        "# Generated compatibility matrix",
        "",
        "Evidence kind: "
        + ", ".join(
            f"{target}={matrix['evidence_kind'][target]}" for target in matrix["targets"]
        ),
        "",
        "## Entry-agent classification by source semantic",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
        "",
        "## Strict conformance by module (all agents)",
        "",
        "`accepted` means no finding in the module is approximated or unsupported; "
        "`unverified` findings do not block and are listed in each report.",
        "",
        "| " + " | ".join(module_headers) + " |",
        "| " + " | ".join("---" for _ in module_headers) + " |",
        *("| " + " | ".join(row) + " |" for row in module_rows),
        "",
        "Generated from individual compatibility reports by `scripts/build_runtime_matrix.py`.",
        "",
    ]
    (RUNTIME / "matrix.md").write_text("\n".join(markdown), encoding="utf-8")
    print(f"generated matrix for {len(reports)} targets and {len(features)} source semantics")


if __name__ == "__main__":
    main()
