"""One route per function: every error handler in the product is listed with the documented
behaviour it serves, and the handler's own code must have that behaviour's shape.

The inventory is computed from the source: every ``except`` whose body does not end in ``raise``
(or returns, breaks or continues before it), every ``contextlib.suppress`` and every ``finally``
that returns is found. Each must appear in HANDLED under one of the CONTRACTS, a documented
sentence of README.md "Errors", and the test then checks the handler's code against that contract:
a command boundary prints the error and returns a nonzero code, a result row carries the error text,
a dialog shows it, and a display fallback only guards a window-system call in the desktop viewer.
A listed handler that no longer exists fails too, so the list cannot go stale. The tests below it
each inject an error into a route that used to hide it and require a failure.
"""
from __future__ import annotations

import ast
from collections import Counter
import json
from pathlib import Path
import shutil
import zipfile

import pytest
import yaml

from research_tree_support import folder  # noqa: F401 - shared question fixture

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "researchguard"
SCANNED = {SRC: "", ROOT / "scripts": "scripts/"}

# The behaviours a handler that does not re-raise may serve, as README.md "Errors" states them.
CONTRACTS = {
    "exit": "A command that fails prints the error and exits with a nonzero code; it never answers with a default value.",
    "row": "A check or library step that fails puts the error into the result it returns, as a named error, gap, finding or error field with the error text, so the caller sees it.",
    "dialog": "In the desktop library viewer, a failed import, export or dissolve shows the error in an error dialog and changes nothing.",
    "display": "When the desktop library viewer cannot use a window-system feature (maximizing, screen DPI, an icon, a dialog), it draws the plain form instead; this changes what is shown, never a result.",
}

