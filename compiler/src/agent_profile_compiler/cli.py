from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .compiler import CompilationError, compile_package
from .model import ProfileError
from .parser import load_package


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile an Agent Composition Profile package")
    parser.add_argument("entry", type=Path, help="Entry .agent.md declaration")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--target", choices=["amplifier", "claude-code", "codex", "afm"], required=True)
    parser.add_argument("--binding", type=Path, help="Target-specific, non-portable binding YAML")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true", help="Write output even when required semantics are unsupported")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    binding = {}
    if args.binding:
        loaded = yaml.safe_load(args.binding.read_text(encoding="utf-8")) or {}
        if "targets" in loaded:
            loaded = loaded["targets"].get(args.target, {})
        if not isinstance(loaded, dict):
            print("binding must decode to a mapping", file=sys.stderr)
            return 2
        binding = loaded
    try:
        package = load_package(args.entry, args.package_root)
        result = compile_package(package, args.target, binding, strict=not args.diagnostic)
    except (ProfileError, CompilationError, OSError, yaml.YAMLError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    args.output.mkdir(parents=True, exist_ok=True)
    for relative, content in result.files.items():
        destination = args.output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
