import json
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).parents[2]
SCHEMA = json.loads(
    (ROOT / "spec" / "agent-composition-profile-v0.2-frontmatter.schema.json").read_text(
        encoding="utf-8"
    )
)


def test_evidence_revision_accepts_the_narrow_core() -> None:
    jsonschema.validate({"name": "technical-researcher"}, SCHEMA)


def test_evidence_revision_rejects_removed_delegates() -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"name": "technical-researcher", "delegates": []}, SCHEMA)


def test_model_requirements_are_declared_in_the_profile() -> None:
    jsonschema.validate(
        {"name": "technical-researcher", "model": {"requires": {"tool-use": True}}}, SCHEMA
    )


@pytest.mark.parametrize(
    "model",
    [
        {},
        {"requires": {}},
        {"requires": {"tool-use": False}},
        {"prefers": {"vision-input": True}},
        {"requires": {"tool-use": True}, "prefers": {"vision-input": True}},
    ],
)
def test_model_preferences_and_empty_requirements_are_rejected(model: dict) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"name": "technical-researcher", "model": model}, SCHEMA)