# (file, enclosing function, caught types) -> (count, contract)
HANDLED = {
    ("experiment/cli.py", "main", "(KeyError, ValueError, TypeError)"): (1, "exit"),
    ("logic/cli.py", "main", "Exception"): (1, "exit"),
    ("logic/cli.py", "_cmd_library_viewer", "ImportError"): (1, "exit"),
    ("source/cli.py", "main", "Exception"): (1, "exit"),
    ("source/cli.py", "run", "(ValueError, TypeError, KeyError)"): (1, "exit"),
    ("trace/cli.py", "cmd_validate", "(OSError, SchemaError, ValueError, InferenceError)"): (1, "exit"),
    ("trace/cli.py", "cmd_evaluate", "(OSError, SchemaError, ValueError, InferenceError)"): (1, "exit"),
    ("trace/cli.py", "cmd_depth", "(OSError, SchemaError, ValueError, InferenceError)"): (1, "exit"),
    ("trace/cli.py", "cmd_diagnose", "(OSError, SchemaError, ValueError, InferenceError)"): (1, "exit"),
    ("trace/cli.py", "cmd_gaps", "(OSError, SchemaError, ValueError, InferenceError)"): (1, "exit"),
    ("trace/cli.py", "cmd_report", "(OSError, SchemaError, ValueError, InferenceError)"): (1, "exit"),
    ("trace/cli.py", "cmd_export_logicguard", "(OSError, SchemaError, ValueError, InferenceError)"): (1, "exit"),
    ("trace/cli.py", "cmd_compare", "(OSError, SchemaError, ValueError, InferenceError)"): (1, "exit"),
    ("trace/cli.py", "cmd_simulate", "(OSError, SchemaError, ValueError, InferenceError)"): (2, "exit"),
    ("trace/cli.py", "cmd_iterate", "(OSError, SchemaError, ValueError, InferenceError, TaskIterationError)"): (1, "exit"),
    ("trace/cli.py", "cmd_library", "(OSError, ValueError, case_library.LibraryError, SchemaError)"): (1, "exit"),
    ("research.py", "sync_main", "(OSError, ValueError, TypeError, yaml.YAMLError)"): (1, "exit"),
    ("research.py", "status_main", "(OSError, ValueError, TypeError, yaml.YAMLError)"): (1, "exit"),
    ("research.py", "load_research", "(OSError, ValueError, TypeError, KeyError, yaml.YAMLError)"): (1, "row"),
    ("research.py", "load_research", "(OSError, ValueError, TypeError, KeyError)"): (1, "row"),
    ("research.py", "research_status", "(ValueError, TypeError, KeyError, ArithmeticError)"): (3, "row"),
    ("logic/validator.py", "validate_model", "ProvenanceError"): (1, "row"),
    ("logic/validator.py", "source_model_provenance_problems", "ProvenanceError"): (1, "row"),
    ("logic/synthesis.py", "_source_library_binding_gaps", "Exception"): (4, "row"),
    ("logic/source_intake.py", "_intake_one", "SourceLibraryError"): (1, "row"),
    ("logic/source_intake.py", "_intake_one", "Exception"): (1, "row"),
    ("logic/library_viewer.py", "build_source_graph_payload", "ModelLoadError"): (1, "row"),
    ("logic/library_viewer.py", "_source_card", "ModelLoadError"): (1, "row"),
    ("logic_viewer/launcher.py", "_show_startup_error", "ImportError"): (1, "display"),
    ("logic_viewer/launcher.py", "_show_startup_error", "tk.TclError"): (1, "display"),
    ("logic_viewer/desktop_app.py", "_enable_windows_dpi_awareness", "(AttributeError, OSError, ValueError)"): (2, "display"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._maximize_initial_window", "tk.TclError"): (1, "display"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._detect_unit_scale", "tk.TclError"): (1, "display"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._detect_font_scale", "tk.TclError"): (1, "display"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._load_image_assets", "tk.TclError"): (1, "display"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._load_image_assets", "(OSError, tk.TclError)"): (1, "display"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._export_library_package", "Exception"): (1, "dialog"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._import_library_package", "Exception"): (1, "dialog"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._dissolve_project", "Exception"): (1, "dialog"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._open_settings_window.configure_combo_popup", "tk.TclError"): (1, "display"),
    ("scripts/check_researchguard_privacy.py", "scan_tree", "(OSError, RuntimeError)"): (1, "row"),
    ("scripts/check_researchguard_privacy.py", "scan_staged_diff", "(OSError, RuntimeError)"): (2, "row"),
    ("scripts/install_skill.py", "differences", "OSError"): (1, "row"),
}

PRINTERS = {"print", "_print_json", "_json_out", "write"}
ROW_SINKS = {"append", "extend"}
WINDOW_NAMES = {"tk", "ctypes", "ImageTk", "Image", "messagebox"}
WINDOW_ATTRIBUTES = {"tk", "winfo_fpixels", "state", "iconphoto", "PhotoImage"}
DISPLAY_TYPES = {"tk.TclError", "OSError", "AttributeError", "ValueError", "ImportError"}


def _own_nodes(statements):
    """Every node of these statements, without the bodies of nested functions and classes."""
    stack = list(statements)
    while stack:
        node = stack.pop()
        yield node
        stack.extend(child for child in ast.iter_child_nodes(node)
                     if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)))


def _mentions(node, name):
    return name is not None and any(isinstance(item, ast.Name) and item.id == name for item in ast.walk(node))


def _callee(call):
    return call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")


