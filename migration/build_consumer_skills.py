"""Build the four canonical ResearchGuard consumer skills from frozen sources.

This is a one-way source migration.  It deliberately does not emit predecessor
skill ids, forwarding shims, alternate launchers, or author-side receipts into
the consumer projection.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

INTERNAL_LOGIC_ROUTES = {
    "logicguard-source-library": "source-library",
    "logicguard-structured-artifact": "structured-artifact",
    "logicguard-model-deepening": "model-deepening",
    "logicguard-artifact-synthesis": "artifact-synthesis",
    "logicguard-project-library-viewer": "project-library-viewer",
}


def _replace_tree(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    match = re.match(r"\A---\n.*?\n---\n+", text, flags=re.DOTALL)
    if match is None:
        raise ValueError("malformed skill frontmatter")
    return text[match.end() :]


def _canonicalize_commands(text: str) -> str:
    replacements = {
        "python scripts/run_logicguard.py": "researchguard logic",
        "python scripts\\run_logicguard.py": "researchguard logic",
        "python scripts/run_sourceguard.py": "researchguard source",
        "python scripts\\run_sourceguard.py": "researchguard source",
        "python scripts/run_traceguard.py": "researchguard trace",
        "python scripts\\run_traceguard.py": "researchguard trace",
        "python -m logicguard.satellite_execution_depth": "researchguard logic route-depth",
        "python -m logicguard_viewer.launcher": "researchguard logic library viewer",
        "logicguard-library-viewer": "researchguard logic library viewer",
        "python -m logicguard": "researchguard logic",
        "python -m sourceguard": "researchguard source",
        "python -m traceguard": "researchguard trace",
        "python runtime/library_depth.py": "researchguard trace library-depth",
        "python scripts\\logicguard_closure_check.py": (
            "python %USERPROFILE%\\.codex\\skills\\logicguard\\scripts\\logicguard_closure_check.py"
        ),
        "python scripts\\traceguard_closure_check.py": (
            "python %USERPROFILE%\\.codex\\skills\\traceguard\\scripts\\traceguard_closure_check.py"
        ),
        "%USERPROFILE%\\\\.codex\\\\skills\\traceguard-library\\scripts\\traceguard_library_closure_check.py": (
            "%USERPROFILE%\\\\.codex\\\\skills\\traceguard\\scripts\\traceguard_library_closure_check.py"
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _canonicalize_logic_routes(text: str) -> str:
    for predecessor, route in INTERNAL_LOGIC_ROUTES.items():
        text = text.replace(predecessor, f"route:{route}")
    text = text.replace(
        "Fall back to `logicguard`",
        "Return to the general LogicGuard route",
    )
    text = text.replace(
        "fall back to `logicguard`",
        "return to the general LogicGuard route",
    )
    text = text.replace(
        "This is a direct LogicGuard satellite skill",
        "This is an internal LogicGuard route",
    )
    text = text.replace(
        "direct satellite skills",
        "internal routes",
    )
    text = text.replace(
        "main fallback skill",
        "single direct LogicGuard skill",
    )
    text = text.replace(
        "Use a satellite first",
        "Select an internal route",
    )
    text = text.replace(
        "satellite execution-depth",
        "internal-route execution-depth",
    )
    text = text.replace(
        "satellite execution package",
        "internal-route execution package",
    )
    text = text.replace("satellite routes", "internal routes")
    text = text.replace("existing satellites", "the owning internal routes")
    return text


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _main_logic_skill(logic_root: Path) -> str:
    source = (logic_root / "logicguard" / "SKILL.md").read_text(encoding="utf-8")
    source = _canonicalize_logic_routes(_canonicalize_commands(source))
    old = re.compile(
        r"LogicGuard has a single direct LogicGuard skill plus internal routes "
        r"for routes with distinct first actions\. Select an internal route "
        r"when the user's request clearly matches it:\n\n"
        r"(?:- .*\n){5}",
    )
    replacement = (
        "LogicGuard is one direct ResearchGuard member with five internal routes. "
        "Route once by the requested first action:\n\n"
        "- `route:source-library`: preserve, model, deepen, link, or move sources.\n"
        "- `route:structured-artifact`: audit or repair document/deck structure.\n"
        "- `route:model-deepening`: recursively deepen an existing model.\n"
        "- `route:artifact-synthesis`: produce an evidence-bounded story plan.\n"
        "- `route:project-library-viewer`: inspect the read-only project library.\n\n"
        "These are internal routes, not separately installed skills. Read the "
        "matching file under `references/routes/` before executing it. Mixed or "
        "ambiguous requests remain in this general route until one exact owner is "
        "selected; an unclear route blocks instead of trying another route.\n"
    )
    source, count = old.subn(replacement, source, count=1)
    if count != 1:
        raise ValueError("LogicGuard route introduction did not match frozen source")
    source = re.sub(
        r"Executable commands assume.*?bundled wrapper\.\n",
        "Use the single installed `researchguard` console. No checkout locator, "
        "environment-variable launcher, or alternate module command is part of "
        "normal execution.\n",
        source,
        count=1,
    )
    source = source.replace(
        "Use the package entrypoint from a LogicGuard checkout or an environment where `logicguard` is installed:",
        "Use the single installed ResearchGuard entrypoint:",
    )
    source = re.sub(
        r"For direct repository work, run .*?\n",
        "The installed `researchguard logic` command is the only normal runtime path.\n",
        source,
        count=1,
    )
    return source


def _main_member_skill(source: Path, *, name: str, description: str) -> str:
    body = _canonicalize_commands(source.read_text(encoding="utf-8"))
    body = re.sub(
        r"\A---\n.*?\n---\n",
        f"---\nname: {name}\ndescription: {description}\n---\n",
        body,
        flags=re.DOTALL,
        count=1,
    )
    if name == "sourceguard":
        body = body.replace(
            "Treat legacy `status=closed` without a complete closure basis as "
            "`legacy_unqualified`, reopen it for review, and do not inherit the "
            "old completion claim.",
            "Reject any gap record that lacks the current `semantic_state` and a "
            "complete closure basis. Historical records must be migrated directly "
            "before normal runtime.",
        )
        body = body.replace(
            "Preserve the compatibility `status` projection, but close only with "
            "a basis that records anchors, sources, observations, thresholds, "
            "target match, and claim-use decision.",
            "Persist only the current `semantic_state`, and close only with a basis "
            "that records anchors, sources, observations, thresholds, target match, "
            "and claim-use decision.",
        )
    return body


def _researchguard_skill() -> str:
    return """---
