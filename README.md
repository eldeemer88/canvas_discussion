# Canvas Discussion Grader

Analyzes participation in Canvas discussions and produces a grade distribution
from a normal-distribution model. Rebuild of the tool described in
[`docs/Grading_Distribution_SOP_old.pdf`](docs/Grading_Distribution_SOP_old.pdf),
with the changes listed below.

## Quick start

Run against synthetic data — no Canvas token needed:

```bash
pip install -r requirements.txt && DEMO_MODE=1 python3 app.py
```

Then open <http://localhost:5000>. Any URL/token/course ID is accepted in demo mode.

For real use, drop `DEMO_MODE`:

```bash
python3 app.py
```

## What changed from the old tool

### 1. Canvas Test Student is dropped from the statistics

Canvas creates a `Test Student` account the first time an instructor uses
Student View. It carries a `StudentViewEnrollment` and any posts made while
previewing the course. The old tool counted it as a real student, which pulled
the mean and standard deviation — and therefore every z-score and every letter
grade — off target.

It is now detected by enrollment type (with a name fallback), auto-excluded,
locked out of the include list, and reported in the results banner, the run log,
and the XLSX summary. The **Drop Canvas Test Student** toggle turns this off if
you ever need the account counted.

### 2. Mean *and* median are both reported

Participation is usually right-skewed: a few very active students pull the mean
above where most of the class actually sits. The median is shown alongside the
mean everywhere — summary cards, chart, run log, XLSX — and the chart marks both
(green dashed = mean, purple dotted = median).

When the two diverge by more than 0.35σ, the results panel raises a note, since
z-scores are computed from the mean and a skew will drag the tier cutoffs with it.

### 3. The histogram is stacked by posts and replies

Bar height is still the number of students in each participation bin, so the
shape remains a true distribution. Each bar is now split to show what that bin's
activity was made of — posts (blue) versus replies (teal). A bin of students who
only ever reply looks visibly different from one that starts threads.

### 5. Include, don't exclude

Both list panels select what to **include** rather than what to omit. Everything
starts included, so the default run is unchanged, but the panels now read
`9 of 12 discussions included` instead of asking you to reason about a negative.
Bulk actions are `+ Visible / − Visible / All / None`, and shift-click still
selects a contiguous range.

The request also switched from names to **stable Canvas IDs**
(`included_topic_ids`, `included_student_ids`). The old tool matched exclusions
by name string, so two students named "J. Smith" were indistinguishable and
renaming a topic silently changed which discussions were counted.

### Smaller fixes carried along

- The Grade Distribution card is generated from whatever tiers actually ran. The
  old one was hardcoded to 0/80/100/120, so any custom tier (SOP §4.3 invites
  them) produced wrong counts.
- Duplicate z-thresholds in the grading scheme are flagged — previously the
  shadowed tier was simply unreachable.
- A failed run no longer fires an `alert()` and resets the view; the sidebar
  configuration survives the error.
- The results table is sortable and searchable.
- The API token is no longer written to `localStorage` by default. Saved courses
  keep URL, course ID, and alias; **Remember API token** is opt-in per course.
  See the security note below.
- Download filenames are confined to the job directory (the old path was
  interpolated directly).

## Architecture

Same four-endpoint shape as the original, so this is a drop-in replacement.

| File | Role |
|---|---|
| `app.py` | Flask app, background job runner, API |
| `canvas_client.py` | Canvas REST client (paginated), test-student detection |
| `analysis.py` | `tally()` (needs Canvas) then `score()` (pure arithmetic, re-runnable) |
| `exports.py` | XLSX / CSV / PNG / TXT generation |
| `demo_data.py` | Synthetic course for `DEMO_MODE=1` |
| `static/index.html` | The entire client — one file, no build step |

| Endpoint | Purpose |
|---|---|
| `POST /api/validate` | credentials → course name, topics, people |
| `POST /api/run` | config → `{job_id}` |
| `POST /api/recompute/{job_id}` | new weights/tiers → re-scored results, no Canvas calls |
| `GET /api/status/{job_id}` | `running` / `done` / `error` (+ results when done) |
| `GET /api/download/{job_id}/{file}` | one output file |
| `GET /api/download_all/{job_id}` | all outputs as `.zip` |

Jobs are held in memory with their output files in a temp directory, reaped
after 2 hours. Each job caches its tally, which is what makes re-weighting cheap;
the output files keep the job's original timestamp and are rewritten in place, so
a reweight refines that run rather than littering the directory. That is fine for one or two TAs; it will not survive a restart or
work across multiple web workers (hence `--workers 1` in the `Procfile`).

## Statistical notes

- Standard deviation is the **sample** std (`ddof=1`), matching pandas' default.
  With 30+ students the difference from the population std is negligible.
- Z-scores are computed from the **mean** of `Y`, per the SOP. The median is
  reported but does not drive tier assignment. If you want cutoffs centred on the
  median instead, that is a small change in `analysis.py`.
- Weights are clamped to `[0, 100]`; negative weights would mean participating
  hurts your grade. With `β₁ = β₂ = 0` every score is 0, σ is 0, and every z-score
  is 0 — the degenerate case is handled, not crashed on.
- "Students with zero posts" counts **raw** contributions, so a student who only
  ever replies is not reported as inactive even when `β₂ = 0`.
- A "post" is a top-level discussion entry; a "reply" is anything nested beneath
  one. Deleted entries are skipped, but their surviving replies still count.

## Security note

Canvas API tokens grant full access to the account that created them, and the
SOP tells users to create **non-expiring** ones. This build keeps the token in
memory for the session and only persists it if you explicitly opt in per course.

Tokens are still sent to the server on each request and are not encrypted at
rest in the browser when you do opt in. If this is deployed anywhere shared, the
right fix is a server-side session that exchanges the token once and hands back
an opaque session ID.
