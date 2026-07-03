"""Turn raw post text into a normalized housing listing with Claude.

Uses the Messages API with a JSON-schema-constrained response
(``output_config.format``) so every result matches ``LISTING_SCHEMA`` exactly.
The Anthropic SDK is imported lazily so the fetch/parse commands don't require
it or an API key.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .models import LISTING_SCHEMA
from .parse_feed import RawPost

# Default model. Override with HOUSING_SEARCHER_MODEL. Opus 4.8 supports
# structured outputs and is a strong, cost-reasonable default for extraction.
DEFAULT_MODEL = os.environ.get("HOUSING_SEARCHER_MODEL", "claude-opus-4-8")

SYSTEM_PROMPT = (
    "You extract structured housing information from a single post in a San "
    "Francisco Bay Area housing / sublet Facebook group. The post text is "
    "informal and may include emoji, abbreviations, and typos.\n\n"
    "Fill in the schema from what the post actually says. Do not guess or "
    "invent details: if a value is not stated, use null (or an empty list for "
    "list fields). A studio has 0 bedrooms. Rent should be a plain number in "
    "US dollars. Set is_housing_listing to false for posts that are not "
    "offering or seeking housing (group questions, chatter, announcements) — "
    "you may leave the remaining fields null/empty for those."
)


def build_client() -> Any:
    """Construct an Anthropic client (reads ANTHROPIC_API_KEY / ant profile)."""
    import anthropic

    return anthropic.Anthropic()


def _first_text_block(response: Any) -> str:
    for block in response.content:
        if block.type == "text":
            return block.text
    raise ValueError("model returned no text block")


def extract_listing(
    client: Any, post: RawPost, *, model: str = DEFAULT_MODEL, max_tokens: int = 2048
) -> dict[str, Any]:
    """Extract one listing dict from one raw post, preserving provenance."""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": LISTING_SCHEMA}},
        messages=[{"role": "user", "content": post["text"]}],
    )

    if response.stop_reason == "refusal":
        raise RuntimeError("extraction refused by safety classifier")

    listing = json.loads(_first_text_block(response))
    # Attach provenance from the source post so results are traceable.
    listing["raw_text"] = post["text"]
    listing["source_permalink"] = post.get("permalink")
    listing["posted_by"] = post.get("author")
    listing["posted_at"] = post.get("created_at")
    return listing


def extract_all(
    posts: list[RawPost],
    *,
    model: str = DEFAULT_MODEL,
    listings_only: bool = True,
) -> list[dict[str, Any]]:
    """Extract every post. When ``listings_only``, drop non-housing posts."""
    client = build_client()
    results: list[dict[str, Any]] = []
    for i, post in enumerate(posts, 1):
        try:
            listing = extract_listing(client, post, model=model)
        except Exception as exc:  # keep going; one bad post shouldn't stop the run
            print(f"  [{i}/{len(posts)}] skipped: {exc}")
            continue
        if listings_only and not listing.get("is_housing_listing"):
            continue
        results.append(listing)
        print(f"  [{i}/{len(posts)}] extracted: {listing.get('summary') or '(no summary)'}")
    return results