name: researchguard
description: Route a research or investigation request to exactly one ResearchGuard member when the request crosses argument, source-discovery, or evidence-trace boundaries, or when the correct member is genuinely ambiguous. Use LogicGuard directly for argument structure, SourceGuard directly for evidence discovery planning, and TraceGuard directly for temporal or competing-storyline reconstruction.
---

# ResearchGuard

ResearchGuard is the single suite-level entry for three complete member skills:
`logicguard`, `sourceguard`, and `traceguard`. It coordinates them without
duplicating their native work or silently trying another member.

## Route once

1. Classify the request by its first required native action.
2. Use `logicguard` for argument structure, warrants, assumptions, rebuttals,
   artifact structure, source-library preservation, model deepening, synthesis,
   or the LogicGuard project-library viewer.
3. Use `sourceguard` for evidence/source discovery plans, source-role gaps,
   retrieval execution, provider evidence, and claim-use qualification.
4. Use `traceguard` for temporal order, competing storylines, event/evidence
   separation, execution chains, counter-scenarios, and bounded causal stories.
5. Use the umbrella only for a genuinely cross-member or ambiguous request.
   Select exactly one member before any member executes:

```powershell
researchguard run --member logicguard -- <member arguments>
researchguard run --member sourceguard -- <member arguments>
researchguard run --member traceguard -- <member arguments>
```

