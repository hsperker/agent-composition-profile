from __future__ import annotations

import copy
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

import yaml
from jsonschema import Draft202012Validator
from yaml.constructor import ConstructorError
from yaml.tokens import AliasToken, AnchorToken, TagToken

from .model import Agent, McpServer, Package, Plugin, ProfileError, Skill
from .vendor_schemas import MCP_SCHEMA, MCP_SCHEMA_ID, PLUGIN_SCHEMA, PLUGIN_SCHEMA_ID


_ALLOWED_FIELDS = {"name", "description", "model", "skills", "plugins", "delegates"}
_ALLOWED_CAPABILITIES = {"reasoning", "tool-use", "vision-input"}
_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class _CoreLoader(yaml.SafeLoader):
    """SafeLoader adjusted to YAML 1.2 core booleans and duplicate-key failure."""


_CoreLoader.yaml_implicit_resolvers = copy.deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)

# PyYAML defaults to YAML 1.1 boolean spellings. Keep only true/false.
for first_char, resolvers in list(_CoreLoader.yaml_implicit_resolvers.items()):
    _CoreLoader.yaml_implicit_resolvers[first_char] = [
        resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:bool"
    ]
_CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false)$", re.IGNORECASE),
    list("tTfF"),
)


def _construct_mapping(loader: _CoreLoader, node: yaml.nodes.MappingNode, deep: bool = False) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_CoreLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping,
)


def _unicode_trimmed(value: str) -> str:
    whitespace = (
        "\u0009\u000a\u000b\u000c\u000d\u0020\u0085\u00a0\u1680"
        "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009"
        "\u200a\u2028\u2029\u202f\u205f\u3000"
    )
    return value.strip(whitespace)


def _read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ProfileError(f"cannot read UTF-8 document {path}: {exc}") from exc

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\n") != "---":
        raise ProfileError(f"{path}: document must begin with YAML frontmatter")

    closing: int | None = None
    for index in range(1, len(lines)):
        if lines[index].rstrip("\n") == "---":
            closing = index
            break
    if closing is None:
        raise ProfileError(f"{path}: frontmatter has no closing delimiter")

    yaml_text = "".join(lines[1:closing])
    body = "".join(lines[closing + 1 :])
    if not _unicode_trimmed(body):
        raise ProfileError(f"{path}: instruction body must not be empty")

    try:
        for token in yaml.scan(yaml_text, Loader=_CoreLoader):
            if isinstance(token, (AnchorToken, AliasToken)):
                raise ProfileError(f"{path}: YAML anchors and aliases are not allowed")
            if isinstance(token, TagToken):
                raise ProfileError(f"{path}: custom YAML tags are not allowed")
        data = yaml.load(yaml_text, Loader=_CoreLoader)
    except ProfileError:
        raise
    except yaml.YAMLError as exc:
        raise ProfileError(f"{path}: invalid YAML frontmatter: {exc}") from exc

    if not isinstance(data, dict):
        raise ProfileError(f"{path}: frontmatter root must be a mapping")
    if any(not isinstance(key, str) for key in data):
        raise ProfileError(f"{path}: every frontmatter key must be a string")
    if "<<" in data:
        raise ProfileError(f"{path}: YAML merge keys are not allowed")
    return data, body.lstrip("\n")


def _validate_name(name: Any, path: Path, kind: str = "agent") -> str:
    if not isinstance(name, str) or not (1 <= len(name) <= 64) or not _NAME_RE.fullmatch(name):
        raise ProfileError(
            f"{path}: invalid {kind} name; use 1-64 lowercase letters, digits, and single hyphens"
        )
    return name


def _validate_description(description: Any, path: Path) -> str:
    if not isinstance(description, str):
        raise ProfileError(f"{path}: description must be a string")
    trimmed = _unicode_trimmed(description)
    if not trimmed or len(description) > 1024:
        raise ProfileError(f"{path}: description must contain 1-1024 Unicode scalar values")
    return trimmed


def _parse_capabilities(model: Any, path: Path) -> tuple[frozenset[str], frozenset[str]]:
    if model is None:
        return frozenset(), frozenset()
    if not isinstance(model, dict) or not model:
        raise ProfileError(f"{path}: model must be a non-empty mapping")
    unknown = set(model) - {"requires", "prefers"}
    if unknown:
        raise ProfileError(f"{path}: unknown model field(s): {', '.join(sorted(unknown))}")

    parsed: dict[str, frozenset[str]] = {}
    for section in ("requires", "prefers"):
        value = model.get(section)
        if value is None:
            parsed[section] = frozenset()
            continue
        if not isinstance(value, dict) or not value:
            raise ProfileError(f"{path}: model.{section} must be a non-empty mapping")
        unknown_caps = set(value) - _ALLOWED_CAPABILITIES
        if unknown_caps:
            raise ProfileError(
                f"{path}: unknown model capability: {', '.join(sorted(unknown_caps))}"
            )
        for capability, enabled in value.items():
            if enabled is not True:
                raise ProfileError(f"{path}: model capability {capability!r} must equal true")
        parsed[section] = frozenset(value)

    overlap = parsed["requires"] & parsed["prefers"]
    if overlap:
        raise ProfileError(
            f"{path}: capability cannot be both required and preferred: {', '.join(sorted(overlap))}"
        )
    if not parsed["requires"] and not parsed["prefers"]:
        raise ProfileError(f"{path}: model must declare at least one requirement or preference")
    return parsed["requires"], parsed["prefers"]


