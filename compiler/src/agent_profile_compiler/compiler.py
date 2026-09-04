from __future__ import annotations

from typing import Any, Mapping

from .model import CompilationResult, Package
from .targets import afm, amplifier, claude_code, codex


class CompilationError(RuntimeError):
    """Raised when strict compilation would lose a required semantic."""


_TARGETS = {
    "amplifier": amplifier.compile_target,
    "claude-code": claude_code.compile_target,
    "codex": codex.compile_target,
    "afm": afm.compile_target,
}


def compile_package(
    package: Package,
    target: str,
    binding: Mapping[str, Any] | None = None,
    *,
    strict: bool = True,
) -> CompilationResult:
    try:
        adapter = _TARGETS[target]
    except KeyError as exc:
        raise CompilationError(f"unknown target {target!r}; choose one of {', '.join(sorted(_TARGETS))}") from exc
    result = adapter(package, binding or {})
    if strict and result.report.has_blocking_loss:
        details = [
            f"{finding.status} {finding.agent}:{finding.feature}: {finding.detail}"
            for finding in result.report.findings
            if finding.status in {"approximated", "unsupported"}
        ]
        raise CompilationError(
            "strict compilation would lose required semantics for target "
            f"{target}: " + " | ".join(details)
        )
    return result
