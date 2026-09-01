"""Synthetic course data so the app can be demoed and tested without a Canvas token.

Enabled with DEMO_MODE=1. Mirrors CanvasClient's interface exactly.
"""

from __future__ import annotations

import random

from canvas_client import Entry, Person, Topic

FIRST = ["Ava", "Noah", "Mia", "Liam", "Zoe", "Ethan", "Iris", "Owen", "Nora", "Kai",
         "Lena", "Jonah", "Priya", "Marcus", "Elena", "Tobias", "Ruth", "Dmitri",
         "Simone", "Andre", "Yuki", "Clara", "Hassan", "Beatriz", "Felix", "Ingrid",
         "Omar", "Sofia", "Theo", "Wren", "Xavier", "Yara", "Zane", "Amara", "Bodhi"]
LAST = ["Ahmed", "Barnes", "Chen", "Dubois", "Eriksen", "Ferrari", "Garcia", "Huang",
        "Ivanov", "Jensen", "Kowalski", "Lopez", "Meyer", "Novak", "Okafor", "Petrov",
        "Quinn", "Rossi", "Silva", "Tanaka", "Ueda", "Vargas", "Weber", "Xu", "Yilmaz",
        "Zhang", "Abbott", "Bauer", "Costa", "Dunn", "Elias", "Fisher", "Gross",
        "Haas", "Ito"]
TOPIC_TITLES = [
    "Week 1 — Introductions", "Week 2 — Rational Choice", "Week 3 — Prospect Theory",
    "Week 4 — Nudges and Defaults", "Week 5 — Social Preferences",
    "Week 6 — Time Discounting", "Week 7 — Midterm Reflection",
    "Presentation Group A", "Presentation Group B", "Presentation Group C",
    "Week 9 — Market Design", "Week 10 — Course Wrap-Up",
]

TEST_STUDENT_ID = 999001


class DemoClient:
    """Deterministic stand-in for CanvasClient."""

    def __init__(self, seed: int = 20260409):
        self.rng = random.Random(seed)
        self._people: list[Person] | None = None

    def get_course(self, course_id: str) -> dict:
        return {"id": course_id, "name": "BEHV 1750 — Behavioral Economics (Demo)"}

    def get_people(self, course_id: str) -> list[Person]:
        if self._people is not None:
            return self._people

        people = [
            Person(id=1000 + i, name=f"{f} {l}", sortable_name=f"{l}, {f}")
            for i, (f, l) in enumerate(zip(FIRST, LAST))
        ]
        people.append(
            Person(id=900, name="Dr. Helena Vance", sortable_name="Vance, Helena",
                   roles={"TeacherEnrollment"})
        )
        people.append(
            Person(id=901, name="Sam Okonkwo", sortable_name="Okonkwo, Sam",
                   roles={"TaEnrollment"})
        )
        # The Canvas "Student View" user. Given heavy activity on purpose so the
        # effect of filtering it out of the mean is obvious in the demo.
        people.append(
            Person(id=TEST_STUDENT_ID, name="Test Student", sortable_name="Student, Test",
                   roles={"StudentViewEnrollment"}, is_test_student=True)
        )
        self._people = sorted(people, key=lambda p: p.sortable_name)
        return self._people

    def get_topics(self, course_id: str) -> list[Topic]:
        return [Topic(id=200 + i, title=t) for i, t in enumerate(TOPIC_TITLES)]

    def get_entries(self, course_id: str, topic_id: int) -> list[Entry]:
        people = self.get_people(course_id)
        students = [p for p in people if not p.roles]
        rng = random.Random(topic_id * 7919)
        entries: list[Entry] = []

        for i, student in enumerate(students):
            # A stable per-student engagement level, so the cohort has a
            # believable spread rather than uniform noise.
            level = ((student.id * 37) % 100) / 100
            if rng.random() < 0.12 + (1 - level) * 0.3:
                continue  # skipped this discussion entirely
            posts = 1 if rng.random() < 0.85 else 2
            replies = int(rng.random() * (1 + level * 4))
            entries += [Entry(topic_id, student.id, False)] * posts
            entries += [Entry(topic_id, student.id, True)] * replies

        # Staff and the test student also post; all get filtered downstream.
        entries += [Entry(topic_id, 900, True)] * rng.randint(0, 3)
        entries += [Entry(topic_id, 901, True)] * rng.randint(0, 2)
        entries += [Entry(topic_id, TEST_STUDENT_ID, False)] * rng.randint(2, 6)
        return entries
