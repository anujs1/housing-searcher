"""Command-line entry point for the personal housing-group pipeline.

Commands:
  login    open a browser, log in by hand, save your session (run once)
  fetch    load the group with your session and capture its feed responses
  parse    turn captured responses into raw post records
  extract  normalize raw posts into structured listings with Claude
  run      fetch -> parse -> extract in one go

Data lives under HOUSING_SEARCHER_DATA (default: ./data), which is gitignored.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

DATA_DIR = os.environ.get("HOUSING_SEARCHER_DATA", "data")
DEFAULT_GROUP = os.environ.get("HOUSING_SEARCHER_GROUP", "843764532374203")

STATE_PATH = os.path.join(DATA_DIR, "session_state.json")
CAPTURE_PATH = os.path.join(DATA_DIR, "captures.jsonl")
POSTS_PATH = os.path.join(DATA_DIR, "raw_posts.jsonl")
LISTINGS_PATH = os.path.join(DATA_DIR, "listings.jsonl")


def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _write_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False))
            fh.write("\n")


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def cmd_login(args: argparse.Namespace) -> None:
    from .fetch import save_session

    _ensure_data_dir()
    save_session(STATE_PATH)


def cmd_fetch(args: argparse.Namespace) -> None:
    from .fetch import capture_feed

    _ensure_data_dir()
    if not os.path.exists(STATE_PATH):
        raise SystemExit("No saved session. Run 'login' first.")
    capture_feed(
        group_id=args.group,
        state_path=STATE_PATH,
        capture_path=CAPTURE_PATH,
        manual=args.manual,
        scrolls=args.scrolls,
        headless=args.headless,
    )


def cmd_parse(args: argparse.Namespace) -> None:
    from .parse_feed import parse_capture_file

    src = args.captures or CAPTURE_PATH
    if not os.path.exists(src):
        raise SystemExit(f"No capture file at {src}. Run 'fetch' first.")
    posts = parse_capture_file(src)
    _ensure_data_dir()
    _write_jsonl(POSTS_PATH, posts)
    print(f"Parsed {len(posts)} unique post(s) -> {POSTS_PATH}")


def cmd_extract(args: argparse.Namespace) -> None:
    from .extract import DEFAULT_MODEL, extract_all

    src = args.posts or POSTS_PATH
    if not os.path.exists(src):
        raise SystemExit(f"No raw posts at {src}. Run 'parse' first.")
    posts = _read_jsonl(src)
    print(f"Extracting {len(posts)} post(s) with {DEFAULT_MODEL}...")
    listings = extract_all(posts, listings_only=not args.keep_all)
    _ensure_data_dir()
    _write_jsonl(LISTINGS_PATH, listings)
    print(f"Wrote {len(listings)} listing(s) -> {LISTINGS_PATH}")


def cmd_run(args: argparse.Namespace) -> None:
    cmd_fetch(args)
    cmd_parse(args)
    cmd_extract(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="housing-searcher", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_login = sub.add_parser("login", help="log in by hand and save your session")
    p_login.set_defaults(func=cmd_login)

    def add_fetch_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--group", default=DEFAULT_GROUP, help="Facebook group id")
        p.add_argument("--manual", action="store_true", help="you scroll; tool only records")
        p.add_argument("--scrolls", type=int, default=8, help="auto-scroll steps (non-manual)")
        p.add_argument("--headless", action="store_true", help="run without a visible window")

    p_fetch = sub.add_parser("fetch", help="capture the group feed with your session")
    add_fetch_args(p_fetch)
    p_fetch.set_defaults(func=cmd_fetch)

    p_parse = sub.add_parser("parse", help="turn captured responses into raw posts")
    p_parse.add_argument("--captures", help=f"capture file (default {CAPTURE_PATH})")
    p_parse.set_defaults(func=cmd_parse)

    p_extract = sub.add_parser("extract", help="normalize raw posts into listings")
    p_extract.add_argument("--posts", help=f"raw posts file (default {POSTS_PATH})")
    p_extract.add_argument("--keep-all", action="store_true", help="keep non-housing posts too")
    p_extract.set_defaults(func=cmd_extract)

    p_run = sub.add_parser("run", help="fetch + parse + extract")
    add_fetch_args(p_run)
    p_run.add_argument("--captures", help=argparse.SUPPRESS)
    p_run.add_argument("--posts", help=argparse.SUPPRESS)
    p_run.add_argument("--keep-all", action="store_true", help="keep non-housing posts too")
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
