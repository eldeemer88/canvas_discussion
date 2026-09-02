"""Canvas Discussion Grader — web service.

Serves the single-file client and runs analyses as background jobs, keeping the
same four-endpoint shape as the original tool so it stays a drop-in replacement.
"""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import threading
import traceback
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file, send_from_directory

import demo_data
import exports
from analysis import StudentRow, Tier, Weights, parse_scheme, parse_weights, score, tally
from canvas_client import CanvasClient, CanvasError

def _resource_dir() -> Path:
    """Where bundled files live.

    PyInstaller unpacks data files to a temp dir it advertises as sys._MEIPASS,
    so the frozen desktop build cannot use __file__ to find static/.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return Path(__file__).parent


BASE_DIR = _resource_dir()
STATIC_DIR = BASE_DIR / "static"
IS_FROZEN = getattr(sys, "frozen", False)
# Set by the desktop launcher; signals the server to stop.
SHUTDOWN = threading.Event()
JOB_TTL = timedelta(hours=2)
DEMO_MODE = os.environ.get("DEMO_MODE") == "1"

app = Flask(__name__, static_folder=None)


@dataclass
class Job:
    id: str
    status: str = "running"  # running | done | error
    progress: int = 0
    total: int = 0
    message: str = "Initializing..."
    created: datetime = field(default_factory=datetime.now)
    result: dict[str, Any] | None = None
    workdir: Path | None = None
    # Cached tally, so re-weighting and re-tiering never re-hit the Canvas API.
    rows: list[StudentRow] = field(default_factory=list)
    removed_test: list[str] = field(default_factory=list)
    stamp: str = ""
    topics_analysed: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


JOBS: dict[str, Job] = {}
JOBS_LOCK = threading.Lock()


def _client(payload: dict) -> CanvasClient:
    if DEMO_MODE:
        return demo_data.DemoClient()
    return CanvasClient(payload.get("canvas_url", ""), payload.get("token", ""))


def _reap_old_jobs() -> None:
    cutoff = datetime.now() - JOB_TTL
    with JOBS_LOCK:
        stale = [j for j in JOBS.values() if j.created < cutoff]
        for job in stale:
            if job.workdir and job.workdir.exists():
                shutil.rmtree(job.workdir, ignore_errors=True)
            JOBS.pop(job.id, None)


# ---------------------------------------------------------------------------
# Static
# ---------------------------------------------------------------------------


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/healthz")
def healthz():
    return jsonify(ok=True, demo=DEMO_MODE, desktop=IS_FROZEN)


@app.post("/api/quit")
def quit_app():
    """Let the page shut the desktop app down; a no-op when server-hosted."""
    if not IS_FROZEN:
        return jsonify(error="Not running as a desktop app."), 400
    SHUTDOWN.set()
    return jsonify(ok=True)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@app.post("/api/validate")
def validate():
    payload = request.get_json(silent=True) or {}
    course_id = str(payload.get("course_id", "")).strip()

    if not DEMO_MODE and not all(
        [payload.get("canvas_url"), payload.get("token"), course_id]
    ):
        return jsonify(error="Canvas URL, token, and course ID are all required."), 400

    try:
        client = _client(payload)
        course = client.get_course(course_id)
        people = client.get_people(course_id)
        topics = client.get_topics(course_id)
    except CanvasError as exc:
        return jsonify(error=str(exc)), 400
    except Exception as exc:  # noqa: BLE001 - surface anything unexpected to the UI
        return jsonify(error=f"Unexpected error: {exc}"), 500

    return jsonify(
        course_name=course.get("name") or f"Course {course_id}",
        topics=[{"id": t.id, "title": t.title} for t in topics],
        students=[
            {
                "id": p.id,
                "name": p.name,
                "is_test_student": p.is_test_student,
                "is_staff": p.is_teacher or p.is_ta,
                "role": "Teacher" if p.is_teacher else "TA" if p.is_ta else "Student",
            }
            for p in people
        ],
    )


@app.post("/api/run")
def run():
    _reap_old_jobs()
    payload = request.get_json(silent=True) or {}
    job = Job(id=uuid.uuid4().hex[:12])
    with JOBS_LOCK:
        JOBS[job.id] = job
    threading.Thread(target=_execute, args=(job, payload), daemon=True).start()
    return jsonify(job_id=job.id)


def _execute(job: Job, payload: dict) -> None:
    try:
        course_id = str(payload.get("course_id", "")).strip()
        client = _client(payload)

        # Allow-lists: the client sends what to INCLUDE, by stable Canvas ID.
        included_topics = payload.get("included_topic_ids")
        included_students = payload.get("included_student_ids")

        job.message = "Loading roster..."
        people = client.get_people(course_id)
        topics = client.get_topics(course_id)

        if included_topics is not None:
            keep = {int(t) for t in included_topics}
            topics = [t for t in topics if t.id in keep]
        if included_students is not None:
            student_ids = {int(s) for s in included_students}
        else:
            student_ids = {p.id for p in people}

        job.total = max(len(topics), 1)
        entries = []
        for i, topic in enumerate(topics, start=1):
            job.progress = i
            job.message = f"[{i}/{len(topics)}] {topic.title[:60]}"
            entries.extend(client.get_entries(course_id, topic.id))

        job.message = "Computing distribution..."
        job.rows, job.removed_test = tally(
            people,
            entries,
            included_student_ids=student_ids,
            exclude_instructors=bool(payload.get("exclude_instructors", True)),
            exclude_tas=bool(payload.get("exclude_tas", True)),
            drop_test_student=bool(payload.get("drop_test_student", True)),
        )
        job.stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        job.workdir = Path(tempfile.mkdtemp(prefix=f"cdg_{job.id}_"))
        job.topics_analysed = len(topics)

        job.message = "Writing files..."
        job.result = _render(
            job,
            parse_scheme(payload.get("grading_scheme")),
            parse_weights(payload),
        )
        job.progress = job.total
        job.status = "done"

    except CanvasError as exc:
        job.status, job.message = "error", str(exc)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        job.status, job.message = "error", f"Unexpected error: {exc}"


def _render(job: Job, tiers: list[Tier], weights: Weights) -> dict[str, Any]:
    """Score the cached tally and (re)write every output file.

    Files keep the job's original timestamp and are rewritten in place, so a
    reweight refines this run rather than littering the directory.
    """
    stats = score(job.rows, tiers, weights, job.removed_test)
    wd, ts = job.workdir, job.stamp
    assert wd is not None

    chart = wd / f"discussion_analysis_{ts}.png"
    composition = wd / f"discussion_composition_{ts}.png"
    xlsx = wd / f"discussion_grades_{ts}.xlsx"
    csv = wd / f"discussion_raw_data_{ts}.csv"
    log = wd / f"last_run_log_{ts}.txt"

    exports.write_png(job.rows, stats, tiers, chart)
    exports.write_composition_png(job.rows, stats, tiers, composition)
    exports.write_csv(job.rows, stats, csv)
    exports.write_log(job.rows, stats, tiers, log)
    exports.write_xlsx(job.rows, stats, tiers, [chart, composition], xlsx)

    bust = int(datetime.now().timestamp() * 1000)
    return {
        "summary": [
            {
                "Student": r.name,
                "StudentId": r.student_id,
                "Posts": r.posts,
                "Replies": r.replies,
                "Total": r.total,
                "Weighted": round(r.weighted, 3),
                "Z": round(r.z, 3),
                "Grade": r.grade,
            }
            for r in job.rows
        ],
        "stats": {
            "mean": stats.mean,
            "median": stats.median,
            "std": stats.std,
            "n": stats.n,
            "zero_posts": stats.zero_posts,
            "total_posts": stats.total_posts,
            "total_replies": stats.total_replies,
            "test_students_removed": stats.test_students_removed,
            "beta_posts": weights.posts,
            "beta_replies": weights.replies,
            "weights_default": weights.is_default,
            "formula": weights.label(),
        },
        "topics_analysed": job.topics_analysed,
        "files": [p.name for p in (xlsx, csv, chart, composition, log)],
        "chart_url": f"/api/download/{job.id}/{chart.name}?v={bust}",
        "composition_url": f"/api/download/{job.id}/{composition.name}?v={bust}",
    }


@app.post("/api/recompute/<job_id>")
def recompute(job_id: str):
    """Re-score a finished job under new weights or tiers. No Canvas traffic."""
    job = JOBS.get(job_id)
    if job is None or job.status != "done":
        return jsonify(error="Job not found or expired. Run the analysis again."), 404

    payload = request.get_json(silent=True) or {}
    try:
        # Serialised: concurrent slider ticks would otherwise interleave writes
        # to the same output files.
        with job.lock:
            job.result = _render(
                job, parse_scheme(payload.get("grading_scheme")), parse_weights(payload)
            )
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        return jsonify(error=f"Recompute failed: {exc}"), 500

    return jsonify({"status": "done", **job.result})


@app.get("/api/status/<job_id>")
def status(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        return jsonify(status="error", message="Job not found or expired."), 404
    body = {
        "status": job.status,
        "progress": job.progress,
        "total": job.total,
        "message": job.message,
    }
    if job.status == "done" and job.result:
        body.update(job.result)
    return jsonify(body)


def _safe_file(job_id: str, filename: str) -> Path:
    job = JOBS.get(job_id)
    if job is None or not job.workdir:
        raise FileNotFoundError("Job not found or expired.")
    # Resolve and confine to the job directory so a crafted name can't escape.
    target = (job.workdir / filename).resolve()
    if job.workdir.resolve() not in target.parents or not target.is_file():
        raise FileNotFoundError("File not found.")
    return target


@app.get("/api/download/<job_id>/<path:filename>")
def download(job_id: str, filename: str):
    try:
        return send_file(_safe_file(job_id, filename), as_attachment=False)
    except FileNotFoundError as exc:
        return jsonify(error=str(exc)), 404


@app.get("/api/download_all/<job_id>")
def download_all(job_id: str):
    job = JOBS.get(job_id)
    if job is None or not job.workdir or not job.result:
        return jsonify(error="Job not found or expired."), 404

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in job.result["files"]:
            path = job.workdir / name
            if path.is_file():
                zf.write(path, arcname=name)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="canvas_discussion_results.zip",
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
