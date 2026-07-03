"""Data model for a normalized housing listing and the JSON schema used to
constrain Claude's structured-extraction output.

The schema is the single source of truth: every field is required (structured
outputs require it) and optional values are expressed as an ``anyOf`` with
``null`` so the model can say "not stated" without inventing data.
"""

from __future__ import annotations

from typing import Any

# ---- schema building helpers -------------------------------------------------


def _nullable(inner: dict[str, Any]) -> dict[str, Any]:
    """Wrap a schema so the value may also be null (i.e. "not stated")."""
    return {"anyOf": [inner, {"type": "null"}]}


def _enum(values: list[str]) -> dict[str, Any]:
    return {"type": "string", "enum": values}


LISTING_TYPES = ["sublet", "lease_takeover", "room_in_shared", "whole_unit", "other"]
LISTING_INTENTS = ["offering", "wanted", "other"]
RENT_PERIODS = ["month", "week", "night", "other"]

# Order here is the order fields appear to the model; keep the classification
# gate first so it reasons about relevance before pulling details.
_PROPERTIES: dict[str, dict[str, Any]] = {
    "is_housing_listing": {
        "type": "boolean",
        "description": (
            "True if this post is offering or seeking a place to live "
            "(sublet, room, apartment, etc.). False for unrelated chatter, "
            "questions about the group, jokes, or announcements."
        ),
    },
    "listing_intent": {
        **_enum(LISTING_INTENTS),
        "description": (
            "'offering' if the poster has a place available, 'wanted' if they "
            "are looking for one, 'other' otherwise."
        ),
    },
    "listing_type": _nullable(
        {
            **_enum(LISTING_TYPES),
            "description": (
                "sublet = temporary; lease_takeover = permanent handoff; "
                "room_in_shared = a room in an occupied unit; whole_unit = the "
                "entire apartment/house."
            ),
        }
    ),
    "location_text": _nullable(
        {"type": "string", "description": "Verbatim location description from the post."}
    ),
    "neighborhoods": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Named neighborhoods, e.g. ['Mission', 'SoMa']. Empty if none stated.",
    },
    "city": _nullable({"type": "string", "description": "City, e.g. 'San Francisco', 'Oakland'."}),
    "address": _nullable({"type": "string", "description": "Specific street address if stated."}),
    "bedrooms": _nullable(
        {"type": "number", "description": "Number of bedrooms. A studio is 0."}
    ),
    "bathrooms": _nullable({"type": "number", "description": "Number of bathrooms."}),
    "rent_usd": _nullable(
        {"type": "number", "description": "Rent amount in US dollars, as a number (no '$' or commas)."}
    ),
    "rent_period": _nullable(
        {**_enum(RENT_PERIODS), "description": "The period the rent covers."}
    ),
    "available_from": _nullable(
        {
            "type": "string",
            "description": (
                "Move-in date. ISO 8601 (YYYY-MM-DD) when the year is stated or "
                "unambiguous; otherwise the verbatim phrase, e.g. 'July 1'."
            ),
        }
    ),
    "available_to": _nullable(
        {"type": "string", "description": "Move-out / end date, same format rules as available_from."}
    ),
    "lease_term": _nullable(
        {"type": "string", "description": "Length of stay, e.g. '3 months', '1 year', 'flexible'."}
    ),
    "furnished": _nullable({"type": "boolean", "description": "True if furnished, false if unfurnished."}),
    "pets_allowed": _nullable({"type": "boolean", "description": "True if pets are allowed."}),
    "unit_amenities": {
        "type": "array",
        "items": {"type": "string"},
        "description": (
            "Amenities inside the unit, e.g. 'in-unit washer/dryer', "
            "'dishwasher', 'parking', 'private bathroom', 'AC'."
        ),
    },
    "building_amenities": {
        "type": "array",
        "items": {"type": "string"},
        "description": (
            "Shared/building amenities, e.g. 'gym', 'roof deck', 'elevator', "
            "'shared laundry', 'doorman'."
        ),
    },
    "contact": _nullable(
        {"type": "string", "description": "How to reach the poster, if stated (email, phone, 'DM me')."}
    ),
    "summary": _nullable(
        {"type": "string", "description": "One-sentence summary of the listing."}
    ),
}

LISTING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": _PROPERTIES,
    "required": list(_PROPERTIES.keys()),
    "additionalProperties": False,
}

# Field names, handy for consumers building tables/exports.
LISTING_FIELDS: list[str] = list(_PROPERTIES.keys())
