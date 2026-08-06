"""Scoped job search backing the match agent's tools.

Kept free of LangChain so it stays unit-testable; ``app/agents/match_tools.py``
is the thin tool wrapper over it.

Results are deliberately *compressed*: a scope can hold ~1000 jobs, and their
full descriptions would be several hundred thousand tokens. Tools return a
one-line view per job (~60 tokens) and the agent pulls full text for the few it
actually wants via ``get_job_detail``.
"""

import json
import re
from typing import Any

import aiosqlite

from app.schemas.match import MatchScope

SUMMARY_CHARS = 90

# Title matches are what users actually mean; body matches are weak evidence.
WEIGHT_TITLE = 6
WEIGHT_CATEGORY = 3
WEIGHT_BODY = 1

_TOKEN_SPLIT = re.compile(r"[\s,，、/|]+")


def tokenize(query: str) -> list[str]:
    """Split a free-text query into search terms."""
    if not query:
        return []
    return [t for t in _TOKEN_SPLIT.split(query.strip()) if len(t) >= 2]


def _decode_location(raw: str | None) -> list[str]:
    """Decode the JSON-array location column."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return [raw]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def compress(row: aiosqlite.Row | dict) -> dict:
    """Reduce a job row to the compact view the agent reasons over.

    ``summary`` is derived from the head of the description rather than stored:
    the column that used to hold it was NULL on every row, so every compact view
    fell through to this same truncation anyway.
    """
    data = dict(row)
    summary = " ".join((data.get("description") or "").split())
    if len(summary) > SUMMARY_CHARS:
        summary = summary[:SUMMARY_CHARS] + "…"

    return {
        "id": data["id"],
        "title": data.get("title", ""),
        "company": data.get("company_id", ""),
        "category": data.get("category", ""),
        "location": _decode_location(data.get("location")),
        "job_type": data.get("job_type") or "",
        "summary": summary,
    }


def expand(row: aiosqlite.Row | dict) -> dict:
    """Return the full job detail."""
    data = dict(row)
    return {
        "id": data["id"],
        "title": data.get("title", ""),
        "company": data.get("company_id", ""),
        "category": data.get("category", ""),
        "location": _decode_location(data.get("location")),
        "job_type": data.get("job_type") or "",
        "posted_date": data.get("posted_date") or "",
        "description": data.get("description") or "",
        "requirements": data.get("requirements") or "",
        "source_url": data.get("source_url") or "",
    }


def _scope_clause(scope: MatchScope) -> tuple[str, list[Any], str]:
    """Build the FROM/WHERE fragment enforcing the turn's scope.

    Returns:
        ``(from_sql, params, where_sql)``.
    """
    if scope.mode == "favorites":
        return (
            "FROM jobs j JOIN favorites f ON f.job_id = j.id",
            [],
            "1 = 1",
        )

    if not scope.company_ids:
        # No company chosen: match nothing rather than silently searching all.
        return ("FROM jobs j", [], "1 = 0")

    placeholders = ",".join("?" for _ in scope.company_ids)
    return ("FROM jobs j", list(scope.company_ids), f"j.company_id IN ({placeholders})")


def _filter_clauses(
    categories: list[str] | None,
    locations: list[str] | None,
    job_types: list[str] | None,
) -> tuple[list[str], list[Any]]:
    """Build hard-filter SQL conditions."""
    conditions: list[str] = []
    params: list[Any] = []

    if categories:
        conditions.append("j.category IN (" + ",".join("?" for _ in categories) + ")")
        params.extend(categories)

    if locations:
        # location is stored as a JSON array, matched the same way the jobs
        # list endpoint does it.
        conditions.append("(" + " OR ".join("j.location LIKE ?" for _ in locations) + ")")
        params.extend(f'%"{loc}"%' for loc in locations)

    if job_types:
        conditions.append("j.job_type IN (" + ",".join("?" for _ in job_types) + ")")
        params.extend(job_types)

    return conditions, params


async def count_jobs(
    db: aiosqlite.Connection,
    scope: MatchScope,
    categories: list[str] | None = None,
    locations: list[str] | None = None,
    job_types: list[str] | None = None,
) -> int:
    """Count jobs matching the scope and hard filters."""
    from_sql, params, scope_where = _scope_clause(scope)
    conditions, filter_params = _filter_clauses(categories, locations, job_types)

    where = " AND ".join([scope_where, *conditions])
    async with db.execute(f"SELECT COUNT(*) {from_sql} WHERE {where}", params + filter_params) as c:
        return (await c.fetchone())[0]


async def search_jobs(
    db: aiosqlite.Connection,
    scope: MatchScope,
    query: str = "",
    categories: list[str] | None = None,
    locations: list[str] | None = None,
    job_types: list[str] | None = None,
    top_k: int = 20,
) -> tuple[list[dict], int]:
    """Search within a scope and return compact job views.

    Hard filters run in SQL; keyword ranking runs in Python over the reduced
    candidate set, which a scope keeps to roughly a thousand rows at most.

    Args:
        db: Open connection.
        scope: The turn's allowed job set.
        query: Free-text terms.
        categories: Restrict to these directions.
        locations: Restrict to these cities.
        job_types: Restrict to these employment types.
        top_k: How many jobs to return.

    Returns:
        ``(jobs, total_matching)`` where ``jobs`` are compact views.
    """
    from_sql, params, scope_where = _scope_clause(scope)
    conditions, filter_params = _filter_clauses(categories, locations, job_types)
    where = " AND ".join([scope_where, *conditions])

    sql = f"""
        SELECT j.id, j.company_id, j.title, j.category, j.location, j.job_type,
               j.description, j.requirements
        {from_sql}
        WHERE {where}
    """
    async with db.execute(sql, params + filter_params) as cursor:
        rows = [dict(r) for r in await cursor.fetchall()]

    total = len(rows)
    terms = tokenize(query)

    if not terms:
        # No keywords: hard filters alone define the result set.
        return [compress(r) for r in rows[:top_k]], total

    scored: list[tuple[int, dict]] = []
    for row in rows:
        title = (row.get("title") or "").lower()
        category = (row.get("category") or "").lower()
        body = " ".join(
            str(row.get(field) or "") for field in ("description", "requirements")
        ).lower()

        score = 0
        for term in terms:
            t = term.lower()
            if t in title:
                score += WEIGHT_TITLE
            if t in category:
                score += WEIGHT_CATEGORY
            if t in body:
                score += WEIGHT_BODY

        if score:
            scored.append((score, row))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [compress(row) for _, row in scored[:top_k]], len(scored)


async def get_job_detail(db: aiosqlite.Connection, job_id: str) -> dict | None:
    """Return one job's full detail."""
    async with db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cursor:
        row = await cursor.fetchone()
        return expand(row) if row else None


async def list_favorites(db: aiosqlite.Connection, company_id: str | None = None) -> list[dict]:
    """Return favourited jobs as compact views."""
    sql = """
        SELECT j.id, j.company_id, j.title, j.category, j.location, j.job_type,
               j.description
        FROM favorites f JOIN jobs j ON j.id = f.job_id
    """
    params: list[Any] = []
    if company_id:
        sql += " WHERE j.company_id = ?"
        params.append(company_id)
    sql += " ORDER BY f.created_at DESC"

    async with db.execute(sql, params) as cursor:
        return [compress(row) for row in await cursor.fetchall()]
