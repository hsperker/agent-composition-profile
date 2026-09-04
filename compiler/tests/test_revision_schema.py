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


@pytest.mark.parametrize("removed", ["model", "delegates"])
def test_evidence_revision_rejects_removed_semantics(removed: str) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"name": "technical-researcher", removed: {}}, SCHEMA)