def _shapes(row):
    """The contracts a handler's own code satisfies, computed from its AST."""
    kind, name, body, guarded, path, caught = (row[key] for key in ("kind", "name", "body", "guarded", "path", "caught"))
    nodes = list(_own_nodes(body))
    calls = [node for node in nodes if isinstance(node, ast.Call)]
    shapes = set()
    if kind == "except" and _mentions(ast.Module(body=body, type_ignores=[]), name):
        if any(_callee(call) in PRINTERS for call in calls) and any(
                isinstance(node, ast.Return) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, int) and node.value.value >= 1 for node in nodes):
            shapes.add("exit")
        carried = [arg for call in calls if _callee(call) in ROW_SINKS for arg in call.args]
        carried += [value for node in nodes if isinstance(node, ast.Dict)
                    for key, value in zip(node.keys, node.values)
                    if isinstance(key, ast.Constant) and "error" in str(key.value)]
        carried += [keyword.value for call in calls for keyword in call.keywords if keyword.arg in {"error", "skip_reason"}]
        carried += [node.value for node in nodes if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and "error" in target.id for target in node.targets)]
        if any(_mentions(value, name) for value in carried):
            shapes.add("row")
        if any(_callee(call) == "showerror" and any(_mentions(arg, name) for arg in call.args) for call in calls):
            shapes.add("dialog")
    touches_window = any((isinstance(node, ast.Name) and node.id in WINDOW_NAMES)
                         or (isinstance(node, ast.Attribute) and node.attr in WINDOW_ATTRIBUTES)
                         or (isinstance(node, (ast.Import, ast.ImportFrom)) and "tkinter" in ast.unparse(node))
                         for node in _own_nodes(guarded))
    types = {part.strip() for part in caught.strip("()").split(",")}
    if kind in {"except", "suppress"} and path.startswith("logic_viewer/") and touches_window and types <= DISPLAY_TYPES:
        shapes.add("display")
    return shapes


def handlers_in(text, path):
    """Every handler in ``text`` that does not re-raise, with what the contract checks need."""
    tree = ast.parse(text)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def owner_name(node):
        names, owner = [], parents.get(node)
        while owner is not None:
            if isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(owner.name)
            owner = parents.get(owner)
        return ".".join(reversed(names)) or "<module>"

    rows = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            for handler in node.handlers:
                exits = [item for item in _own_nodes(handler.body) if isinstance(item, (ast.Return, ast.Break, ast.Continue))]
                if isinstance(handler.body[-1], ast.Raise) and not exits:
                    continue
                rows.append({"kind": "except", "path": path, "function": owner_name(handler), "name": handler.name,
                             "caught": ast.unparse(handler.type) if handler.type else "<bare>",
                             "body": handler.body, "guarded": node.body})
            if any(isinstance(item, (ast.Return, ast.Break, ast.Continue)) for item in _own_nodes(node.finalbody)):
                rows.append({"kind": "finally", "path": path, "function": owner_name(node), "name": None,
                             "caught": "finally", "body": node.finalbody, "guarded": node.body})
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                call = item.context_expr
                if isinstance(call, ast.Call) and _callee(call) == "suppress":
                    rows.append({"kind": "suppress", "path": path, "function": owner_name(node), "name": None,
                                 "caught": ", ".join(ast.unparse(arg) for arg in call.args) or "<none>",
                                 "body": [], "guarded": node.body})
    return rows


def _handlers():
    rows = []
    for base, prefix in SCANNED.items():
        for path in sorted(base.rglob("*.py")):
            rows.extend(handlers_in(path.read_text(encoding="utf-8"), prefix + path.relative_to(base).as_posix()))
    return rows


def inventory_problems(rows, handled):
    """What is wrong with the inventory: unlisted or stale handlers, and handlers that do not do what their contract says."""
    found = Counter((row["path"], row["function"], row["caught"]) for row in rows)
    listed = Counter({key: count for key, (count, _) in handled.items()})
    problems = [f"not listed: {key} x{count - listed[key]} (raise visibly, or give it a documented contract)"
                for key, count in sorted(found.items()) if count > listed[key]]
    problems += [f"listed but gone: {key} x{count - found[key]}" for key, count in sorted(listed.items()) if count > found[key]]
    for row in rows:
        key = (row["path"], row["function"], row["caught"])
        if key not in handled:
            continue
        contract = handled[key][1]
        if contract not in CONTRACTS:
            problems.append(f"{key}: {contract!r} is not a documented contract ({', '.join(CONTRACTS)})")
        elif contract not in _shapes(row):
            problems.append(f"{key} ({row['kind']}): its code does not do what contract {contract!r} says: {CONTRACTS[contract]}")
    return problems


