"""Timestamped output files: XLSX, CSV, PNG, TXT."""

from __future__ import annotations

import os
import pathlib
import tempfile
from collections import Counter
from pathlib import Path
from typing import Sequence

# Container images and frozen app bundles often have no writable HOME, which
# makes matplotlib fail on import while building its font cache. Point it at a
# STABLE temp path -- a fresh mkdtemp each launch would rebuild the cache every
# single time, costing seconds of startup.
_MPL_CACHE = pathlib.Path(tempfile.gettempdir()) / "canvas_grader_mplcache"
_MPL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_MPL_CACHE))

import matplotlib

matplotlib.use("Agg")  # headless: no display on the server

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis import Stats, StudentRow, Tier, Weights, histogram_data

BG = "#0d1117"
FG = "#e6edf3"
MUTED = "#8b949e"
GRID = "#30363d"
PANEL = "#161b22"

BAR_COLOR = "#4a8fe7"
POST_COLOR = "#4a8fe7"
REPLY_COLOR = "#7ee0b8"
MEAN_COLOR = "#5ce08f"
MEDIAN_COLOR = "#c792ea"
SIGMA_COLOR = "#e6c07b"
FIT_COLOR = "#e06c75"
TIER_PALETTE = ["#4a8fe7", "#5ce08f", "#e6c07b", "#e06c75", "#c792ea", "#56b6c2", "#e59f6a"]


def _dark(*axes) -> None:
    for ax in axes:
        ax.set_facecolor(BG)
        ax.tick_params(colors=MUTED, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(GRID)


def _legend(ax, **kw):
    return ax.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=FG,
                     framealpha=0.95, **kw)


def _grade_colors(tiers: Sequence[Tier]) -> dict[float, str]:
    return {t.grade: TIER_PALETTE[i % len(TIER_PALETTE)] for i, t in enumerate(tiers)}


def _axis_label(stats: Stats) -> str:
    return "Total Posts + Replies" if stats.weights.is_default else "Weighted participation (Y)"


def _frame(rows: Sequence[StudentRow], stats: Stats) -> pd.DataFrame:
    data = [
        {
            "Student": r.name,
            "Student ID": r.student_id,
            "Posts": r.posts,
            "Replies": r.replies,
            "Total": r.total,
            "Weighted Y": round(r.weighted, 3),
            "Z-Score": round(r.z, 4),
            "Grade %": r.grade,
        }
        for r in rows
    ]
    df = pd.DataFrame(data)
    if stats.weights.is_default and not df.empty:
        # Y is identical to Total at 1/1, so the extra column is just noise.
        df = df.drop(columns=["Weighted Y"])
    return df


def _describe(tiers: Sequence[Tier]) -> list[str]:
    out = []
    for t in tiers:
        cond = "otherwise" if t.is_floor else f"z >= {t.z_min:g}"
        out.append(f"{cond} -> {t.grade:g}%")
    return out


def write_csv(rows: Sequence[StudentRow], stats: Stats, path: Path) -> None:
    _frame(rows, stats).to_csv(path, index=False)


