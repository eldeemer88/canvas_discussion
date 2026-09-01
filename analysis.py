"""Participation statistics and grade assignment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

import numpy as np

from canvas_client import Entry, Person


@dataclass
class Tier:
    """One row of the grading scheme. `z_min is None` marks the catch-all floor."""

    z_min: float | None
    grade: float

    @property
    def is_floor(self) -> bool:
        return self.z_min is None


@dataclass
class Weights:
    """Coefficients of the participation score Y = b1*posts + b2*replies."""

    posts: float = 1.0
    replies: float = 1.0

    @property
    def is_default(self) -> bool:
        return self.posts == 1.0 and self.replies == 1.0

    @property
    def is_degenerate(self) -> bool:
        return self.posts == 0.0 and self.replies == 0.0

    def score(self, posts: float, replies: float) -> float:
        return self.posts * posts + self.replies * replies

    def label(self) -> str:
        return f"Y = {self.posts:g}·posts + {self.replies:g}·replies"


@dataclass
class StudentRow:
    student_id: int
    name: str
    posts: int = 0
    replies: int = 0
    weighted: float = 0.0
    z: float = 0.0
    grade: float = 0.0

    @property
    def total(self) -> int:
        """Raw contribution count, kept for auditability regardless of weights."""
        return self.posts + self.replies


@dataclass
class Stats:
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    n: int = 0
    zero_posts: int = 0
    total_posts: int = 0
    total_replies: int = 0
    # mean/median/std describe the *weighted* score, not the raw totals.
    weights: "Weights" = field(default_factory=lambda: Weights())
    # Test students are removed before any of the above is computed.
    test_students_removed: list[str] = field(default_factory=list)


def parse_weights(raw: dict | None) -> Weights:
    """Read the weight pair from a request body, clamped to sane values."""

    def one(key: str) -> float:
        try:
            v = float((raw or {}).get(key, 1.0))
        except (TypeError, ValueError):
            return 1.0
        # Negative weights would mean "participating hurts you"; not meaningful.
        return min(max(v, 0.0), 100.0)

    return Weights(posts=one("beta_posts"), replies=one("beta_replies"))


def parse_scheme(raw: Iterable[dict] | None) -> list[Tier]:
    """Normalise the client's grading scheme into ordered tiers.

    Tiers are sorted high-to-low by z_min so the first match wins, and exactly
    one floor tier is guaranteed, so every student always receives a grade.
    """
    tiers: list[Tier] = []
    floor: Tier | None = None
    for row in raw or []:
        grade = float(row.get("grade") or 0)
        z_raw = row.get("z_min")
        if z_raw is None or z_raw == "":
            floor = Tier(None, grade)
        else:
            tiers.append(Tier(float(z_raw), grade))

    if not tiers and floor is None:  # empty scheme -> SOP default
        tiers = [Tier(1.0, 120), Tier(0.0, 100), Tier(-1.0, 80)]
        floor = Tier(None, 0)

    tiers.sort(key=lambda t: t.z_min, reverse=True)  # type: ignore[arg-type,return-value]
    tiers.append(floor or Tier(None, 0))
    return tiers


def grade_for(z: float, tiers: Sequence[Tier]) -> float:
    for tier in tiers:
        if tier.is_floor or z >= tier.z_min:  # type: ignore[operator]
            return tier.grade
    return 0.0


def tally(
    people: Sequence[Person],
    entries: Iterable[Entry],
    *,
    included_student_ids: set[int],
    exclude_instructors: bool = True,
    exclude_tas: bool = True,
    drop_test_student: bool = True,
) -> tuple[list[StudentRow], list[str]]:
    """Count each included student's posts and replies.

    This is the only step that needs Canvas data, so its result is cached and
    reused when the grading scheme or the weights change.
    `included_student_ids` is an allow-list: only these students are counted.
    """
    by_id = {p.id: p for p in people}
    roster: dict[int, StudentRow] = {}
    removed_test: list[str] = []

    for person in people:
        # Test students are checked before the allow-list so the removal is
        # always reported, even though the UI also leaves them unchecked.
        if drop_test_student and person.is_test_student:
            removed_test.append(person.name)
            continue
        if person.id not in included_student_ids:
            continue
        if exclude_instructors and person.is_teacher:
            continue
        if exclude_tas and person.is_ta:
            continue
        roster[person.id] = StudentRow(student_id=person.id, name=person.name)

    for entry in entries:
        row = roster.get(entry.user_id)
        if row is None:
            # Contribution by someone filtered out (staff, test student, or an
            # un-included student). Deliberately not counted anywhere.
            continue
        if entry.is_reply:
            row.replies += 1
        else:
            row.posts += 1

    rows = sorted(roster.values(), key=lambda r: (by_id[r.student_id].sortable_name or r.name))
    return rows, removed_test


def score(
    rows: Sequence[StudentRow],
    tiers: Sequence[Tier],
    weights: Weights | None = None,
    removed_test: Sequence[str] = (),
) -> Stats:
    """Apply weights, fit the distribution, and assign grades.

    Mutates `rows` in place. Cheap enough to re-run on every slider tick.
    """
    weights = weights or Weights()
    stats = Stats(weights=weights, test_students_removed=list(removed_test))

    for row in rows:
        row.weighted = weights.score(row.posts, row.replies)

    values = np.array([r.weighted for r in rows], dtype=float)
    if values.size:
        stats.mean = float(values.mean())
        stats.median = float(np.median(values))
        # Sample standard deviation (ddof=1), matching pandas' default. Falls
        # back to 0 for a single student, where a sample std is undefined.
        stats.std = float(values.std(ddof=1)) if values.size > 1 else 0.0
        stats.n = int(values.size)
        # Counted on raw contributions: a student who only replies has still
        # participated, even when replies are weighted to zero.
        stats.zero_posts = int(sum(1 for r in rows if r.total == 0))
        stats.total_posts = sum(r.posts for r in rows)
        stats.total_replies = sum(r.replies for r in rows)

    for row in rows:
        row.z = (row.weighted - stats.mean) / stats.std if stats.std > 0 else 0.0
        row.grade = grade_for(row.z, tiers)

    return stats


def analyse(
    people: Sequence[Person],
    entries: Iterable[Entry],
    *,
    included_student_ids: set[int],
    tiers: Sequence[Tier],
    weights: Weights | None = None,
    exclude_instructors: bool = True,
    exclude_tas: bool = True,
    drop_test_student: bool = True,
) -> tuple[list[StudentRow], Stats]:
    """Tally then score in one call."""
    rows, removed = tally(
        people,
        entries,
        included_student_ids=included_student_ids,
        exclude_instructors=exclude_instructors,
        exclude_tas=exclude_tas,
        drop_test_student=drop_test_student,
    )
    return rows, score(rows, tiers, weights, removed)


def histogram_data(rows: Sequence[StudentRow], bins: int = 12) -> dict[str, Any]:
    """Bin students by their weighted participation score."""
    values = np.array([r.weighted for r in rows], dtype=float)
    if not values.size:
        return {"edges": [], "counts": []}

    hi = float(values.max())
    edges = np.linspace(0.0, hi if hi > 0 else 1.0, bins + 1)
    idx = np.clip(np.digitize(values, edges[1:-1], right=False), 0, bins - 1)

    counts = np.zeros(bins)
    for b in idx:
        counts[b] += 1

    return {"edges": edges.tolist(), "counts": counts.tolist()}
