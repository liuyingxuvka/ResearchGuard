"""One route per function: every error handler in the product is listed with the documented
behaviour it serves, and the handler's own code must have that behaviour's shape.

The inventory is computed from the source of src/ and scripts/: every ``except`` that does not
re-raise (or that returns, breaks or continues before it does), every ``finally`` that returns, every
use of ``contextlib.suppress`` however it is imported or entered, every ExitStack exit callback and
every ``__exit__`` that returns a true value. Each must appear in HANDLED under one of the CONTRACTS,
the sentences of README.md "Errors", and the test then checks the handler's code against its sentence
(see ``_shapes``): a command, found from the entry points and what they dispatch to, prints a value
that carries the error and returns a nonzero code; a result handler puts a value that carries the
error into what its function returns before any way out; a dialog shows it; a display fallback only
guards window-system calls in the viewer. A listed handler that no longer exists fails too, so the
list cannot go stale. This reads the shape of the code; it is not a proof. The tests below it each
inject an error into a route that used to hide it and require a failure.
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
    "row": "A check or library step that fails puts the error into the result it returns, as a named error, gap, finding or error field that names the error, so the caller sees it.",
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

PRINTERS = {"print", "_print_json", "_json_out"}
STREAMS = {"stderr", "stdout"}
ROW_SINKS = {"append", "extend", "add", "insert", "update", "setdefault"}
WINDOW_NAMES = {"tk", "ctypes", "ImageTk", "Image", "messagebox"}
WINDOW_ATTRIBUTES = {"tk", "winfo_fpixels", "state", "iconphoto", "PhotoImage"}
DISPLAY_TYPES = {"tk.TclError", "OSError", "AttributeError", "ValueError", "ImportError"}
EXITS = (ast.Return, ast.Break, ast.Continue)
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


def _own_nodes(statements):
    """Every node of these statements, without the bodies of nested functions and classes."""
    stack = list(statements)
    while stack:
        node = stack.pop()
        yield node
        stack.extend(child for child in ast.iter_child_nodes(node)
                     if not isinstance(child, (*FUNCTIONS, ast.ClassDef, ast.Lambda)))


def _callee(call):
    return call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")


def _carried(node):
    """The names whose value flows into what ``node`` evaluates to; a name that is only tested is not carried."""
    if node is None or isinstance(node, (ast.Constant, ast.Compare, ast.UnaryOp, ast.Lambda)):
        return set()
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.IfExp):  # both branches carry it, or the test is the value and its true branch carries it
        carried = _carried(node.body) & _carried(node.orelse)
        if isinstance(node.test, ast.Name) and node.test.id in _carried(node.body):
            carried.add(node.test.id)
        return carried
    if isinstance(node, ast.BoolOp):
        return set.intersection(*(_carried(value) for value in node.values))
    if isinstance(node, ast.Call):
        parts = [*node.args, *(keyword.value for keyword in node.keywords)]
        if isinstance(node.func, ast.Attribute):
            parts.append(node.func.value)  # str(exc).strip(), "{}".format(exc)
        return set().union(*(_carried(part) for part in parts))
    if isinstance(node, (ast.Attribute, ast.Subscript, ast.Starred, ast.FormattedValue, ast.NamedExpr)):
        return _carried(node.value)
    if isinstance(node, ast.BinOp):
        return _carried(node.left) | _carried(node.right)
    if isinstance(node, ast.JoinedStr):
        return set().union(*(_carried(value) for value in node.values))
    if isinstance(node, ast.Dict):
        return set().union(*(_carried(value) for value in (*node.keys, *node.values) if value is not None))
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return set().union(*(_carried(item) for item in node.elts))
    return set()


def _labelled(node):
    """The names ``node`` carries into a place named as an error: an ``error`` key or keyword, or ``skip_reason``."""
    def named(label):
        return isinstance(label, str) and ("error" in label or label == "skip_reason")

    if isinstance(node, ast.Dict):
        return set().union(*((_carried(value) if isinstance(key, ast.Constant) and named(key.value) else _labelled(value))
                             for key, value in zip(node.keys, node.values)))
    if isinstance(node, ast.Call):
        return set().union(*(_labelled(arg) for arg in node.args),
                           *((_carried(item.value) if named(item.arg) else _labelled(item.value)) for item in node.keywords))
    if isinstance(node, ast.IfExp):
        labelled = _labelled(node.body) & _labelled(node.orelse)
        if isinstance(node.test, ast.Name) and node.test.id in _labelled(node.body):
            labelled.add(node.test.id)
        return labelled
    if isinstance(node, (ast.List, ast.Tuple)):
        return set().union(*(_labelled(item) for item in node.elts))
    if isinstance(node, ast.Starred):
        return _labelled(node.value)
    return set()


def _root(node):
    """The name an attribute, item or method chain hangs on (``problems`` for ``problems['errors'].append``)."""
    while isinstance(node, (ast.Attribute, ast.Subscript, ast.Call)):
        node = node.func if isinstance(node, ast.Call) else node.value
    return node.id if isinstance(node, ast.Name) else None


def _tainted(body, name):
    """The exception name and every name the handler assigns from a value that carries it."""
    tainted = {name}
    while True:
        new = {item.id for node in _own_nodes(body)
               if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and _carried(node.value) & tainted
               for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
               for item in ast.walk(target) if isinstance(item, ast.Name)} - tainted
        if not new:
            return tainted
        tainted |= new


def _results(function):
    """What a function hands back: the names its returns carry in an error field, and the names that hold
    its result (names its returns carry, and the collections a caller passed in)."""
    if function is None:
        return set(), set()
    values = [node.value for node in _own_nodes(function.body) if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom))]
    arguments = function.args
    parameters = {item.arg for item in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                                        arguments.vararg, arguments.kwarg) if item is not None} - {"self", "cls"}
    return set().union(*map(_labelled, values)), set().union(*map(_carried, values)) | parameters


def _first(body, test):
    """Index of the first top-level statement that passes ``test``, if no exit comes before it."""
    for index, statement in enumerate(body):
        if test(statement):
            return index
        if any(isinstance(node, EXITS) for node in _own_nodes([statement])):
            return None
    return None


def _touches_window(statements):
    """Every statement uses the window system, directly or through a name bound from it in this block."""
    names = set(WINDOW_NAMES)
    for statement in statements:
        nodes = list(_own_nodes([statement]))
        if not any((isinstance(node, ast.Name) and node.id in names)
                   or (isinstance(node, ast.Attribute) and node.attr in WINDOW_ATTRIBUTES)
                   or (isinstance(node, (ast.Import, ast.ImportFrom)) and "tkinter" in ast.unparse(node))
                   for node in nodes):
            return False
        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names |= {item.id for target in targets for item in ast.walk(target) if isinstance(item, ast.Name)}
            elif isinstance(node, ast.withitem) and node.optional_vars is not None:
                names |= {item.id for item in ast.walk(node.optional_vars) if isinstance(item, ast.Name)}
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names |= {alias.asname or alias.name.split(".")[0] for alias in node.names}
    return bool(statements)


def _shapes(row):
    """The contracts a handler's own code satisfies, computed from its AST.

    exit: in a command (a function whose return value becomes the process exit code), the handler first
      prints a value that carries the error, then every way out of it returns a constant code of 1 or more.
    row: before any way out, the handler puts a value that carries the error into the result: it returns
      it, assigns it to a name the function returns, or adds it to a collection the function returns or
      was given. A value that only tests the error, or a list or dict nobody holds, does not count.
    dialog: in the viewer, before any way out, the handler shows a value that carries the error in showerror.
    display: in the viewer, every statement it guards uses the window system and it catches only
      window-system error types.
    """
    kind, path, body = row["kind"], row["path"], row["body"]
    shapes = set()
    if kind == "except" and row["name"] is not None:
        tainted = _tainted(body, row["name"])
        returned, holders = _results(row["owner"])

        def carries(node):
            return bool(_carried(node) & tainted)

        def call_carries(call):
            return any(carries(part) for part in (*call.args, *(keyword.value for keyword in call.keywords)))

        def printed(statement):
            call = statement.value if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call) else None
            stream = (call is not None and isinstance(call.func, ast.Attribute) and call.func.attr == "write"
                      and isinstance(call.func.value, ast.Attribute) and call.func.value.attr in STREAMS)
            return call is not None and (_callee(call) in PRINTERS or stream) and call_carries(call)

        def recorded(statement):
            if isinstance(statement, ast.Return):
                return bool(_labelled(statement.value) & tainted)
            if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
                call = statement.value
                return (isinstance(call.func, ast.Attribute) and call.func.attr in ROW_SINKS
                        and _root(call.func.value) in holders and call_carries(call))
            if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and carries(statement.value):
                targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                return any((isinstance(target, ast.Name) and target.id in returned)
                           or (isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant)
                               and "error" in str(target.slice.value) and _root(target) in holders)
                           or (isinstance(target, ast.Attribute) and "error" in target.attr and _root(target) in holders)
                           or (isinstance(statement, ast.AugAssign) and isinstance(target, ast.Name) and target.id in holders)
                           for target in targets)
            return False

        def shown(statement):
            return (isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
                    and _callee(statement.value) == "showerror" and call_carries(statement.value))

        exits = [node for node in _own_nodes(body) if isinstance(node, EXITS)]
        codes = all(isinstance(node, ast.Return) and isinstance(node.value, ast.Constant)
                    and type(node.value.value) is int and node.value.value >= 1 for node in exits)
        if row["command"] and _first(body, printed) is not None and codes and isinstance(body[-1], ast.Return):
            shapes.add("exit")
        if _first(body, recorded) is not None:
            shapes.add("row")
        if path.startswith("logic_viewer/") and _first(body, shown) is not None:
            shapes.add("dialog")
    types = {part.strip() for part in row["caught"].strip("()").split(",")}
    if (kind in {"except", "suppress"} and path.startswith("logic_viewer/") and types <= DISPLAY_TYPES
            and _touches_window(row["guarded"])):
        shapes.add("display")
    return shapes


def _module(path):
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return tuple(parts) if parts[:1] == ["scripts"] else ("researchguard", *parts)


def _defs(tree):
    return {node.name: node for node in tree.body if isinstance(node, FUNCTIONS)}


def _resolve(trees, path, scope, name):
    """The (file, function) pairs that ``name`` can mean inside ``scope`` (a function, or None for the module).

    A function may import the same name in several branches; each import is one meaning.
    """
    meanings = set()
    for places in ([*_own_nodes(scope.body)] if scope is not None else [], trees[path].body):
        for node in places:
            if not isinstance(node, ast.ImportFrom):
                continue
            for alias in node.names:
                if (alias.asname or alias.name) != name:
                    continue
                if node.level:
                    own = _module(path)
                    package = own[: len(own) - (0 if path.endswith("__init__.py") else 1) - (node.level - 1)]
                    module = (*package, *(node.module.split(".") if node.module else ()))
                else:
                    module = tuple((node.module or "").split("."))
                target = next((candidate for candidate in trees if _module(candidate) == module), None)
                if target is not None and alias.name in _defs(trees[target]):
                    meanings.add((target, alias.name))
        if meanings:
            return meanings
    return {(path, name)} if name in _defs(trees[path]) else set()


def _loop_values(tree, name):
    """``name`` itself, or, when a for loop binds it from a written-out list, every name in that list."""
    values = {name}
    for node in ast.walk(tree):
        if (isinstance(node, ast.For) and any(isinstance(item, ast.Name) and item.id == name for item in ast.walk(node.target))
                and isinstance(node.iter, (ast.List, ast.Tuple))):
            values |= {item.id for item in ast.walk(node.iter) if isinstance(item, ast.Name)}
    return values


def command_functions(trees, entries):
    """Functions whose return value becomes the process exit code.

    They are the entry points, the functions passed to SystemExit or sys.exit, and whatever a command
    returns the result of: a function it calls by name, the handlers set_defaults registers when it
    returns ``args.<name>(args)``, and the functions a factory returns when it returns ``factory(...)(...)``.
    """
    commands = set(entries)
    dispatch = {path: {} for path in trees}
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            exit_call = _callee(node) == "SystemExit" or (isinstance(node.func, ast.Attribute) and node.func.attr == "exit"
                                                          and getattr(node.func.value, "id", "") == "sys")
            if exit_call:
                for arg in node.args:
                    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
                        commands |= _resolve(trees, path, None, arg.func.id)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "set_defaults":
                for keyword in node.keywords:
                    if isinstance(keyword.value, ast.Name):
                        dispatch[path].setdefault(keyword.arg, set()).update(_loop_values(tree, keyword.value.id))
    queue = list(commands)
    while queue:
        path, name = queue.pop()
        function = _defs(trees[path]).get(name) if path in trees else None
        if function is None:
            continue
        found = set()
        for node in _own_nodes(function.body):
            value = node.value if isinstance(node, ast.Return) else None
            while isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "int" and len(value.args) == 1:
                value = value.args[0]
            if not isinstance(value, ast.Call):
                continue
            if isinstance(value.func, ast.Name):
                found |= _resolve(trees, path, function, value.func.id)
            elif isinstance(value.func, ast.Attribute):
                for item in dispatch[path].get(value.func.attr, ()):
                    found |= _resolve(trees, path, None, item)
            elif isinstance(value.func, ast.Call) and isinstance(value.func.func, ast.Name):
                for factory_path, factory_name in _resolve(trees, path, function, value.func.func.id):
                    made = _defs(trees[factory_path])[factory_name]
                    for item in _own_nodes(made.body):
                        if isinstance(item, ast.Return) and isinstance(item.value, ast.Name):
                            found |= _resolve(trees, factory_path, made, item.value.id)
        for item in found - commands:
            commands.add(item)
            queue.append(item)
    return commands


def _scan(tree, path):
    """Every place in one file that can end an error without raising it."""
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def owner(node):
        names, function, parent = [], None, parents.get(node)
        while parent is not None:
            if isinstance(parent, (*FUNCTIONS, ast.ClassDef)):
                names.append(parent.name)
                if function is None and isinstance(parent, FUNCTIONS):
                    function = parent
            parent = parents.get(parent)
        return ".".join(reversed(names)) or "<module>", function

    def row(kind, node, name, caught, body, guarded):
        qualified, function = owner(node)
        return {"kind": kind, "path": path, "function": qualified, "owner": function, "name": name,
                "caught": caught, "body": body, "guarded": guarded}

    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module == "contextlib"]
    quiet = {alias.asname or alias.name for node in imports for alias in node.names if alias.name in {"suppress", "*"}}
    quiet |= {"suppress"} if "*" in quiet else set()
    uses_contextlib = bool(imports) or any(isinstance(node, ast.Import) and any(alias.name == "contextlib" for alias in node.names)
                                           for node in ast.walk(tree))
    with_items = {id(item.context_expr.func): (item.context_expr, statement) for statement in ast.walk(tree)
                  if isinstance(statement, (ast.With, ast.AsyncWith)) for item in statement.items
                  if isinstance(item.context_expr, ast.Call)}
    rows = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            for handler in node.handlers:
                exits = [item for item in _own_nodes(handler.body) if isinstance(item, EXITS)]
                if isinstance(handler.body[-1], ast.Raise) and not exits:
                    continue
                rows.append(row("except", handler, handler.name, ast.unparse(handler.type) if handler.type else "<bare>",
                                handler.body, node.body))
            if any(isinstance(item, EXITS) for item in _own_nodes(node.finalbody)):
                rows.append(row("finally", node, None, "finally", node.finalbody, node.body))
        names_suppress = ((isinstance(node, ast.Name) and node.id in quiet and isinstance(node.ctx, ast.Load))
                          or (isinstance(node, ast.Attribute) and node.attr == "suppress")
                          or (isinstance(node, ast.Constant) and node.value == "suppress"))  # getattr, __dict__[...]
        if names_suppress:  # however suppress is named or reached, and whether or not a with statement enters it
            call, statement = with_items.get(id(node), (None, None))
            caught = ", ".join(ast.unparse(arg) for arg in call.args) or "<none>" if call is not None else f"<{ast.unparse(node)}>"
            rows.append(row("suppress", node, None, caught, [], statement.body if statement is not None else []))
        if (uses_contextlib and isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"push", "push_async_exit"}):
            rows.append(row("exit callback", node, None, f"<{ast.unparse(node)}>", [], []))
        if isinstance(node, FUNCTIONS) and node.name in {"__exit__", "__aexit__"}:
            kept = [item for item in _own_nodes(node.body) if isinstance(item, ast.Return) and item.value is not None
                    and not (isinstance(item.value, ast.Constant) and item.value.value in (None, False))]
            if kept:
                rows.append(row("exit method", kept[0], None, node.name, [], []))
    return rows


def inventory(texts, entries=frozenset()):
    """Every handler in these files that does not re-raise, with what the contract checks need."""
    trees = {path: ast.parse(text) for path, text in texts.items()}
    commands = command_functions(trees, entries)
    rows = [item for path, tree in trees.items() for item in _scan(tree, path)]
    for item in rows:
        item["command"] = (item["path"], item["function"]) in commands
    return rows


def handlers_in(text, path):
    return inventory({path: text})


def _entry_points():
    import tomllib
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]
    return {("/".join(target.split(":")[0].split(".")[1:]) + ".py", target.split(":")[1]) for target in scripts.values()}


def _handlers():
    texts = {prefix + path.relative_to(base).as_posix(): path.read_text(encoding="utf-8")
             for base, prefix in SCANNED.items() for path in sorted(base.rglob("*.py"))}
    return inventory(texts, _entry_points())


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
    # Review round 2: each of these was accepted under the listing in brackets.
    "error kept in a local the function never returns [row]":
        "def licence(x):\n    try:\n        return int(x)\n    except Exception as exc:\n        error = exc\n        return 'licence open'\n",
    "error appended to a list nobody holds [row]":
        "def licence(x):\n    try:\n        return int(x)\n    except Exception as exc:\n        [].append(exc)\n        return 'licence open'\n",
    "error put in a dict that is thrown away [row]":
        "def licence(x):\n    try:\n        return int(x)\n    except Exception as exc:\n        {'error': exc}\n        return 'licence open'\n",
    "error only tested, never carried [row]":
        "def licence(x):\n    try:\n        return int(x)\n    except Exception as exc:\n        return 'open' if exc else 'closed'\n",
    "error stored on the object, default returned [row]":
        "class Card:\n    def licence(self, x):\n        try:\n            return int(x)\n        except Exception as exc:\n            self.error = exc\n            return 0\n",
    "default returned before the error is recorded [row]":
        "def check(x, errors):\n    try:\n        return int(x)\n    except ValueError as exc:\n        if x:\n            return 0\n        errors.append(str(exc))\n",
    "print and exit code in a helper that is no command [exit]":
        "def helper(x):\n    try:\n        return int(x)\n    except ValueError as exc:\n        print(exc)\n        return 1\n",
    "suppress imported under another name":
        "from contextlib import suppress as quiet\ndef f(x):\n    with quiet(Exception):\n        return int(x)\n    return 0\n",
    "suppress fetched by name":
        "import contextlib\ndef f(x):\n    quiet = getattr(contextlib, 'suppress')\n    with quiet(ValueError):\n        return int(x)\n",
    "suppress entered through an ExitStack":
        "import contextlib\ndef f(x):\n    with contextlib.ExitStack() as stack:\n        stack.enter_context(contextlib.suppress(ValueError))\n        return int(x)\n",
    "exit callback that swallows":
        "import contextlib\ndef f(x):\n    with contextlib.ExitStack() as stack:\n        stack.push(lambda *exc: True)\n        return int(x)\n",
    "context manager whose __exit__ swallows":
        "class Quiet:\n    def __enter__(self):\n        return self\n    def __exit__(self, *exc):\n        return True\n",
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
        "exit": "def main():\n    try:\n        run()\n    except ValueError as exc:\n        print(exc)\n        return 2\n\n\n"
                "if __name__ == '__main__':\n    raise SystemExit(main())\n",
        "row": "def check(errors):\n    try:\n        run()\n    except ValueError as exc:\n        errors.append(f'bad: {exc}')\n",
        "dialog": "def act(self):\n    try:\n        run()\n    except Exception as exc:\n        messagebox.showerror('x', str(exc))\n",
        "display": "def icon(self):\n    try:\n        self.iconphoto(True, tk.PhotoImage(file='a.png'))\n    except tk.TclError:\n        self.icon = None\n",
    }
    for contract, text in good.items():
        rows = handlers_in(text, "logic_viewer/new.py")
        key = (rows[0]["path"], rows[0]["function"], rows[0]["caught"])
        assert inventory_problems(rows, {key: (1, contract)}) == [], contract
    assert handlers_in("def f():\n    try:\n        run()\n    except ValueError:\n        raise\n", "x.py") == []


def test_a_command_is_found_from_the_entry_point_through_dispatch():
    files = {
        "cli.py": "def main(argv):\n    from .member.cli import main as member\n    if argv:\n        return member(argv)\n    return helper()\n\n"
                  "def helper():\n    return 0\n",
        "member/cli.py": "def main(argv):\n    args = parser(argv)\n    return int(args.handler(args))\n\n"
                         "def parser(argv):\n    sub.set_defaults(handler=cmd_show)\n\n"
                         "def cmd_show(args):\n    return 0\n\ndef unrelated(args):\n    return 1\n",
    }
    found = command_functions({path: ast.parse(text) for path, text in files.items()}, {("cli.py", "main")})
    assert found == {("cli.py", "main"), ("cli.py", "helper"), ("member/cli.py", "main"), ("member/cli.py", "cmd_show")}


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


@pytest.mark.parametrize("option,builder", [("--picture", "researchguard.picture.support_picture"),
                                            (None, "researchguard.research.hypothesis_view")])
def test_status_json_prints_the_view_it_was_asked_for_even_when_it_is_empty(folder, capsys, monkeypatch, option, builder):
    from researchguard.cli import main
    monkeypatch.setattr(builder, lambda *args, **kwargs: {})
    main(["status", str(folder), "--hypothesis", "h", *([option] if option else []), "--json"])
    assert json.loads(capsys.readouterr().out) == {}


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
    # Review round 2: os._exit(0) inside a test ended the run with exit code 0.
    "os._exit with code 0 after a failure": """
import os

def test_first():
    assert False

def test_it():
    os._exit(0)
""",
    "the platform module's _exit": """
import importlib
import os

def test_first():
    assert False

def test_it():
    importlib.import_module(os.name)._exit(0)
""",
    "exec into a process that exits 0": """
import os
import sys

def test_first():
    assert False

def test_it():
    os.execv(sys.executable, [sys.executable, "-c", "pass"])
""",
    "a test that clears the failure count": """
def test_first():
    assert False

def test_second(request):
    request.session.testsfailed = 0
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