def write_log(rows, stats: Stats, tiers, path: Path) -> None:
    dist = Counter(r.grade for r in rows)
    lines = [
        "CANVAS DISCUSSION GRADER - RUN LOG",
        "=" * 46,
        "",
        f"Students analysed      : {stats.n}",
        f"Students with 0 posts  : {stats.zero_posts}",
        f"Total posts            : {stats.total_posts}",
        f"Total replies          : {stats.total_replies}",
        "",
        "PARTICIPATION SCORE",
        "-" * 46,
        f"Formula                : {stats.weights.label()}",
        f"  beta_posts           : {stats.weights.posts:g}",
        f"  beta_replies         : {stats.weights.replies:g}",
        "",
        "DISTRIBUTION OF Y",
        "-" * 46,
        f"Mean                   : {stats.mean:.2f}",
        f"Median                 : {stats.median:.2f}",
        f"Std deviation (ddof=1) : {stats.std:.2f}",
        f"Mean - 1 sigma         : {stats.mean - stats.std:.2f}",
        f"Mean + 1 sigma         : {stats.mean + stats.std:.2f}",
        "",
        "GRADING SCHEME",
        "-" * 46,
        *_describe(tiers),
        "",
        "GRADE DISTRIBUTION",
        "-" * 46,
        *[f"{g:g}%".ljust(23) + f": {dist[g]}" for g in sorted(dist, reverse=True)],
    ]

    if stats.test_students_removed:
        lines += [
            "",
            "EXCLUDED FROM STATISTICS",
            "-" * 46,
            *[f"Canvas test student    : {n}" for n in stats.test_students_removed],
        ]

    zeros = [r.name for r in rows if r.total == 0]
    if zeros:
        lines += ["", "STUDENTS WITH ZERO PARTICIPATION", "-" * 46, *zeros]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Chart 1: distribution (histogram of Y + grade counts)
# ---------------------------------------------------------------------------


def write_png(rows: Sequence[StudentRow], stats: Stats, tiers, path: Path) -> None:
    hist = histogram_data(rows, bins=12)
    edges = np.array(hist["edges"] or [0.0, 1.0])
    centers = (edges[:-1] + edges[1:]) / 2
    width = (edges[1] - edges[0]) * 0.9 if len(edges) > 1 else 1.0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5), facecolor=BG)
    _dark(ax1, ax2)

    ax1.bar(centers, np.array(hist["counts"] or []), width=width, color=BAR_COLOR,
            label="Students", zorder=3)

    if stats.std > 0:
        xs = np.linspace(float(edges[0]), float(edges[-1]), 300)
        pdf = np.exp(-0.5 * ((xs - stats.mean) / stats.std) ** 2) / (
            stats.std * np.sqrt(2 * np.pi)
        )
        # Scale the density onto the student-count axis so both are readable.
        scale = (stats.n * (edges[1] - edges[0])) if len(edges) > 1 else stats.n
        ax1.plot(xs, pdf * scale, color=FIT_COLOR, lw=1.6, label="Normal fit", zorder=6)
        # Cutoff markers sit above the bars, otherwise they vanish behind them.
        ax1.axvline(stats.mean - stats.std, color=SIGMA_COLOR, ls="--", lw=1.2, zorder=5)
        ax1.axvline(
            stats.mean + stats.std, color=SIGMA_COLOR, ls="--", lw=1.2, zorder=5,
            label=f"±1σ = {stats.mean - stats.std:.1f} / {stats.mean + stats.std:.1f}",
        )

    ax1.axvline(stats.mean, color=MEAN_COLOR, ls="--", lw=1.8,
                label=f"Mean = {stats.mean:.1f}", zorder=7)
    ax1.axvline(stats.median, color=MEDIAN_COLOR, ls=":", lw=2.2,
                label=f"Median = {stats.median:.1f}", zorder=7)

    ax1.set_title("Participation Distribution", color=FG, fontsize=11)
    ax1.set_xlabel(_axis_label(stats), color=MUTED, fontsize=9)
    ax1.set_ylabel("Number of Students", color=MUTED, fontsize=9)
    _legend(ax1).set_zorder(10)
    ax1.set_ylim(top=max(ax1.get_ylim()[1] * 1.28, 1))

    dist = Counter(r.grade for r in rows)
    grades = sorted(dist)
    cmap = _grade_colors(tiers)
    bars = ax2.bar([f"{g:g}%" for g in grades], [dist[g] for g in grades],
                   color=[cmap.get(g, BAR_COLOR) for g in grades], zorder=3)
    for bar, g in zip(bars, grades):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), str(dist[g]),
                 ha="center", va="bottom", color=FG, fontsize=9)
    ax2.set_title("Grade Distribution", color=FG, fontsize=11)
    ax2.set_xlabel("Grade", color=MUTED, fontsize=9)
    ax2.set_ylabel("Number of Students", color=MUTED, fontsize=9)

    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Chart 2: composition (posts vs replies)