def test_every_non_raising_handler_serves_a_documented_contract():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert [name for name, sentence in CONTRACTS.items() if sentence not in readme] == []
    assert inventory_problems(_handlers(), HANDLED) == []


SWALLOWERS = {
    "default on error": "def f(x):\n    try:\n        return int(x)\n    except ValueError:\n        return 0\n",
    "error text returned as a value": "def f(x):\n    try:\n        return int(x)\n    except ValueError as exc:\n        return str(exc)\n",
    "early return before raise": "def f(x, quiet):\n    try:\n        return int(x)\n    except ValueError:\n        if quiet:\n            return 0\n        raise\n",
    "suppress": "import contextlib\ndef f(x):\n    with contextlib.suppress(Exception):\n        return int(x)\n    return 0\n",
    "return inside finally": "def f(x):\n    try:\n        return int(x)\n    finally:\n        return 0\n",
    "pass in the viewer": "def f(x):\n    try:\n        return int(x)\n    except ValueError:\n        pass\n",
}


@pytest.mark.parametrize("name", sorted(SWALLOWERS))
def test_the_inventory_refuses_a_swallowing_handler_under_any_listing(name):
    path = "logic_viewer/new.py" if name == "pass in the viewer" else "picture.py"
    rows = handlers_in(SWALLOWERS[name], path)
    assert len(rows) == 1
    key = (rows[0]["path"], rows[0]["function"], rows[0]["caught"])
    assert inventory_problems(rows, {})[0].startswith("not listed:")
    for contract in (*CONTRACTS, "fine"):
        assert inventory_problems(rows, {key: (1, contract)}), contract


def test_the_inventory_accepts_handlers_that_carry_the_error():
    good = {
        "exit": "def main():\n    try:\n        run()\n    except ValueError as exc:\n        print(exc)\n        return 2\n",
        "row": "def check(errors):\n    try:\n        run()\n    except ValueError as exc:\n        errors.append(f'bad: {exc}')\n",
        "dialog": "def act(self):\n    try:\n        run()\n    except Exception as exc:\n        messagebox.showerror('x', str(exc))\n",
        "display": "def icon(self):\n    try:\n        self.iconphoto(True, tk.PhotoImage(file='a.png'))\n    except tk.TclError:\n        self.icon = None\n",
    }
    for contract, text in good.items():
        rows = handlers_in(text, "logic_viewer/new.py")
        key = (rows[0]["path"], rows[0]["function"], rows[0]["caught"])
        assert inventory_problems(rows, {key: (1, contract)}) == [], contract
    assert handlers_in("def f():\n    try:\n        run()\n    except ValueError:\n        raise\n", "x.py") == []


# Each test below injects an error into a route that used to answer with a default or skip it.

def test_an_input_that_vanishes_before_its_digest_fails_status(folder):
    from researchguard.research import load_research, research_status
    tree = load_research(folder)
    (folder / "trace.yaml").unlink()
    with pytest.raises(FileNotFoundError):
        research_status(tree)


def test_a_non_numeric_logic_confidence_or_weight_is_a_load_error():
    from researchguard.logic.loader import ModelLoadError, load_model_from_dict
    node = {"type": "Claim", "text": "A claim"}
    assert load_model_from_dict({"model": {"id": "m"}, "nodes": {"c": node}, "edges": []}).nodes["c"].confidence == 0.5
    with pytest.raises(ModelLoadError, match="confidence"):
        load_model_from_dict({"model": {"id": "m"}, "nodes": {"c": {**node, "confidence": "high"}}, "edges": []})
    with pytest.raises(ModelLoadError, match="weight"):
        load_model_from_dict({"model": {"id": "m"}, "nodes": {"c": node, "d": node},
                              "edges": [{"source": "c", "target": "d", "type": "supports", "weight": "strong"}]})


