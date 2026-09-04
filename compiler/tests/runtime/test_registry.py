import importlib

import pytest

from agent_profile_compiler.runtime.registry import (
    RUNTIME_TARGETS,
    RuntimeDependencyError,
    load_runtime_adapter,
)


def test_registry_exposes_exactly_the_eight_requested_runtime_targets() -> None:
    assert tuple(RUNTIME_TARGETS) == (
        "langgraph",
        "crewai",
        "llamaindex",
        "agno",
        "openai-agents",
        "google-adk",
        "pydantic-ai",
        "microsoft-agent-framework",
    )
    for target, spec in RUNTIME_TARGETS.items():
        assert spec.requirements.name == f"{target}.lock"
        assert spec.requirements.is_file()


def test_registry_loads_one_adapter_without_importing_the_other_seven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imported: list[str] = []
    real_import = importlib.import_module

    def recording_import(name: str):
        imported.append(name)
        return real_import(name)

    monkeypatch.setattr(importlib, "import_module", recording_import)

    adapter = load_runtime_adapter("langgraph")

    assert adapter.TARGET == "langgraph"
    assert imported == ["agent_profile_compiler.runtime.langgraph"]


def test_registry_reports_the_exact_extra_when_an_sdk_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_import(name: str):
        error = ModuleNotFoundError("No module named 'crewai'")
        error.name = "crewai"
        raise error

    monkeypatch.setattr(importlib, "import_module", missing_import)

    with pytest.raises(
        RuntimeDependencyError,
        match=r"crewai\.lock.*crewai==1\.15\.18",
    ):
        load_runtime_adapter("crewai")


def test_registry_rejects_unknown_target() -> None:
    with pytest.raises(ValueError, match="unknown runtime target"):
        load_runtime_adapter("autogen")