# ---------------------------------------------------------------------------


def write_composition_png(rows: Sequence[StudentRow], stats: Stats, tiers, path: Path) -> None:
    """Posts-vs-replies scatter with grade bands, plus a per-student breakdown."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.6), facecolor=BG)
    _dark(ax1, ax2)
    cmap = _grade_colors(tiers)

    posts = np.array([r.posts for r in rows], dtype=float)
    replies = np.array([r.replies for r in rows], dtype=float)
    grades = np.array([r.grade for r in rows], dtype=float)
    w = stats.weights

    if not len(rows):
        for ax in (ax1, ax2):
            ax.text(0.5, 0.5, "No students", ha="center", va="center", color=MUTED,
                    transform=ax.transAxes)
        fig.savefig(path, dpi=150, facecolor=BG)
        plt.close(fig)
        return

    # -- left: scatter, shaded by grade band -------------------------------
    xmax = max(posts.max() * 1.15, 1.0)
    ymax = max(replies.max() * 1.15, 1.0)

    # Tier cutoffs live in Y-space: b1*posts + b2*replies = mean + z*std.
    # Filling with contourf handles every weight combination uniformly,
    # including b2 = 0 (vertical bands) and b1 = 0 (horizontal bands).
    ranked = [t for t in tiers if not t.is_floor]
    cuts = [stats.mean + t.z_min * stats.std for t in ranked] if stats.std > 0 else []

    if cuts and not w.is_degenerate:
        gx, gy = np.meshgrid(np.linspace(0, xmax, 400), np.linspace(0, ymax, 400))
        gz = w.posts * gx + w.replies * gy
        levels = [-np.inf] + sorted(cuts) + [np.inf]
        # Bands run low-to-high, so grades are the floor tier then the ranked
        # tiers in ascending threshold order.
        band_grades = [tiers[-1].grade] + [t.grade for t in sorted(ranked, key=lambda t: t.z_min)]
        ax1.contourf(gx, gy, gz, levels=levels,
                     colors=[cmap.get(g, BAR_COLOR) for g in band_grades], alpha=0.14, zorder=1)
        ax1.contour(gx, gy, gz, levels=sorted(cuts), colors=GRID,
                    linestyles="--", linewidths=1, zorder=2)

    if replies.max() > 0 and posts.max() > 0:
        lim = min(xmax, ymax)
        ax1.plot([0, lim], [0, lim], color=MUTED, ls=":", lw=1, alpha=0.55, zorder=2)
        ax1.annotate("equal posts & replies", (lim * 0.62, lim * 0.67), color=MUTED,
                     fontsize=7, rotation=38, zorder=3)

    for g in sorted(set(grades), reverse=True):
        m = grades == g
        ax1.scatter(posts[m], replies[m], s=54, color=cmap.get(g, BAR_COLOR),
                    edgecolor=BG, linewidth=0.8, label=f"{g:g}%", zorder=5)

    ax1.set_xlim(0, xmax)
    ax1.set_ylim(0, ymax)
    ax1.set_title("Posts vs Replies, shaded by grade band", color=FG, fontsize=11)
    ax1.set_xlabel("Posts", color=MUTED, fontsize=9)
    ax1.set_ylabel("Replies", color=MUTED, fontsize=9)
    ax1.annotate(w.label(), (0.985, 0.03), xycoords="axes fraction", ha="right",
                 color=MUTED, fontsize=7.5, zorder=8)
    _legend(ax1, title="Grade", title_fontsize=7, loc="upper right").set_zorder(10)

    # -- right: every student, sorted ---------------------------------------
    order = np.argsort([r.weighted for r in rows])
    idx = np.arange(len(rows))
    sp, sr = posts[order], replies[order]

    if w.is_default:
        # Bars sum to Y, so a plain stack is exact.
        ax2.bar(idx, sp, color=POST_COLOR, label="Posts", zorder=3)
        ax2.bar(idx, sr, bottom=sp, color=REPLY_COLOR, label="Replies", zorder=3)
        ylabel = "Contributions"
    else:
        # Under weights the stack shows each part's *contribution to Y*, so the
        # bar height still equals the score the grade is based on.
        ax2.bar(idx, w.posts * sp, color=POST_COLOR,
                label=f"Posts × {w.posts:g}", zorder=3)
        ax2.bar(idx, w.replies * sr, bottom=w.posts * sp, color=REPLY_COLOR,
                label=f"Replies × {w.replies:g}", zorder=3)
        ylabel = "Weighted participation (Y)"

    for tier, cut in zip(ranked, cuts):
        color = cmap.get(tier.grade, SIGMA_COLOR)
        ax2.axhline(cut, color=color, ls="--", lw=1.1, zorder=4)
        ax2.annotate(f"{tier.grade:g}% cutoff", (len(rows) * 0.012, cut),
                     textcoords="offset points", xytext=(0, 4), color=color,
                     fontsize=7, zorder=5)

    ax2.set_title("Every student, sorted by participation", color=FG, fontsize=11)
    ax2.set_xlabel("Students (ranked)", color=MUTED, fontsize=9)
    ax2.set_ylabel(ylabel, color=MUTED, fontsize=9)
    ax2.set_xticks([])
    ax2.set_xlim(-0.8, len(rows) - 0.2)
    _legend(ax2, loc="upper left").set_zorder(10)

    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=BG)
    plt.close(fig)


def write_xlsx(rows, stats: Stats, tiers, images: Sequence[Path], path: Path) -> None:
    dist = Counter(r.grade for r in rows)
    summary = pd.DataFrame(
        {
            "Metric": [
                "Students analysed", "Students with 0 posts", "Total posts", "Total replies",
                "Score formula", "beta_posts", "beta_replies",
                "Mean (Y)", "Median (Y)", "Std deviation (ddof=1)", "Mean - 1σ", "Mean + 1σ",
                "Canvas test students removed",
            ],
            "Value": [
                stats.n, stats.zero_posts, stats.total_posts, stats.total_replies,
                stats.weights.label(), stats.weights.posts, stats.weights.replies,
                round(stats.mean, 2), round(stats.median, 2), round(stats.std, 2),
                round(stats.mean - stats.std, 2), round(stats.mean + stats.std, 2),
                ", ".join(stats.test_students_removed) or "none",
            ],
        }
    )
    scheme = pd.DataFrame({"Rule": _describe(tiers)})
    grade_dist = pd.DataFrame(
        {"Grade %": [f"{g:g}" for g in sorted(dist, reverse=True)],
         "Students": [dist[g] for g in sorted(dist, reverse=True)]}
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        _frame(rows, stats).to_excel(writer, sheet_name="Grades", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)
        grade_dist.to_excel(writer, sheet_name="Summary", index=False, startrow=len(summary) + 3)
        scheme.to_excel(writer, sheet_name="Grading Scheme", index=False)

        for name, widths in (("Grades", [30, 12, 10, 10, 10, 12, 12, 10]),
                             ("Summary", [32, 34]), ("Grading Scheme", [30])):
            ws = writer.sheets[name]
            for i, width in enumerate(widths, start=1):
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

        existing = [p for p in images if p and p.exists()]
        if existing:
            from openpyxl.drawing.image import Image as XLImage

            chart_ws = writer.book.create_sheet("Charts")
            row = 2
            for img_path in existing:
                img = XLImage(str(img_path))
                img.width, img.height = 1040, 420
                chart_ws.add_image(img, f"B{row}")
                row += 23
