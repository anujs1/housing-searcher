"""Parse captured Facebook GraphQL responses into raw post records.

Facebook renders group feeds from internal ``/api/graphql`` responses rather
than server-rendered HTML, so the fetcher saves those raw response bodies and
this module turns them into ``{text, author, permalink, created_at}`` records.

The approach is deliberately structure-agnostic: Facebook reshuffles its
GraphQL object graph constantly, but the shape of a post message
(``{"message": {"text": "..."}}``) and the story-level metadata around it
(``actors``, ``wwwURL``, ``creation_time``) are stable signals. We recursively
walk the tree, carry the nearest-ancestor metadata down, and snapshot it
whenever we hit message text. This survives most layout changes without edits.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterator

RawPost = dict[str, Any]

_JSONP_PREFIX = "for (;;);"


def iter_json_objects(body: str) -> Iterator[Any]:
    """Yield each JSON object from a GraphQL response body.

    Facebook responses come in three shapes: a single JSON object, several
    objects concatenated with newlines (streamed multipart), or any of those
    behind a ``for (;;);`` anti-JSON-hijacking prefix. Handle all of them.
    """
    body = body.strip()
    if body.startswith(_JSONP_PREFIX):
        body = body[len(_JSONP_PREFIX):].strip()
    if not body:
        return
    # Fast path: the whole body is one JSON document.
    try:
        yield json.loads(body)
        return
    except json.JSONDecodeError:
        pass
    # Streamed multipart: one JSON document per line.
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _epoch_to_iso(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    # Facebook uses seconds; guard against obviously-wrong values.
    if value < 1_000_000_000 or value > 4_000_000_000:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()


def _looks_like_permalink(url: Any) -> bool:
    return isinstance(url, str) and "/posts/" in url or (
        isinstance(url, str) and "/permalink/" in url
    )


def _walk(node: Any, ctx: dict[str, Any], out: list[RawPost]) -> None:
    if isinstance(node, dict):
        ctx = dict(ctx)  # copy so sibling branches don't leak metadata into each other

        # Refine the inherited context with anything this level tells us.
        for key in ("wwwURL", "url", "story_permalink"):
            if _looks_like_permalink(node.get(key)):
                ctx["permalink"] = node[key]
                break
        iso = _epoch_to_iso(node.get("creation_time"))
        if iso:
            ctx["created_at"] = iso
        actors = node.get("actors")
        if isinstance(actors, list) and actors and isinstance(actors[0], dict):
            name = actors[0].get("name")
            if isinstance(name, str) and name.strip():
                ctx["author"] = name.strip()

        # A post body: a message dict carrying real text.
        message = node.get("message")
        if (
            isinstance(message, dict)
            and isinstance(message.get("text"), str)
            and message["text"].strip()
        ):
            out.append(
                {
                    "text": message["text"].strip(),
                    "author": ctx.get("author"),
                    "permalink": ctx.get("permalink"),
                    "created_at": ctx.get("created_at"),
                }
            )

        for value in node.values():
            _walk(value, ctx, out)
    elif isinstance(node, list):
        for item in node:
            _walk(item, ctx, out)


def extract_posts(bodies: list[str]) -> list[RawPost]:
    """Extract deduplicated raw posts from a list of GraphQL response bodies."""
    found: list[RawPost] = []
    for body in bodies:
        for obj in iter_json_objects(body):
            _walk(obj, {"author": None, "permalink": None, "created_at": None}, found)

    # Dedup by post text (the same story appears across paginated responses).
    seen: set[str] = set()
    unique: list[RawPost] = []
    for post in found:
        key = " ".join(post["text"].split())
        if key in seen:
            continue
        seen.add(key)
        unique.append(post)
    return unique


def load_capture_file(path: str) -> list[str]:
    """Load raw response bodies from a capture file.

    The capture file is JSONL where each line is ``{"url": ..., "body": ...}``
    and ``body`` is the raw response text (JSON-encoded, so embedded newlines
    survive the round trip).
    """
    bodies: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            body = record.get("body")
            if isinstance(body, str):
                bodies.append(body)
    return bodies


def parse_capture_file(path: str) -> list[RawPost]:
    return extract_posts(load_capture_file(path))


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: python -m housing_searcher.parse_feed <capture-file.jsonl>", file=sys.stderr)
        raise SystemExit(2)
    posts = parse_capture_file(sys.argv[1])
    print(f"Parsed {len(posts)} unique post(s):\n", file=sys.stderr)
    for post in posts:
        print(json.dumps(post, ensure_ascii=False))