def test_a_non_numeric_source_score_is_a_schema_error():
    from researchguard.source.schema import BeliefState, SchemaError
    assert BeliefState.from_dict({"sources": [{"source_id": "s"}]}).sources[0].source_reliability == 0.0
    with pytest.raises(SchemaError, match="source_reliability"):
        BeliefState.from_dict({"sources": [{"source_id": "s", "source_reliability": "high"}]})


@pytest.mark.parametrize("key,value", [("minimum_per_trace_qualified_event_count", "many"),
                                       ("minimum_per_trace_qualified_event_ratio", "most")])
def test_a_non_numeric_storyline_policy_is_an_error(key, value):
    from research_tree_support import EVERGIVEN
    from researchguard.trace.evaluator import evaluate_model
    from researchguard.trace.loader import load_model
    model = load_model(EVERGIVEN / "trace.yaml")
    model.metadata["storyline_depth_policy"] = {key: value}
    with pytest.raises(ValueError, match=key):
        evaluate_model(model, include_storyline_depth=True)


@pytest.mark.parametrize("policy,field", [("strict", "storyline_depth_policy"), (["count"], "storyline_depth_policy"),
                                          ({"minimum_per_trace_qualified_event_count": -2}, "minimum_per_trace_qualified_event_count"),
                                          ({"maximum_per_trace_unqualified_run": 2.5}, "maximum_per_trace_unqualified_run"),
                                          ({"maximum_per_trace_unqualified_run": True}, "maximum_per_trace_unqualified_run"),
                                          ({"minimum_per_trace_qualified_event_ratio": 7}, "minimum_per_trace_qualified_event_ratio"),
                                          ({"minimum_per_trace_qualified_event_ratio": float("nan")}, "minimum_per_trace_qualified_event_ratio")])
def test_a_storyline_policy_that_is_not_a_mapping_or_out_of_range_is_an_error(policy, field):
    from research_tree_support import EVERGIVEN
    from researchguard.trace.evaluator import evaluate_model
    from researchguard.trace.loader import load_model
    from researchguard.trace.storyline_depth import evaluate_storyline_depth
    model = load_model(EVERGIVEN / "trace.yaml")
    model.metadata["storyline_depth_policy"] = policy
    with pytest.raises(ValueError, match=field):
        evaluate_model(model, include_storyline_depth=True)
    with pytest.raises(ValueError, match=field):
        evaluate_storyline_depth(model, evaluate_model(model))


@pytest.mark.parametrize("value", [1.7, -3, float("nan"), float("inf")])
def test_a_source_score_outside_zero_to_one_is_a_schema_error(value):
    from researchguard.source.schema import BeliefState, SchemaError
    with pytest.raises(SchemaError, match="source_reliability"):
        BeliefState.from_dict({"sources": [{"source_id": "s", "source_reliability": value}]})
    with pytest.raises(SchemaError, match="importance"):
        BeliefState.from_dict({"gaps": [{"gap_id": "g", "importance": value}]})


def test_qualification_thresholds_must_be_a_mapping_of_scores():
    from researchguard.source.schema import BeliefState, SchemaError
    from researchguard.source.update import _qualification_thresholds
    assert _qualification_thresholds(BeliefState())["source_reliability"] == 0.5
    with pytest.raises(SchemaError, match="qualification_thresholds"):
        _qualification_thresholds(BeliefState(metadata={"qualification_thresholds": "strict"}))
    with pytest.raises(SchemaError, match="qualification_thresholds.specificity"):
        _qualification_thresholds(BeliefState(metadata={"qualification_thresholds": {"specificity": 1.5}}))


