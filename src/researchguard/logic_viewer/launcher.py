from __future__ import annotations

import argparse
import json
import sys

from .software_update import startup_block_message
from .software_update import load_update_state, update_badge_label
from .store import resolve_repo_root
from .ui_data import build_card_detail_payload, build_overview_payload, build_route_view_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open the read-only LogicGuard project library viewer.")
    parser.add_argument("--library-root", "--repo-root", dest="library_root", default="auto")
    parser.add_argument("--route", default="", help="Initial project route for check output.")
    parser.add_argument("--source-id", default="", help="Source id to check detail/graph payload.")
    parser.add_argument("--language", default="", choices=["", "en", "zh-CN"])
    parser.add_argument("--check", action="store_true", help="Validate viewer data without opening a desktop window.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        library_root = resolve_repo_root(args.library_root)
    except FileNotFoundError as exc:
        _show_startup_error(str(exc))
        raise SystemExit(2) from exc

    language = args.language or "en"
    if args.check:
        route_payload = build_route_view_payload(library_root, route=args.route, language=language)
        overview = build_overview_payload(library_root)
        detail = build_card_detail_payload(library_root, args.source_id, language=language) if args.source_id else None
        update_state = load_update_state(library_root)
        print(
            json.dumps(
                {
                    "ok": True,
                    "library_root": str(library_root),
                    "source_count": overview["entry_count"],
                    "route": route_payload["route_label"],
                    "deck_count": len(route_payload["deck"]),
                    "language": language,
                    "first_source_title": route_payload["deck"][0]["title"] if route_payload["deck"] else "",
                    "detail_graph_nodes": len((detail or {}).get("graph", {}).get("nodes", [])),
                    "update_status": update_state,
                    "update_label": update_badge_label(update_state, language),
                    "team_sync_controls": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    update_message = startup_block_message(library_root, language=language)
    if update_message:
        _show_startup_error(update_message)
        raise SystemExit(3)

    from .desktop_app import run_desktop_app

    run_desktop_app(library_root, language=language)


def _show_startup_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("LogicGuard Library Viewer", message)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)
