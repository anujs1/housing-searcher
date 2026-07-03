# housing-searcher

A **personal-use** pipeline for turning San Francisco Bay Area housing/sublet
Facebook group posts into structured, searchable listings.

It captures a group's feed using *your own* logged-in browser session, then uses
Claude to normalize each free-text post into fields you can filter and sort on —
location, bedrooms, bathrooms, rent, dates, unit amenities, building amenities,
and more.

---

## ⚠️ Read this first: what this is and isn't

There is **no sanctioned API** for reading a private Facebook group. Meta
deprecated the Groups API in April 2024, and reputable commercial scrapers
refuse authenticated/private-group content. The only thing that can read a
members-only group is a browser session that is already logged in and a member —
i.e. yours.

This tool is built narrowly for that personal case, and it matters that you keep
it there:

- **It's for you, aggregating groups you belong to, for your own housing
  search.** At that scale, the privacy-law exposure (GDPR/CCPA) generally falls
  under the "personal or household activity" exemption, and the CFAA theory is
  weak because you're reading content you're authorized to see.
- **It still violates Meta's Terms of Service** (automated access without
  written permission). The realistic consequence at personal scale is **account
  action** — restriction or a ban — not a lawsuit. That risk is small with
  human-paced, low-volume use, but it is not zero. Many people use a secondary
  account.
- **Don't redistribute, resell, or publish the collected data.** Sharing it
  breaks the personal/household framing that keeps the privacy-law risk low, and
  re-introduces the exposure this design avoids.
- **Don't run it at high volume, with many accounts, or against groups you
  haven't joined.** That's the product-scale scraping this design deliberately
  is *not*, and it's where bans and legal exposure become real.

The lowest-footprint way to run it is `fetch --manual`: you scroll the group
yourself and the tool just records the feed data your own browsing already
loaded — no automated requests beyond opening the page.

This is not legal advice; it's a description of the tradeoffs so you can make an
informed call for your own situation.

---

## How it works

```
login    you log in by hand once  ──►  data/session_state.json  (gitignored, holds live cookies)
fetch    your session opens the group, records its GraphQL feed responses  ──►  data/captures.jsonl
parse    walk the captured JSON for post text + author/permalink/date       ──►  data/raw_posts.jsonl
extract  Claude normalizes each post against a JSON schema                  ──►  data/listings.jsonl
```

Capture and parsing are decoupled: raw responses are saved to disk, so you can
re-parse or re-extract without re-fetching. Facebook renders group feeds from
internal `/api/graphql` responses rather than server HTML; the parser walks that
JSON structure-agnostically (it keys off the stable `{"message": {"text": ...}}`
shape and nearby story metadata), which survives most of Facebook's frequent
layout changes.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m playwright install chromium   # one-time browser download
```

Set your Anthropic credentials for the extract step (`ANTHROPIC_API_KEY`, or an
`ant auth login` profile).

## Usage

```bash
# 1. Log in once — a browser opens; log in by hand, then press Enter.
housing-searcher login

# 2. Capture the group feed. --manual is the lowest-footprint mode:
#    you scroll, it records. (Default auto-scrolls at a human pace.)
housing-searcher fetch --manual
housing-searcher fetch --scrolls 10          # or let it scroll for you

# 3. Parse captured responses into raw posts.
housing-searcher parse

# 4. Normalize into structured listings with Claude.
housing-searcher extract                     # drops non-housing chatter
housing-searcher extract --keep-all          # keep everything, tagged

# Or do fetch + parse + extract in one go:
housing-searcher run --manual
```

The group defaults to the one you configured; override with `--group <id>` or
`HOUSING_SEARCHER_GROUP`. Output goes to `data/` (override with
`HOUSING_SEARCHER_DATA`). The extraction model defaults to `claude-opus-4-8`
(override with `HOUSING_SEARCHER_MODEL`).

### Output

`data/listings.jsonl`, one listing per line:

```json
{
  "is_housing_listing": true,
  "listing_intent": "offering",
  "listing_type": "sublet",
  "location_text": "the Mission",
  "neighborhoods": ["Mission"],
  "city": "San Francisco",
  "bedrooms": 1,
  "bathrooms": 1,
  "rent_usd": 2100,
  "rent_period": "month",
  "available_from": "2024-07-01",
  "available_to": "2024-09-30",
  "furnished": null,
  "pets_allowed": true,
  "unit_amenities": ["in-unit washer/dryer", "dishwasher"],
  "building_amenities": ["gym", "roof deck"],
  "contact": "DM me",
  "summary": "1BR sublet in the Mission, $2100/mo, July–September.",
  "source_permalink": "https://www.facebook.com/groups/.../posts/111/",
  "posted_by": "Jane Doe",
  "posted_at": "2024-07-01"
}
```

Fields not stated in a post are `null` (or `[]`) — the extractor is instructed
not to invent data. Posts that aren't housing listings get
`is_housing_listing: false` and are dropped unless you pass `--keep-all`.

## Development / offline test

The parser is fully testable without touching Facebook, using the committed
fixture:

```bash
PYTHONPATH=src python -m housing_searcher.parse_feed examples/sample_captures.jsonl
```

## Security

`data/session_state.json` holds live Facebook auth cookies. It is gitignored —
never commit it or share it. Treat it like a password.
