"""One route per function: every error handler in the product is listed with what it does.

The inventory is computed from the source, not written by the code's author: a handler whose
body does not end in ``raise`` must appear in HANDLED with the reason the error is still visible,
and a listed handler that no longer exists fails too, so the list cannot go stale.
The tests below it each inject an error into a route that used to hide it and require a failure.
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

REPORTED_CLI = "command boundary: prints the error as JSON or text and returns a nonzero exit code"
REPORTED_ROW = "the error is recorded as an error row of the result the caller reads"
GUI = "desktop viewer only: a missing window-system feature changes the display, never a result"

# (file, enclosing function, caught types) -> (count, reason)
HANDLED = {
    ("experiment/cli.py", "main", "(KeyError, ValueError, TypeError)"): (1, REPORTED_CLI),
    ("logic/cli.py", "main", "Exception"): (1, REPORTED_CLI + "; --debug re-raises it"),
    ("logic/cli.py", "_cmd_library_viewer", "ImportError"): (1, REPORTED_CLI + "; names the missing viewer extra"),
    ("source/cli.py", "main", "Exception"): (1, REPORTED_CLI),
    ("source/cli.py", "run", "(ValueError, TypeError, KeyError)"): (1, REPORTED_CLI + "; nothing is written"),
    ("trace/cli.py", "cmd_validate", "(OSError, SchemaError, ValueError, InferenceError)"): (1, REPORTED_CLI),
    ("trace/cli.py", "cmd_evaluate", "(OSError, SchemaError, ValueError, InferenceError)"): (1, REPORTED_CLI),
    ("trace/cli.py", "cmd_depth", "(OSError, SchemaError, ValueError, InferenceError)"): (1, REPORTED_CLI),
    ("trace/cli.py", "cmd_diagnose", "(OSError, SchemaError, ValueError, InferenceError)"): (1, REPORTED_CLI),
    ("trace/cli.py", "cmd_gaps", "(OSError, SchemaError, ValueError, InferenceError)"): (1, REPORTED_CLI),
    ("trace/cli.py", "cmd_report", "(OSError, SchemaError, ValueError, InferenceError)"): (1, REPORTED_CLI),
    ("trace/cli.py", "cmd_export_logicguard", "(OSError, SchemaError, ValueError, InferenceError)"): (1, REPORTED_CLI),
    ("trace/cli.py", "cmd_compare", "(OSError, SchemaError, ValueError, InferenceError)"): (1, REPORTED_CLI),
    ("trace/cli.py", "cmd_simulate", "(OSError, SchemaError, ValueError, InferenceError)"): (2, REPORTED_CLI),
    ("trace/cli.py", "cmd_iterate", "(OSError, SchemaError, ValueError, InferenceError, TaskIterationError)"): (1, REPORTED_CLI),
    ("trace/cli.py", "cmd_library", "(OSError, ValueError, case_library.LibraryError, SchemaError)"): (1, REPORTED_CLI),
    ("research.py", "sync_main", "(OSError, ValueError, TypeError, yaml.YAMLError)"): (1, REPORTED_CLI + "; nothing is written"),
    ("research.py", "status_main", "(OSError, ValueError, TypeError, yaml.YAMLError)"): (1, REPORTED_CLI + "; names a ResearchGuard defect apart from a bad research.yaml"),
    ("research.py", "load_research", "(OSError, ValueError, TypeError, KeyError, yaml.YAMLError)"): (1, REPORTED_ROW + " (model_invalid:<route>), and status exits 1"),
    ("research.py", "load_research", "(OSError, ValueError, TypeError, KeyError)"): (1, REPORTED_ROW + " (model_invalid:experiment_observations), and status exits 1"),
    ("research.py", "research_status", "(ValueError, TypeError, KeyError, ArithmeticError)"): (3, REPORTED_ROW + " (model_invalid:<route>|ablation|verdict), and status exits 1"),
    ("logic/validator.py", "validate_model", "ProvenanceError"): (1, REPORTED_ROW + " of the validation"),
    ("logic/validator.py", "source_model_provenance_problems", "ProvenanceError"): (1, REPORTED_ROW + " of the source-model check"),
    ("logic/synthesis.py", "_source_library_binding_gaps", "Exception"): (4, "the failure becomes a named *_unresolved gap that blocks the synthesis candidate"),
    ("logic/source_intake.py", "_intake_one", "SourceLibraryError"): (1, "the material is reported skipped with the error text; nothing is saved for it"),
    ("logic/source_intake.py", "_intake_one", "Exception"): (1, "the saved source is reported with modeling_status error and the error text"),
    ("logic/library_viewer.py", "build_source_graph_payload", "ModelLoadError"): (1, "the payload says status invalid_model with the error text"),
    ("logic/library_viewer.py", "_source_card", "ModelLoadError"): (1, "the card says status invalid_model with the error text"),
    ("logic_viewer/launcher.py", "_show_startup_error", "Exception"): (1, "the startup error is printed to stderr when no dialog can open; the launcher still exits 2"),
    ("logic_viewer/desktop_app.py", "_enable_windows_dpi_awareness", "(AttributeError, OSError, ValueError)"): (2, GUI + " (no Windows DPI call outside Windows)"),
    ("logic_viewer/desktop_app.py", "_confidence_label", "(TypeError, ValueError)"): (1, GUI + " (an unreadable confidence is shown as its raw text)"),
    ("logic_viewer/desktop_app.py", "_skill_dependency_count", "(TypeError, ValueError)"): (1, GUI + " (an unreadable count is shown as 0)"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._maximize_initial_window", "tk.TclError"): (1, GUI),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._detect_unit_scale", "tk.TclError"): (1, GUI),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._detect_font_scale", "tk.TclError"): (1, GUI),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._load_image_assets", "tk.TclError"): (1, GUI + " (text labels replace icons)"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._load_image_assets", "(OSError, tk.TclError)"): (1, GUI + " (text labels replace icons)"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._export_library_package", "Exception"): (1, "the error is shown in an error dialog and nothing is exported"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._import_library_package", "Exception"): (1, "the error is shown in an error dialog and nothing is imported"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._dissolve_project", "Exception"): (1, "the error is shown in an error dialog and the project stays"),
    ("logic_viewer/desktop_app.py", "KbDesktopApp._open_settings_window.configure_combo_popup", "tk.TclError"): (1, GUI),
}


def _handlers():
    found = Counter()
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or isinstance(node.body[-1], ast.Raise):
                continue
            names, owner = [], parents.get(node)
            while owner is not None:
                if isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.append(owner.name)
                owner = parents.get(owner)
            key = (path.relative_to(SRC).as_posix(), ".".join(reversed(names)) or "<module>",
                   ast.unparse(node.type) if node.type else "<bare>")
            found[key] += 1
    return found


def test_every_non_raising_handler_is_listed_with_its_reason():
    found = _handlers()
    listed = Counter({key: count for key, (count, _) in HANDLED.items()})
    unlisted = sorted(f"{key} x{count - listed[key]}" for key, count in found.items() if count > listed[key])
    stale = sorted(f"{key} x{count - found[key]}" for key, count in listed.items() if count > found[key])
    assert not unlisted, "handlers that do not raise and are not listed (raise visibly, or list why the error stays visible):\n" + "\n".join(unlisted)
    assert not stale, "listed handlers that no longer exist:\n" + "\n".join(stale)
    assert all(reason.strip() for _, reason in HANDLED.values())


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


# A test may only skip for an absent platform feature, never because a handler swallowed an error.

def test_a_skip_for_any_other_reason_fails_the_run(tmp_path):
    import subprocess
    import sys
    shutil.copy(ROOT / "tests" / "conftest.py", tmp_path / "conftest.py")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (tmp_path / "test_inner.py").write_text("""
import subprocess
import pytest

def test_swallowed_error_turned_into_a_skip():
    try:
        subprocess.run(["no-such-program-for-researchguard"], check=True)
    except FileNotFoundError:
        pytest.skip("git is unavailable")

def test_absent_tkinter_may_skip():
    pytest.skip("could not import 'tkinter': No module named 'tkinter'")
""", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-rA", str(tmp_path)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "1 failed, 1 skipped" in result.stdout, result.stdout
    assert "skipped for a reason that is not an absent platform feature: git is unavailable" in result.stdout, result.stdout
