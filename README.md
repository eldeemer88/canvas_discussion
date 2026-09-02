# Canvas Discussion Grader

Analyzes participation in Canvas discussions and produces a grade distribution
from a normal-distribution model. Runs as a downloadable desktop app — no server,
no hosting, and Canvas tokens never leave the user's machine.

**[→ Download the app](../../releases/latest)** &nbsp;·&nbsp;
**[→ Full SOP (PDF)](docs/Canvas_Discussion_Grader_SOP.pdf)**

The SOP is the document to hand to teaching staff: installation, token
generation, configuration, how to read the output, and troubleshooting. This
README covers the code.

> Canvas site is **https://canvas.harvard.edu**. The older
> [`docs/Grading_Distribution_SOP_old.pdf`](docs/Grading_Distribution_SOP_old.pdf)
> is the inherited Pitt document this tool was rebuilt from — kept for reference
> only. Its URLs, institution and sample data are not accurate.

## For TAs: download the app

Grab the latest build from the [Releases page](../../releases) — pick the Mac or
Windows zip. Everything runs on your own machine: your Canvas token never leaves
it, and no student data is sent anywhere. Full instructions are in the
[SOP](docs/Canvas_Discussion_Grader_SOP.pdf).

The apps are unsigned, so the first launch shows a warning (the warning means
"no paid certificate", not "unsafe"):

**macOS.** Unzip, drag to Applications. It will refuse to open the first time.
Right-click → Open does *not* work on macOS 15 Sequoia or newer — Apple removed
that bypass. Instead either open **System Settings → Privacy & Security**, scroll
to **Security**, and click **Open Anyway**; or run this one line:

```bash
xattr -dr com.apple.quarantine "/Applications/Canvas Discussion Grader.app"
```

The block comes from the quarantine flag your browser attaches to downloads,
not from anything wrong with the app — its signature is valid, just ad-hoc
rather than a paid Developer ID. One-time step either way.

**Windows.** Unzip and run the `.exe`. At "Windows protected your PC", click
**More info → Run anyway**.

The app opens in your browser. Click **Quit** in the top right when you're done.

## For developers: run from source

Run against synthetic data — no Canvas token needed:

```bash
pip install -r requirements.txt && DEMO_MODE=1 python3 app.py
```

Then open <http://localhost:5000>. Any URL/token/course ID is accepted in demo mode.

For real use, drop `DEMO_MODE`:

```bash
python3 app.py
```

To run it the way the packaged app does (waitress, random port, opens a browser):

```bash
python3 desktop.py
```

## Building the desktop apps

Builds are automated. Tag a commit and GitHub Actions produces all three
binaries and attaches them to a Release:

```bash
git tag v1.0.0 && git push --tags
```

The Actions tab also has a **Run workflow** button to build without releasing.

To build locally, use a **clean virtualenv** — building from a kitchen-sink
Python (Anaconda especially) sweeps PyQt, scipy and friends into the bundle and
inflates it about 8x, from ~86 MB to ~716 MB:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pyinstaller && .venv/bin/pyinstaller build.spec --noconfirm
```

PyInstaller cannot cross-compile: a Windows `.exe` has to be built on Windows,
which is the reason the release pipeline runs on three different runners.

## Regenerating the SOP

The SOP's figures are real screenshots, captured by driving the app in demo mode
rather than pasted in by hand, so they cannot drift from the UI:

```bash
pip install reportlab playwright && python3 -m playwright install chromium
```

`tools/capture_figures.py` starts the app (plus a mock Canvas, for the failure
screenshots), captures each panel, and `tools/make_sop.py` builds the PDF into
`docs/`. Re-run both after any UI change that the SOP depicts.

### Signing

The binaries are unsigned, which is why users see a one-time warning. Removing
it costs $99/year for an Apple Developer account (macOS notarization) and more
for a Windows Authenticode certificate. Worth it only if non-technical staff
find the warning off-putting.

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
