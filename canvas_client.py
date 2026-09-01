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

    def _get(self, path: str, **params: Any) -> requests.Response:
        url = path if path.startswith("http") else f"{self.base_url}/api/v1{path}"
        try:
            res = self.session.get(url, params=params or None, timeout=self.timeout)
        except requests.RequestException as exc:
            raise CanvasError(f"Could not reach Canvas: {exc}") from exc

        if res.status_code == 401:
            raise CanvasError("Canvas rejected the access token (401). Generate a new one.")
        if res.status_code == 403:
            raise CanvasError("Token lacks permission for this course (403).")
        if res.status_code == 404:
            raise CanvasError("Course or resource not found (404). Check the Course ID.")
        if not res.ok:
            raise CanvasError(f"Canvas returned {res.status_code} for {url}")
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