def test_an_importance_outside_zero_to_one_is_an_error():
    from researchguard.logic.execution_depth import _card_inventory
    from researchguard.logic.loader import load_model_from_dict
    from researchguard.logic.source_library import NodeLink, SourceLibraryError
    from researchguard.logic.synthesis import _item_from_branch
    model = load_model_from_dict({"model": {"id": "m", "model_cards": [{"card_id": "card:a", "node_ids": ["c"], "importance": 5}]},
                                  "nodes": {"c": {"type": "Claim", "text": "A claim"}}, "edges": []})
    with pytest.raises(ValueError, match="importance"):
        _card_inventory(model, ())
    with pytest.raises(ValueError, match="importance"):
        _item_from_branch({"branch_id": "b", "source_id": "s", "importance": 5})
    for value in (5, -1):
        with pytest.raises(SourceLibraryError, match="importance"):
            NodeLink.from_dict({"project_id": "p", "importance": value})


@pytest.mark.parametrize("value", [float("nan"), "inf"])
def test_an_order_index_that_is_not_finite_is_an_error(value):
    from researchguard.logic.structured_artifact import _order_index
    with pytest.raises(ValueError, match="order_index"):
        _order_index("n7", value)


def test_i18n_payload_is_inline_json_or_a_readable_file(tmp_path):
    from researchguard.logic.cli import _load_i18n_payload
    long_inline = json.dumps({"zh": {"title": "x" * 400}})
    assert _load_i18n_payload(long_inline)["zh"]["title"] == "x" * 400
    path = tmp_path / "i18n.json"
    path.write_text('{"zh": {"title": "t"}}', encoding="utf-8")
    assert _load_i18n_payload(str(path)) == {"zh": {"title": "t"}}
    with pytest.raises(FileNotFoundError):
        _load_i18n_payload(str(tmp_path / "missing.json"))


def test_intake_of_a_text_file_that_is_not_utf8_reports_an_error(tmp_path):
    from researchguard.logic import IntakeMaterial, IntakeOptions, intake_materials
    source_file = tmp_path / "notes.txt"
    source_file.write_bytes("Claim: caf\xe9 prices rose.".encode("latin-1"))
    item = intake_materials([IntakeMaterial.file(source_file)], options=IntakeOptions(tmp_path / "library")).materials[0]
    assert item.modeling_status == "error"
    assert "UTF-8" in item.error


def test_a_package_missing_a_project_member_it_names_is_refused(tmp_path):
    from researchguard.logic.source_library import SourceLibraryError
    from researchguard.logic.source_library_io import export_library_package, import_library_package
    from tests.logic.test_source_library_io import _source_with_project
    _, project_id, _ = _source_with_project(tmp_path / "library")
    package = tmp_path / "project.zip"
    export_library_package(tmp_path / "library", package, mode="project", project_id=project_id)
    damaged = tmp_path / "damaged.zip"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(damaged, "w") as target:
        for info in source.infolist():
            if not info.filename.endswith("node_links.json"):
                target.writestr(info, source.read(info.filename))
    with pytest.raises(SourceLibraryError, match="node_links"):
        import_library_package(tmp_path / "target", damaged)


def test_a_source_card_with_an_unreadable_model_says_invalid_model(tmp_path):
    from researchguard.logic import SourceLibrary
    from researchguard.logic.library_viewer import build_source_cards
    source_file = tmp_path / "study.txt"
    source_file.write_text("Study", encoding="utf-8")
    library = SourceLibrary(tmp_path / "library")
    source_id = library.import_source(source_file, title="Study").source.source_id
    library.source_model_path(source_id).parent.mkdir(parents=True, exist_ok=True)
    library.source_model_path(source_id).write_text("nodes: [not, a, mapping]\n", encoding="utf-8")
    card = next(card for card in build_source_cards(tmp_path / "library") if card["source_id"] == source_id)
    assert card["status"] == card["modeling_status"] == "invalid_model"
    assert card["error"]


def test_a_non_numeric_model_card_importance_is_an_error():
    from researchguard.logic.execution_depth import _card_inventory
    from researchguard.logic.loader import load_model_from_dict
    model = load_model_from_dict({"model": {"id": "m", "model_cards": [{"card_id": "card:a", "node_ids": ["c"], "importance": "high"}]},
                                  "nodes": {"c": {"type": "Claim", "text": "A claim"}}, "edges": []})
    with pytest.raises(ValueError, match="importance"):
        _card_inventory(model, ())