def _canonical_reference(
    value: Any,
    *,
    source: Path,
    package_root: Path,
    expected: str,
) -> Path:
    if not isinstance(value, str) or not value.startswith(("./", "../")):
        raise ProfileError(f"{source}: {expected} reference must begin with ./ or ../")
    if "\\" in value or "\x00" in value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ProfileError(f"{source}: invalid character in {expected} reference {value!r}")
    candidate = source.parent / value
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ProfileError(f"{source}: missing {expected} reference {value!r}") from exc
    try:
        resolved.relative_to(package_root)
    except ValueError as exc:
        raise ProfileError(f"{source}: {expected} reference resolves outside package root: {value!r}") from exc
    return resolved


def _resolve_reference_list(
    value: Any,
    *,
    source: Path,
    package_root: Path,
    expected: str,
) -> tuple[Path, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not value:
        raise ProfileError(f"{source}: {expected} must be a non-empty array")
    resolved: list[Path] = []
    seen: set[Path] = set()
    for item in value:
        target = _canonical_reference(
            item, source=source, package_root=package_root, expected=expected
        )
        if target in seen:
            raise ProfileError(f"{source}: duplicate canonical {expected} target: {item!r}")
        seen.add(target)
        resolved.append(target)
    return tuple(resolved)



def _validate_json_schema(data: Any, schema: dict[str, Any], path: Path, label: str) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(data),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if not errors:
        return
    error = errors[0]
    location = ".".join(str(part) for part in error.absolute_path)
    where = f" at {location}" if location else ""
    raise ProfileError(
        f"{path}: does not conform to Agent Plugins 1.0.0 {label} schema{where}: {error.message}"
    )


def _load_skill(root: Path) -> Skill:
    if not root.is_dir():
        raise ProfileError(f"{root}: Agent Skill reference must resolve to a directory")
    skill_file = root / "SKILL.md"
    if not skill_file.is_file():
        raise ProfileError(f"{root}: Agent Skill directory has no SKILL.md")
    data, body = _read_frontmatter(skill_file)
    name = _validate_name(data.get("name"), skill_file, "skill")
    if name != root.name:
        raise ProfileError(
            f"{skill_file}: Agent Skill name {name!r} must match its parent directory {root.name!r}"
        )
    description = _validate_description(data.get("description"), skill_file)
    return Skill(root=root, name=name, description=description, instructions=body)


def _load_mcp_servers(plugin_root: Path) -> tuple[McpServer, ...]:
    mcp_file = plugin_root / "mcp.json"
    if not mcp_file.exists():
        return ()
    try:
        data = json.loads(mcp_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileError(f"{mcp_file}: invalid Agent Plugin MCP configuration: {exc}") from exc
    _validate_json_schema(data, MCP_SCHEMA, mcp_file, "MCP")
    if data.get("$schema") != MCP_SCHEMA_ID:
        raise ProfileError(f"{mcp_file}: expected Agent Plugins 1.0.0 MCP schema")
    servers = data["mcpServers"]
    return tuple(
        McpServer(name=name, config=dict(config))
        for name, config in servers.items()
    )


def _load_plugin(root: Path) -> Plugin:
    if not root.is_dir():
        raise ProfileError(f"{root}: Agent Plugin reference must resolve to a directory")
    manifest = root / "plugin.json"
    if not manifest.is_file():
        raise ProfileError(f"{root}: Agent Plugin directory has no plugin.json")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProfileError(f"{manifest}: invalid Agent Plugin manifest: {exc}") from exc
    _validate_json_schema(data, PLUGIN_SCHEMA, manifest, "plugin")
    if data.get("$schema") != PLUGIN_SCHEMA_ID:
        raise ProfileError(f"{manifest}: expected Agent Plugins 1.0.0 plugin schema")
    name = data["name"]

    skills: list[Skill] = []
    skills_root = root / "skills"
    if skills_root.exists():
        if not skills_root.is_dir():
            raise ProfileError(f"{skills_root}: plugin skills path must be a directory")
        for child in sorted(skills_root.iterdir(), key=lambda item: item.name):
            if child.is_dir():
                skills.append(_load_skill(child.resolve()))

    mcp_servers = _load_mcp_servers(root)
    if not skills and not mcp_servers:
        raise ProfileError(f"{root}: Agent Plugin has no standard skill or MCP component")
    return Plugin(root=root, name=name, skills=tuple(skills), mcp_servers=mcp_servers)


def _parse_agent_document(path: Path, package_root: Path) -> Agent:
    if not path.is_file():
        raise ProfileError(f"{path}: agent declaration must be a regular file")
    data, body = _read_frontmatter(path)
    unknown = set(data) - _ALLOWED_FIELDS
    if unknown:
        raise ProfileError(f"{path}: unknown top-level field(s): {', '.join(sorted(unknown))}")
    missing = {"name", "description"} - set(data)
    if missing:
        raise ProfileError(f"{path}: missing required field(s): {', '.join(sorted(missing))}")

    name = _validate_name(data["name"], path)
    description = _validate_description(data["description"], path)
    requires, prefers = _parse_capabilities(data.get("model"), path)
    skill_paths = _resolve_reference_list(
        data.get("skills"), source=path, package_root=package_root, expected="skill"
    )
    plugin_paths = _resolve_reference_list(
        data.get("plugins"), source=path, package_root=package_root, expected="plugin"
    )
    delegate_paths = _resolve_reference_list(
        data.get("delegates"), source=path, package_root=package_root, expected="delegate"
    )

    direct_skills = tuple(_load_skill(skill_path) for skill_path in skill_paths)
    plugins = tuple(_load_plugin(plugin_path) for plugin_path in plugin_paths)

    skill_sources: dict[str, Path] = {}
    for skill in direct_skills + tuple(s for p in plugins for s in p.skills):
        prior = skill_sources.get(skill.name)
        if prior is not None and prior != skill.root:
            raise ProfileError(
                f"{path}: duplicate effective skill name {skill.name!r}: {prior} and {skill.root}"
            )
        skill_sources[skill.name] = skill.root

    return Agent(
        source_path=path,
        relative_path=path.relative_to(package_root),
        name=name,
        description=description,
        instructions=body,
        requires=requires,
        prefers=prefers,
        direct_skills=direct_skills,
        plugins=plugins,
        delegate_paths=delegate_paths,
    )


def load_package(entry_path: Path | str, package_root: Path | str) -> Package:
    root = Path(package_root).resolve(strict=True)
    if not root.is_dir():
        raise ProfileError(f"package root is not a directory: {root}")
    entry = Path(entry_path).resolve(strict=True)
    try:
        entry.relative_to(root)
    except ValueError as exc:
        raise ProfileError(f"entry declaration is outside package root: {entry}") from exc

    by_path: dict[Path, Agent] = {}
    by_name: dict[str, Agent] = {}
    visiting: list[Path] = []

    def visit(path: Path) -> Agent:
        if path in visiting:
            cycle = visiting[visiting.index(path) :] + [path]
            rendered = " -> ".join(str(item.relative_to(root)) for item in cycle)
            raise ProfileError(f"delegate cycle: {rendered}")
        if path in by_path:
            return by_path[path]

        agent = _parse_agent_document(path, root)
        prior = by_name.get(agent.name)
        if prior is not None and prior.source_path != path:
            raise ProfileError(
                f"duplicate package agent name {agent.name!r}: "
                f"{prior.relative_path} and {agent.relative_path}"
            )
        by_path[path] = agent
        by_name[agent.name] = agent
        visiting.append(path)

        # Inspect direct names before descending so ambiguous direct catalogs get a precise error.
        direct_name_sources: dict[str, Path] = {}
        parsed_children: list[Agent] = []
        for delegate_path in agent.delegate_paths:
            child = by_path.get(delegate_path) or _parse_agent_document(delegate_path, root)
            previous = direct_name_sources.get(child.name)
            if previous is not None and previous != delegate_path:
                raise ProfileError(
                    f"{path}: duplicate direct delegate name {child.name!r}: "
                    f"{previous.relative_to(root)} and {delegate_path.relative_to(root)}"
                )
            direct_name_sources[child.name] = delegate_path
            parsed_children.append(child)

        delegate_names: list[str] = []
        for delegate_path in agent.delegate_paths:
            child = visit(delegate_path)
            delegate_names.append(child.name)

        visiting.pop()
        final_agent = replace(agent, delegate_names=tuple(delegate_names))
        by_path[path] = final_agent
        by_name[final_agent.name] = final_agent
        return final_agent

    entry_agent = visit(entry)
    # Resolve stale pre-recursion objects to their final versions.
    agents = {name: by_path[agent.source_path] for name, agent in by_name.items()}
    return Package(root=root, entry_name=entry_agent.name, agents=agents)
