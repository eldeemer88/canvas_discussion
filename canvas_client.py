"""Thin Canvas LMS REST client.

Only the handful of endpoints the grader needs. Everything is paginated via the
RFC-5988 Link header that Canvas returns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

import requests

# Canvas's "Student View" pseudo-user. It shows up in the course user list with
# a StudentViewEnrollment and would otherwise be counted as a real student with
# zero (or worse, test) participation, dragging the mean down.
STUDENT_VIEW_ENROLLMENT = "StudentViewEnrollment"
TEST_STUDENT_NAME = "Test Student"

_NEXT_LINK = re.compile(r'<([^>]+)>;\s*rel="next"')


class CanvasError(RuntimeError):
    """Raised for any non-recoverable Canvas API failure."""


@dataclass
class Person:
    id: int
    name: str
    sortable_name: str = ""
    roles: set[str] = field(default_factory=set)
    is_test_student: bool = False

    @property
    def is_teacher(self) -> bool:
        return "TeacherEnrollment" in self.roles

    @property
    def is_ta(self) -> bool:
        return "TaEnrollment" in self.roles


@dataclass
class CourseRef:
    id: int
    name: str
    state: str = ""
    term: str = ""
    role: str = ""


@dataclass
class Topic:
    id: int
    title: str


@dataclass
class Entry:
    """One discussion contribution."""

    topic_id: int
    user_id: int
    is_reply: bool


class CanvasClient:
    def __init__(self, base_url: str, token: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.startswith(("http://", "https://")):
            self.base_url = "https://" + self.base_url
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"
        self.timeout = timeout

    # -- plumbing ----------------------------------------------------------

    @staticmethod
    def _detail(res: requests.Response) -> str:
        """Canvas explains itself in the body; surface that instead of a bare code."""
        try:
            data = res.json()
        except ValueError:
            return ""
        errors = data.get("errors") if isinstance(data, dict) else None
        if isinstance(errors, list):
            msgs = [e.get("message", "") for e in errors if isinstance(e, dict)]
            return "; ".join(m for m in msgs if m)
        if isinstance(errors, dict):
            return "; ".join(str(v) for v in errors.values())
        if isinstance(data, dict) and data.get("message"):
            return str(data["message"])
        return ""

    def _get(self, path: str, **params: Any) -> requests.Response:
        url = path if path.startswith("http") else f"{self.base_url}/api/v1{path}"
        try:
            res = self.session.get(url, params=params or None, timeout=self.timeout)
        except requests.RequestException as exc:
            raise CanvasError(f"Could not reach Canvas: {exc}") from exc

        detail = self._detail(res) if not res.ok else ""
        suffix = f" Canvas said: {detail}" if detail else ""

        if res.status_code == 401:
            raise CanvasError(
                "Canvas rejected the access token (401). It may be expired, revoked, "
                "or from a different Canvas site than the URL above." + suffix
            )
        if res.status_code == 403:
            raise CanvasError(
                "Your token is valid, but it cannot access this course (403). "
                "Common causes: the course ID belongs to a different Canvas site, "
                "the course is unpublished, or your enrolment in it is not active yet."
                + suffix
            )
        if res.status_code == 404:
            raise CanvasError(
                "No course with that ID on this Canvas site (404). The Course ID is the "
                "number in the course URL, e.g. /courses/123456." + suffix
            )
        if not res.ok:
            raise CanvasError(f"Canvas returned {res.status_code} for {url}.{suffix}")
        return res

    def _paginate(self, path: str, **params: Any) -> Iterator[dict]:
        params.setdefault("per_page", 100)
        res = self._get(path, **params)
        while True:
            payload = res.json()
            if isinstance(payload, list):
                yield from payload
            else:  # single object endpoints never paginate
                yield payload
                return
            match = _NEXT_LINK.search(res.headers.get("Link", ""))
            if not match:
                return
            res = self._get(match.group(1))

    # -- public API --------------------------------------------------------

    def get_course(self, course_id: str) -> dict:
        return self._get(f"/courses/{course_id}").json()

    def whoami(self) -> str:
        """Display name for the token's owner; empty if the token is invalid."""
        try:
            me = self._get("/users/self").json()
            return me.get("name") or me.get("short_name") or ""
        except CanvasError:
            return ""

    def list_courses(self) -> list[CourseRef]:
        """Every course this token can actually reach.

        Turns a dead-end 403 into a pick-list, which is usually enough for the
        user to spot that they had the wrong ID or the wrong Canvas site.
        """
        found: dict[int, CourseRef] = {}
        for state in ("active", "invited_or_pending", "completed"):
            try:
                rows = self._paginate(
                    "/courses",
                    enrollment_state=state,
                    **{"include[]": ["term"], "state[]": ["unpublished", "available", "completed"]},
                )
                for c in rows:
                    cid = c.get("id")
                    if cid is None or cid in found:
                        continue
                    enrolments = c.get("enrollments") or []
                    found[cid] = CourseRef(
                        id=cid,
                        name=c.get("name") or f"Course {cid}",
                        state=c.get("workflow_state") or "",
                        term=(c.get("term") or {}).get("name") or "",
                        role=(enrolments[0].get("type", "") if enrolments else ""),
                    )
            except CanvasError:
                continue  # one state failing should not hide the others
        return sorted(found.values(), key=lambda c: (c.term, c.name))

    def get_people(self, course_id: str) -> list[Person]:
        """Every student/teacher/TA in the course, test student included and flagged."""
        people: dict[int, Person] = {}
        raw = self._paginate(
            f"/courses/{course_id}/users",
            **{
                "enrollment_type[]": ["student", "teacher", "ta", "student_view"],
                "include[]": ["enrollments"],
            },
        )
        for u in raw:
            uid = u.get("id")
            if uid is None:
                continue
            person = people.setdefault(
                uid,
                Person(
                    id=uid,
                    name=u.get("name") or u.get("short_name") or f"User {uid}",
                    sortable_name=u.get("sortable_name") or "",
                ),
            )
            for enr in u.get("enrollments") or []:
                if enr.get("type"):
                    person.roles.add(enr["type"])
            person.is_test_student = (
                STUDENT_VIEW_ENROLLMENT in person.roles or person.name == TEST_STUDENT_NAME
            )
        return sorted(people.values(), key=lambda p: p.sortable_name or p.name)

    def get_topics(self, course_id: str) -> list[Topic]:
        return [
            Topic(id=t["id"], title=t.get("title") or f"Topic {t['id']}")
            for t in self._paginate(f"/courses/{course_id}/discussion_topics")
            if t.get("id") is not None
        ]

    def get_entries(self, course_id: str, topic_id: int) -> list[Entry]:
        """All non-deleted contributions in a topic.

        Uses the `/view` endpoint so one request returns the whole nested tree.
        Top-level entries count as posts; anything nested counts as a reply.
        """
        res = self._get(f"/courses/{course_id}/discussion_topics/{topic_id}/view")
        data = res.json()
        entries: list[Entry] = []

        def walk(nodes: list[dict], is_reply: bool) -> None:
            for node in nodes or []:
                if node.get("deleted"):
                    # A deleted entry keeps its replies, so recurse regardless.
                    pass
                elif node.get("user_id") is not None:
                    entries.append(
                        Entry(topic_id=topic_id, user_id=node["user_id"], is_reply=is_reply)
                    )
                walk(node.get("replies") or [], True)

        walk(data.get("view") or [], False)
        return entries