def test_a_non_numeric_branch_or_link_importance_is_an_error():
    from researchguard.logic.source_library import NodeLink, SourceLibraryError
    from researchguard.logic.synthesis import _item_from_branch
    assert NodeLink.from_dict({"project_id": "p"}).importance is None
    with pytest.raises(SourceLibraryError, match="importance"):
        NodeLink.from_dict({"project_id": "p", "importance": "high"})
    with pytest.raises(ValueError, match="importance"):
        _item_from_branch({"branch_id": "b", "source_id": "s", "importance": "high"})


def test_a_non_numeric_order_index_is_an_error():
    from researchguard.logic.structured_artifact import _order_index
    assert _order_index("n7", None) == 7.0 and _order_index("n7", "2") == 2.0
    with pytest.raises(ValueError, match="order_index"):
        _order_index("n7", "first")


def test_an_injected_route_failure_fails_status_instead_of_passing(folder, capsys, monkeypatch):
    from researchguard.cli import main

    def broken(model):
        raise ValueError("injected logic failure")

    monkeypatch.setattr("researchguard.research.evaluate_logic", broken)
    assert main(["status", str(folder), "--json"]) == 1
    errors = json.loads(capsys.readouterr().out)["errors"]
    assert "model_invalid:logic: injected logic failure" in errors


# No test may end skipped, expected to fail or cut short: each exits 0 and would hide a swallowed error.

BYPASSES = {
    "function skip inside an except": """
import subprocess
import pytest

def test_it():
    try:
        subprocess.run(["no-such-program-for-researchguard"], check=True)
    except FileNotFoundError:
        pytest.skip("git is unavailable")
""",
    "module skip inside an except": """
import pytest
try:
    import no_such_module_for_researchguard
except ImportError:
    pytest.skip("optional module missing", allow_module_level=True)

def test_it():
    assert False
""",
    "module-level importorskip": """
import pytest
pytest.importorskip("no_such_module_for_researchguard")

def test_it():
    assert False
""",
    "xfail inside an except": """
import pytest

def test_it():
    try:
        int("x")
    except ValueError:
        pytest.xfail("parsing is flaky")
""",
    "xfail marker": """
import pytest

@pytest.mark.xfail(reason="known")
def test_it():
    assert False
""",
    "a skip that only claims a missing platform feature": """
import pytest

def test_it():
    pytest.skip("could not import 'tkinter': No module named 'tkinter'")
""",
    "skipif marker": """
import pytest

@pytest.mark.skipif(True, reason="not here")
def test_it():
    assert False
""",
    "unittest skipTest": """
import unittest

class Case(unittest.TestCase):
    def test_it(self):
        self.skipTest("no network")
""",
    "module-level unittest.SkipTest": """
import unittest
raise unittest.SkipTest("no network")
""",
    "pytest.exit with return code 0": """
import pytest

def test_it():
    try:
        int("x")
    except ValueError:
        pytest.exit("nothing to check here", returncode=0)

def test_later():
    assert False
""",
}


def _run_inner(tmp_path, source):
    import subprocess
    import sys
    shutil.copy(ROOT / "tests" / "conftest.py", tmp_path / "conftest.py")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_inner.py").write_text(source, encoding="utf-8")
    return subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-rA", str(tmp_path)],
                          cwd=tmp_path, capture_output=True, text=True)


@pytest.mark.parametrize("name", sorted(BYPASSES))
def test_no_skip_xfail_or_early_exit_passes_the_run(tmp_path, name):
    result = _run_inner(tmp_path, BYPASSES[name])
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "this suite allows no skip, xfail or early exit" in output, output


def test_a_plain_passing_run_still_passes(tmp_path):
    result = _run_inner(tmp_path, "def test_it():\n    assert True\n")
    assert result.returncode == 0 and "1 passed" in result.stdout, result.stdout + result.stderr
