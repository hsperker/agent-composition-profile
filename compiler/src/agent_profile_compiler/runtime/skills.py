from __future__ import annotations

import json
from collections.abc import Iterable

from ..model import Skill


class SkillCatalog:
    """Per-agent Agent Skills catalog with explicit progressive disclosure."""

    def __init__(self, owner: str, skills: Iterable[Skill]) -> None:
        self.owner = owner
        self._skills: dict[str, Skill] = {}
        self._activated: list[str] = []
        for skill in skills:
            if skill.name in self._skills:
                raise ValueError(f"{owner}: duplicate skill {skill.name!r}")
            self._skills[skill.name] = skill

    @property
    def activated_names(self) -> tuple[str, ...]:
        return tuple(self._activated)

    def metadata(self) -> list[dict[str, str]]:
        return [
            {"name": skill.name, "description": skill.description}
            for skill in self._skills.values()
        ]

    def discovery_text(self) -> str:
        return json.dumps(self.metadata(), ensure_ascii=False, sort_keys=True)

    def activate(self, name: str) -> str:
        try:
            skill = self._skills[name]
        except KeyError as exc:
            raise KeyError(f"{self.owner}: unknown skill {name!r}") from exc
        if name not in self._activated:
            self._activated.append(name)
        return skill.instructions