Direct member commands execute the same owner and primary path:

```powershell
researchguard logic <arguments>
researchguard source <arguments>
researchguard trace <arguments>
```

## Handoffs

A member may emit a typed `awaiting_owner` handoff. A handoff names the source
request, source member, target member, handoff kind, and payload. It does not
execute the next member. Start one new explicit member request after inspecting
the handoff. Re-entry with an active request id is blocked.

## Completion

- one exact member owns each execution;
- direct and umbrella entry bind to the same native owner;
- ambiguity, recursion, unknown members, and terminal member failure are
  visible blocked results;
- no member result is upgraded by another member;
- no old command, skill id, alias, forwarding shell, or alternate runtime is
  part of the suite.
"""


def _openai_yaml(display_name: str, description: str, prompt: str) -> str:
    return (
        "interface:\n"
        f'  display_name: "{display_name}"\n'
        f'  short_description: "{description}"\n'
        f'  default_prompt: "{prompt}"\n'
    )


def build(*, logic_root: Path, source_root: Path, trace_root: Path) -> None:
    _replace_tree(SKILLS)

    _write_text(SKILLS / "researchguard" / "SKILL.md", _researchguard_skill())
    _write_text(
        SKILLS / "researchguard" / "agents" / "openai.yaml",
        _openai_yaml(
            "ResearchGuard",
            "Route research work to one exact Guard owner",
            "Use $researchguard to select exactly one research Guard and preserve typed handoffs.",
        ),
    )

    _write_text(SKILLS / "logicguard" / "SKILL.md", _main_logic_skill(logic_root))
    _write_text(
        SKILLS / "logicguard" / "agents" / "openai.yaml",
        _openai_yaml(
            "LogicGuard",
            "Audit and deepen argument structure",
            "Use $logicguard to model and validate this argument or structured artifact.",
        ),
    )
    logic_routes_root = SKILLS / "logicguard" / "references" / "routes"
    for predecessor, route in INTERNAL_LOGIC_ROUTES.items():
        source = logic_root / predecessor / "SKILL.md"
        body = _strip_frontmatter(source.read_text(encoding="utf-8"))
        body = _canonicalize_logic_routes(_canonicalize_commands(body))
        body = body.replace(
            "English canonical/fallback text plus Chinese and English display variants",
            "explicit Chinese and English display variants with no implicit language substitution",
        )
        body = re.sub(
            r"\A# LogicGuard .*$",
            f"# Internal LogicGuard route: {route}",
            body,
            count=1,
            flags=re.MULTILINE,
        )
        _write_text(logic_routes_root / f"{route}.md", body)
    _copy_file(
        logic_root / "logicguard" / "scripts" / "logicguard_closure_check.py",
        SKILLS / "logicguard" / "scripts" / "logicguard_closure_check.py",
    )
    logic_closure = (
        SKILLS / "logicguard" / "scripts" / "logicguard_closure_check.py"
    )
    _write_text(
        logic_closure,
        logic_closure.read_text(encoding="utf-8").replace(
            '"logicguard-model-deepening"',
            '"logicguard.route.model-deepening"',
        ),
    )

    _write_text(
        SKILLS / "sourceguard" / "SKILL.md",
        _main_member_skill(
            source_root / "sourceguard" / "SKILL.md",
            name="sourceguard",
            description=(
                "Plan and execute evidence/source discovery for a claim with explicit "
                "source roles, provider evidence, gaps, and bounded claim-use decisions. "
                "Use for source search plans and retrieval qualification, not argument "
                "licensing or temporal-storyline inference."
            ),
        ),
    )
    _write_text(
        SKILLS / "sourceguard" / "agents" / "openai.yaml",
        _openai_yaml(
            "SourceGuard",
            "Plan evidence discovery and qualify source use",
            "Use $sourceguard to plan and qualify the evidence needed for this claim.",
        ),
    )
    _copy_file(
        source_root / "sourceguard" / "scripts" / "sourceguard_closure_check.py",
        SKILLS / "sourceguard" / "scripts" / "sourceguard_closure_check.py",
    )

    trace_main = _main_member_skill(
        trace_root / "traceguard" / "SKILL.md",
        name="traceguard",
        description=(
            "Reconstruct and stress-test evidence-backed temporal traces, competing "
            "storylines, execution chains, and bounded causal narratives. Use for "
            "event/evidence separation and counter-scenarios, not source discovery "
            "planning or final argument licensing."
        ),
    )
    trace_main = trace_main.replace(
        "Use `traceguard-library` when the user needs to save messy investigation material by case and search direction before building a model.",
        "Use the internal `route:case-library` when the user needs to save messy investigation material by case and search direction before building a model. Read `references/routes/case-library.md` before executing it.",
    )
    _write_text(SKILLS / "traceguard" / "SKILL.md", trace_main)
    _write_text(
        SKILLS / "traceguard" / "agents" / "openai.yaml",
        _openai_yaml(
            "TraceGuard",
            "Stress-test timelines and competing storylines",
            "Use $traceguard to reconstruct and test this evidence-backed storyline.",
        ),
    )
    trace_library = _strip_frontmatter(
        (trace_root / "traceguard-library" / "SKILL.md").read_text(encoding="utf-8")
    )
    trace_library = _canonicalize_commands(trace_library)
    trace_library = trace_library.replace(
        "# TraceGuard Library Skill",
        "# Internal TraceGuard route: case-library",
    )
    trace_library = trace_library.replace(
        "TraceGuard Library Skill",
        "TraceGuard case-library route",
    )
    trace_library = trace_library.replace(
        "TraceGuard Library v0.3",
        "The current TraceGuard case library",
    )
    trace_library = trace_library.replace(
        "target `traceguard-library`, owner `traceguard.library`, and route\n"
        "`route:traceguard-library:operate`",
        "target `traceguard.case-library`, owner `traceguard.case-library`, and route\n"
        "`route:traceguard:case-library`",
    )
    trace_library = trace_library.replace(
        ".traceguard/traceguard-library-scheduled-production.json",
        ".traceguard/case-library-scheduled-production.json",
    )
    trace_library = trace_library.replace(
        "`route:traceguard-library:operate`",
        "`route:traceguard:case-library`",
    )
    trace_library = trace_library.replace(
        "<traceguard-library-ledger.json>",
        "<trace-case-library-ledger.json>",
    )
    _write_text(
        SKILLS / "traceguard" / "references" / "routes" / "case-library.md",
        trace_library,
    )
    _copy_file(
        trace_root
        / "traceguard-library"
        / "scripts"
        / "traceguard_library_closure_check.py",
        SKILLS / "traceguard" / "scripts" / "traceguard_library_closure_check.py",
    )
    _copy_file(
        trace_root.parent / "scripts" / "traceguard_closure_check.py",
        SKILLS / "traceguard" / "scripts" / "traceguard_closure_check.py",
    )
    trace_closure = (
        SKILLS / "traceguard" / "scripts" / "traceguard_library_closure_check.py"
    )
    trace_closure_text = trace_closure.read_text(encoding="utf-8")
    trace_closure_text = trace_closure_text.replace(
        '"traceguard-library"',
        '"traceguard.case-library"',
    )
    _write_text(trace_closure, trace_closure_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--logic-skills-root", type=Path, required=True)
    parser.add_argument("--source-skills-root", type=Path, required=True)
    parser.add_argument("--trace-skills-root", type=Path, required=True)
    arguments = parser.parse_args()
    build(
        logic_root=arguments.logic_skills_root.resolve(),
        source_root=arguments.source_skills_root.resolve(),
        trace_root=arguments.trace_skills_root.resolve(),
    )
