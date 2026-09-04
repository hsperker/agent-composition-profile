from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
from types import ModuleType


@dataclass(frozen=True)
class RuntimeTarget:
    module: str
    distribution: str
    version: str
    requirements: Path


_REQUIREMENTS = Path(__file__).resolve().parents[3] / "runtime-requirements"


RUNTIME_TARGETS = {
    "langgraph": RuntimeTarget(
        "agent_profile_compiler.runtime.langgraph",
        "langchain",
        "1.4.0",
        _REQUIREMENTS / "langgraph.lock",
    ),
    "crewai": RuntimeTarget(
        "agent_profile_compiler.runtime.crewai",
        "crewai",
        "1.15.18",
        _REQUIREMENTS / "crewai.lock",
    ),
    "llamaindex": RuntimeTarget(
        "agent_profile_compiler.runtime.llamaindex",
        "llama-index-core",
        "0.14.24",
        _REQUIREMENTS / "llamaindex.lock",
    ),
    "agno": RuntimeTarget(
        "agent_profile_compiler.runtime.agno",
        "agno",
        "3.0.5",
        _REQUIREMENTS / "agno.lock",
    ),
    "openai-agents": RuntimeTarget(
        "agent_profile_compiler.runtime.openai_agents",
        "openai-agents",
        "0.22.0",
        _REQUIREMENTS / "openai-agents.lock",
    ),
    "google-adk": RuntimeTarget(
        "agent_profile_compiler.runtime.google_adk",
        "google-adk",
        "2.8.0",
        _REQUIREMENTS / "google-adk.lock",
    ),
    "pydantic-ai": RuntimeTarget(
        "agent_profile_compiler.runtime.pydantic_ai",
        "pydantic-ai",
        "2.38.0",
        _REQUIREMENTS / "pydantic-ai.lock",
    ),
    "microsoft-agent-framework": RuntimeTarget(
        "agent_profile_compiler.runtime.microsoft_agent_framework",
        "agent-framework-core",
        "1.17.0",
        _REQUIREMENTS / "microsoft-agent-framework.lock",
    ),
}


class RuntimeDependencyError(ImportError):
    """Raised when a requested framework's exact tested SDK is unavailable."""


def load_runtime_adapter(target: str) -> ModuleType:
    try:
        spec = RUNTIME_TARGETS[target]
    except KeyError as exc:
        raise ValueError(
            f"unknown runtime target {target!r}; choose one of {', '.join(RUNTIME_TARGETS)}"
        ) from exc

    try:
        return importlib.import_module(spec.module)
    except ModuleNotFoundError as exc:
        raise RuntimeDependencyError(
            f"runtime target {target!r} requires environment lock {spec.requirements.name!r} "
            f"with tested dependency {spec.distribution}=={spec.version}"
        ) from exc
