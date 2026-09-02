"""Generate the Canvas Discussion Grader SOP."""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle)
from PIL import Image as PILImage

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "docs" / "figures"
OUT = ROOT / "docs" / "Canvas_Discussion_Grader_SOP.pdf"

NAVY = colors.HexColor("#1b3a5c")
BLUE = colors.HexColor("#2f6da8")
INK = colors.HexColor("#1a1a1a")
GREY = colors.HexColor("#6b7785")
RULE = colors.HexColor("#c8d4e0")
WARNBG = colors.HexColor("#fdf6e3")
WARNED = colors.HexColor("#d9a441")
NOTEBG = colors.HexColor("#eef4fa")

W, H = letter
MARGIN = 0.9 * inch
CW = W - 2 * MARGIN

ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("t", parent=ss["Title"], fontName="Helvetica-Bold",
                            fontSize=25, leading=30, textColor=NAVY, spaceAfter=4),
    "sub": ParagraphStyle("s", parent=ss["Normal"], fontName="Helvetica",
                          fontSize=13, leading=17, textColor=BLUE,
                          alignment=TA_CENTER, spaceAfter=3),
    "subq": ParagraphStyle("sq", parent=ss["Normal"], fontName="Helvetica",
                           fontSize=9.5, leading=13, textColor=GREY,
                           alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=14.5, leading=18,
                         textColor=colors.white, backColor=NAVY, borderPadding=(7, 8, 7, 8),
                         spaceBefore=20, spaceAfter=12),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                         textColor=NAVY, spaceBefore=14, spaceAfter=6),
    "body": ParagraphStyle("b", fontName="Helvetica", fontSize=9.8, leading=14.5,
                           textColor=INK, spaceAfter=7),
    "bullet": ParagraphStyle("bu", fontName="Helvetica", fontSize=9.8, leading=14.5,
                             textColor=INK, leftIndent=15, bulletIndent=4, spaceAfter=4),
    "step": ParagraphStyle("st", fontName="Helvetica", fontSize=9.8, leading=14.5,
                           textColor=INK, leftIndent=20, bulletIndent=6, spaceAfter=5),
    "cap": ParagraphStyle("c", fontName="Helvetica-Oblique", fontSize=8.2, leading=11,
                          textColor=GREY, alignment=TA_CENTER, spaceBefore=5, spaceAfter=13),
    "code": ParagraphStyle("cd", fontName="Courier", fontSize=8.5, leading=12.5,
                           textColor=colors.HexColor("#12283d"),
                           backColor=colors.HexColor("#f2f5f8"),
                           borderPadding=(6, 7, 6, 7), spaceBefore=4, spaceAfter=9),
    "note": ParagraphStyle("n", fontName="Helvetica", fontSize=9.2, leading=13.5,
                           textColor=INK, backColor=NOTEBG, borderPadding=(8, 9, 8, 9),
                           borderColor=BLUE, borderWidth=0, leftIndent=0, spaceAfter=11),
    "warn": ParagraphStyle("w", fontName="Helvetica", fontSize=9.2, leading=13.5,
                           textColor=INK, backColor=WARNBG, borderPadding=(8, 9, 8, 9),
                           spaceAfter=11),
    "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8.8, leading=12,
                         textColor=colors.white),
    "td": ParagraphStyle("td", fontName="Helvetica", fontSize=8.8, leading=12.3,
                         textColor=INK),
    "tdm": ParagraphStyle("tdm", fontName="Courier", fontSize=8.2, leading=12.3,
                          textColor=colors.HexColor("#12283d")),
}

_fig_n = [0]


def fig(name, caption, width=None):
    """Place a screenshot scaled to fit, with a numbered caption."""
    path = FIG / f"{name}.png"
    iw, ih = PILImage.open(path).size
    w = width or min(CW, iw / 2.4)
    h = w * ih / iw
    max_h = 4.6 * inch
    if h > max_h:
        h = max_h
        w = h * iw / ih
    _fig_n[0] += 1
    img = Image(str(path), width=w, height=h)
    img.hAlign = "CENTER"
    return KeepTogether([img, Paragraph(f"Figure {_fig_n[0]} — {caption}", S["cap"])])


def table(rows, widths, head=True):
    data = []
    for i, row in enumerate(rows):
        style = S["th"] if (head and i == 0) else None
        data.append([Paragraph(c, style or (S["tdm"] if c.startswith(("`", "Y =")) or
                    ("_" in c and "." in c) else S["td"])) for c in row])
    t = Table(data, colWidths=widths, repeatRows=1 if head else 0)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
        ("BOX", (0, 0), (-1, -1), 0.6, RULE),
    ]
    if head:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), NAVY),
                 ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")])]
    t.setStyle(TableStyle(cmds))
    return t


def steps(items):
    return [Paragraph(t, S["step"], bulletText=f"{i}.") for i, t in enumerate(items, 1)]


def bullets(items):
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def decorate(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(MARGIN, H - 0.62 * inch,
                          "Canvas Discussion Grader — Standard Operating Procedure")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, H - 0.7 * inch, W - MARGIN, H - 0.7 * inch)
        canvas.line(MARGIN, 0.72 * inch, W - MARGIN, 0.72 * inch)
        canvas.drawString(MARGIN, 0.56 * inch, "Harvard University — Teaching Staff")
        canvas.drawRightString(W - MARGIN, 0.56 * inch, f"Page {doc.page}")
    canvas.restoreState()


doc = BaseDocTemplate(str(OUT), pagesize=letter,
                      leftMargin=MARGIN, rightMargin=MARGIN,
                      topMargin=0.95 * inch, bottomMargin=0.95 * inch,
                      title="Canvas Discussion Grader SOP",
                      author="Harvard University — Teaching Staff")
doc.addPageTemplates([PageTemplate(id="main",
                                   frames=[Frame(MARGIN, 0.95 * inch, CW, H - 1.9 * inch)],
                                   onPage=decorate)])

E = []
A = E.append

# ---------------------------------------------------------------- cover
A(Spacer(1, 1.5 * inch))
A(Paragraph("Canvas Discussion Grader", S["title"]))
A(Paragraph("Standard Operating Procedure", S["sub"]))
A(Paragraph("Grading discussion participation with a normal-distribution model", S["subq"]))
A(Spacer(1, 0.55 * inch))
A(table([
    ["Document version", "2.0"],
    ["Applies to release", "v1.0.1 and later"],
    ["Effective", "Fall 2026"],
    ["Canvas site", "https://canvas.harvard.edu"],
    ["Download", "github.com/eldeemer88/canvas_discussion/releases/latest"],
    ["Source", "github.com/eldeemer88/canvas_discussion"],
], [2.0 * inch, CW - 2.0 * inch], head=False))
A(Spacer(1, 0.4 * inch))
A(Paragraph(
    "<b>This tool runs entirely on your own computer.</b> Your Canvas access token and "
    "your students' data never leave your machine — there is no server, no account to "
    "create, and nothing is uploaded anywhere.", S["note"]))
A(PageBreak())

# ---------------------------------------------------------------- 1
A(Paragraph("1. Purpose and Scope", S["h1"]))
A(Paragraph(
    "The Canvas Discussion Grader reads every discussion post and reply in a Canvas course "
    "and converts participation into grades using a normal-distribution model. Each student "
    "receives a participation score, the class distribution is fitted, and each student's "
    "z-score determines their grade tier.", S["body"]))
A(Paragraph("The tool produces:", S["body"]))
A(Spacer(1, 2))
for p in bullets([
    "A per-student breakdown of posts, replies, participation score, z-score and grade",
    "A fitted distribution chart and a posts-versus-replies composition chart",
    "Spreadsheet, CSV, image and plain-text exports, all timestamped",
]):
    A(p)
A(Spacer(1, 5))
A(Paragraph("<b>Who this is for.</b> Teaching staff who need to grade discussion participation "
            "consistently across a class. You need a Canvas account with access to the course "
            "and permission to view its discussions.", S["body"]))
A(Paragraph(
    "<b>What changed in version 2.</b> The tool is now a downloadable application rather than "
    "a website. It also filters out the Canvas test student, reports the median alongside the "
    "mean, charts posts against replies, lets you weight posts and replies differently, and "
    "asks which discussions and students to <i>include</i> rather than which to omit.", S["note"]))

# ---------------------------------------------------------------- 2
A(Paragraph("2. Installing the Application", S["h1"]))
A(Paragraph("2.1 Download", S["h2"]))
A(Paragraph("Go to the releases page and download the file matching your computer:", S["body"]))
A(Spacer(1, 2))
A(Paragraph("github.com/eldeemer88/canvas_discussion/releases/latest", S["code"]))
A(table([
    ["Your computer", "File to download"],
    ["Mac with Apple silicon (M1–M4)", "CanvasDiscussionGrader-macOS-AppleSilicon.zip"],
    ["Mac with an Intel processor", "CanvasDiscussionGrader-macOS-Intel.zip"],
    ["Windows", "CanvasDiscussionGrader-Windows.zip"],
], [2.3 * inch, CW - 2.3 * inch]))
A(Spacer(1, 8))
A(Paragraph("To identify your Mac: <b>Apple menu → About This Mac</b>. A chip listed as "
            "\"Apple M1\" or similar means Apple silicon.", S["body"]))

A(Paragraph("2.2 First launch on macOS", S["h2"]))
A(Paragraph(
    "<b>Your Mac will refuse to open the app the first time, and this is expected.</b> The app "
    "is not signed with a paid Apple certificate, so macOS blocks it. The block comes from a "
    "quarantine flag your browser attaches to every download — not from anything wrong with "
    "the application.", S["warn"]))
A(Paragraph(
    "<b>Right-click → Open does not work.</b> Apple removed that bypass in macOS 15 Sequoia. "
    "If you are on Sequoia or later, use one of the two methods below.", S["warn"]))
A(Paragraph("Unzip the download and drag the app into your Applications folder, then:", S["body"]))
A(Spacer(1, 3))
A(Paragraph("<b>Method A — without using Terminal</b>", S["body"]))
for p in steps([
    "Double-click the app. macOS refuses to open it. Dismiss the message.",
    "Open <b>System Settings → Privacy &amp; Security</b>.",
    "Scroll to the <b>Security</b> section. A message names the blocked app.",
    "Click <b>Open Anyway</b> and authenticate with your password or Touch ID.",
]):
    A(p)
A(Spacer(1, 6))
A(Paragraph("<b>Method B — one Terminal command</b>", S["body"]))
A(Paragraph('xattr -dr com.apple.quarantine "/Applications/Canvas Discussion Grader.app"', S["code"]))
A(Paragraph("Either method is needed only once per download. The app opens normally afterwards.",
            S["body"]))

A(Paragraph("2.3 First launch on Windows", S["h2"]))
A(Paragraph(
    "Unzip the download and run <b>CanvasDiscussionGrader.exe</b>. Windows SmartScreen shows "
    "\"Windows protected your PC\". Click <b>More info</b>, then <b>Run anyway</b>. This is "
    "needed only once.", S["body"]))

A(Paragraph("2.4 What happens when it starts", S["h2"]))
A(Paragraph(
    "The application opens in your default web browser. A small window also stays open in the "
    "background — leave it running. When you are finished, click <b>Quit</b> in the top-right "
    "corner of the page.", S["body"]))
A(Paragraph(
    "<b>Results are not saved between sessions.</b> Download any files you need before "
    "quitting.", S["warn"]))

# ---------------------------------------------------------------- 3
A(Paragraph("3. Generating a Canvas Access Token", S["h1"]))
A(Paragraph("The tool authenticates to Canvas with a personal access token that you generate.",
            S["body"]))
for p in steps([
    "Sign in to Canvas at <b>https://canvas.harvard.edu</b>.",
    "Click <b>Account</b> in the left navigation, then <b>Settings</b>.",
    "Scroll to <b>Approved Integrations</b> and click <b>+ New Access Token</b>.",
    "For <b>Purpose</b>, enter a label such as \"Discussion Grading\".",
    "Set an <b>expiry date</b> — see the security note below.",
    "Click <b>Generate Token</b> and copy the token immediately.",
]):
    A(p)
A(Spacer(1, 6))
A(Paragraph(
    "<b>Security.</b> An access token grants full control of your Canvas account to anyone "
    "holding it. Set an expiry date rather than leaving the field blank, never paste a token "
    "into email, chat, a document or a support request, and delete tokens you no longer use "
    "from the same Approved Integrations screen. If a token is ever exposed, delete it there "
    "immediately and generate a replacement.", S["warn"]))
A(Paragraph(
    "The token is shown only once. If you lose it, delete that entry and generate a new one.",
    S["note"]))

# ---------------------------------------------------------------- 4
A(Paragraph("4. Connecting to a Course", S["h1"]))
A(Paragraph("Enter three values in the sidebar and click <b>Connect</b>.", S["body"]))
A(fig("fig_connect", "The Canvas Connection panel"))
A(table([
    ["Field", "Value"],
    ["Canvas URL", "https://canvas.harvard.edu"],
    ["API Access Token", "The token generated in section 3"],
    ["Course ID", "The number in the course web address"],
], [1.5 * inch, CW - 1.5 * inch]))
A(Spacer(1, 9))
A(Paragraph(
    "<b>Finding the Course ID.</b> Open the course in Canvas and look at the address bar. In "
    "<font face=\"Courier\">canvas.harvard.edu/courses/288901</font> the Course ID is "
    "<b>288901</b>.", S["body"]))

A(Paragraph("4.1 Saving a course for next time", S["h2"]))
A(Paragraph(
    "After connecting, give the course a name and click <b>Save Course</b> to add it to Saved "
    "Courses for one-click reconnection. <b>Remember API token</b> is off by default; leave it "
    "off on any shared computer, and the app will ask for the token each time instead.",
    S["body"]))

A(Paragraph("4.2 If the connection fails", S["h2"]))
A(Paragraph(
    "The app diagnoses the failure for you. If your token is valid but the course is not "
    "reachable, it confirms who you are signed in as and lists every course the token "
    "<i>can</i> reach. Click any course in that list to use it.", S["body"]))
A(fig("fig_diagnostics", "A failed connection listing the courses the token can reach"))
A(table([
    ["Message", "What it means"],
    ["Canvas rejected the access token (401)", "The token is wrong, expired, deleted, or was "
     "created on a different Canvas site than the URL you entered."],
    ["Cannot access this course (403)", "The token is valid but the course is not available to "
     "it — commonly an unpublished course or an enrolment that has not started."],
    ["No course with that ID (404)", "The Course ID does not exist on this Canvas site. Check "
     "the number in the course address."],
], [2.15 * inch, CW - 2.15 * inch]))
A(Spacer(1, 8))
A(Paragraph(
    "If the course you want does not appear in the list at all, the issue is in Canvas rather "
    "than the tool: the course is most likely unpublished, or your enrolment is not yet active. "
    "Publishing the course or waiting for the term to begin resolves it.", S["note"]))

# ---------------------------------------------------------------- 5
A(Paragraph("5. Configuring the Analysis", S["h1"]))
A(Paragraph("5.1 Participant filters", S["h2"]))
A(fig("fig_filters", "Participant filters"))
A(Paragraph(
    "<b>Drop Canvas Test Student</b> should stay on. Canvas creates a \"Test Student\" account "
    "the first time an instructor uses Student View, and any posts made while previewing the "
    "course belong to it. Counting that account as a real student distorts the mean, the "
    "standard deviation, and therefore every z-score and every grade. The tool detects it by "
    "enrolment type and reports its removal in the results.", S["body"]))
A(Paragraph(
    "<b>Exclude instructor posts</b> and <b>Exclude TA posts</b> keep teaching staff out of the "
    "distribution. Leave both on unless staff participation is deliberately being graded.",
    S["body"]))

A(Paragraph("5.2 Participation score and weighting", S["h2"]))
A(fig("fig_weights", "The participation score panel", width=2.7 * inch))
A(Paragraph("Each student's participation score is:", S["body"]))
A(Paragraph("Y = &#946;&#8321; &#215; posts + &#946;&#8322; &#215; replies", S["code"]))
A(Paragraph(
    "Both weights default to <b>1</b>, which counts every contribution equally and matches the "
    "original tool. Because a substantive top-level post usually represents more work than a "
    "one-line reply, you may lower the reply weight — setting &#946;&#8322; to 0.5 makes two "
    "replies worth one post. Preset buttons cover the common choices.", S["body"]))
A(Paragraph(
    "Everything downstream follows Y: the mean, median, standard deviation, z-scores, grade "
    "assignment, both charts, and every exported file.", S["body"]))
A(Paragraph(
    "<b>Weights apply instantly after a run.</b> Changing them re-scores the whole class in "
    "about half a second without re-reading anything from Canvas, so you can compare schemes "
    "freely before committing.", S["note"]))

A(Paragraph("5.3 Grading scheme", S["h2"]))
A(fig("fig_scheme", "The grading scheme panel", width=2.7 * inch))
A(Paragraph(
    "Each tier maps a z-score threshold to a grade percentage, evaluated from the top down; the "
    "final <b>else</b> row catches everyone below all thresholds. The default is z &#8805; 1 → "
    "120%, z &#8805; 0 → 100%, z &#8805; &#8722;1 → 80%, otherwise 0%.", S["body"]))
A(Paragraph(
    "Add or remove tiers as needed, and apply whichever scheme the course syllabus specifies. "
    "Duplicate thresholds are flagged, because a repeated value makes the lower tier "
    "unreachable. Like the weights, tier edits re-score instantly after a run.", S["body"]))

A(Paragraph("5.4 Choosing discussions and students", S["h2"]))
A(Paragraph(
    "Both panels work by <b>inclusion</b>: a ticked item is counted. Everything starts ticked, "
    "so a run with no changes covers the whole course.", S["body"]))
A(fig("fig_topics", "Discussion selection", width=2.7 * inch))
for p in bullets([
    "Type in the search box to filter the list.",
    "Click an item to tick or untick it.",
    "<b>Shift-click</b> to select a whole range at once.",
    "<b>+ Visible</b> and <b>&#8722; Visible</b> apply to the current search results — search "
    "for \"Presentation\", click <b>&#8722; Visible</b>, and every presentation topic is dropped.",
    "<b>All</b> and <b>None</b> apply to the entire list.",
]):
    A(p)
A(Spacer(1, 5))
A(fig("fig_students", "Student selection, with the test student locked out", width=2.7 * inch))
A(Paragraph(
    "Students who have dropped the course can be unticked here. The Canvas test student appears "
    "greyed out and cannot be ticked while the filter in section 5.1 is on. The counter above "
    "each list shows how many items are included.", S["body"]))

# ---------------------------------------------------------------- 6
A(Paragraph("6. Running the Analysis", S["h1"]))
for p in steps([
    "Check the filters, weights, grading scheme and both selection lists.",
    "Click <b>Run Analysis</b> at the bottom of the sidebar.",
    "A progress bar names each discussion as it is read.",
]):
    A(p)
A(Spacer(1, 6))
A(Paragraph(
    "Runtime depends on how many discussions the course has; a typical course takes well under "
    "a minute. Large courses take longer because every discussion is fetched individually.",
    S["body"]))
A(Paragraph(
    "You only need to run the analysis once. Adjusting weights or grading tiers afterwards "
    "re-scores from data already held, without contacting Canvas again.", S["note"]))

# ---------------------------------------------------------------- 7
A(Paragraph("7. Reading the Results", S["h1"]))
A(Paragraph("7.1 Summary cards", S["h2"]))
A(fig("fig_cards", "Summary cards"))
A(table([
    ["Card", "Meaning"],
    ["Students", "How many students were analysed, and how many made no contribution at all."],
    ["Mean", "Average participation score, with the standard deviation below it."],
    ["Median", "The midpoint of the class, and its distance from the mean."],
    ["Total Activity", "All contributions, split into posts and replies."],
    ["Grade Distribution", "How many students fell into each grade tier."],
], [1.5 * inch, CW - 1.5 * inch]))
A(Spacer(1, 9))
A(Paragraph(
    "<b>Why both mean and median.</b> Participation is usually skewed: a few very active "
    "students pull the mean above where most of the class actually sits. When the two diverge "
    "noticeably the tool says so, because z-scores are calculated from the mean and a skew "
    "drags every tier boundary with it. A large gap is a reason to check the distribution "
    "before accepting the grades.", S["body"]))

A(Paragraph("7.2 Participation distribution", S["h2"]))
A(fig("fig_chart_dist", "Participation distribution and resulting grade counts"))
A(Paragraph(
    "The left chart bins students by participation score and overlays the fitted normal curve. "
    "The green dashed line marks the mean, the purple dotted line the median, and the amber "
    "lines the &#177;1&#963; boundaries that correspond to grade cutoffs. This chart answers one "
    "question: is the class distribution close enough to normal for z-score grading to be fair? "
    "A badly skewed or strongly bimodal shape is a signal to reconsider the scheme.", S["body"]))

A(Paragraph("7.3 Posts versus replies", S["h2"]))
A(fig("fig_chart_comp", "Composition: posts against replies, and every student ranked"))
A(Paragraph(
    "The left panel plots each student as one point — posts across, replies up — over shaded "
    "grade bands. Because the grade depends on the combined score, the tier boundaries are "
    "straight lines, so <b>any two students on the same band receive the same grade however "
    "differently they earned it</b>. A student clustered near the horizontal axis writes posts "
    "but never engages with classmates; one near the vertical axis only ever replies. The "
    "dotted diagonal marks equal posts and replies.", S["body"]))
A(Paragraph(
    "The right panel shows every student as a single bar split into posts and replies, ordered "
    "by participation, with the tier cutoffs drawn across it. Use it to see who sits just below "
    "a boundary.", S["body"]))
A(fig("fig_chart_comp_weighted",
      "The same class with replies weighted at 0.25 — the grade bands tilt"))
A(Paragraph(
    "Changing the weights tilts the bands. The steeper the tilt, the more the grade depends on "
    "original posts rather than replies, which makes the effect of a weighting choice visible "
    "before you commit to it.", S["body"]))

A(Paragraph("7.4 Student results table", S["h2"]))
A(fig("fig_table", "Per-student results"))
A(Paragraph(
    "Every included student is listed with posts, replies, total, z-score and grade. Click any "
    "column heading to sort, or use the filter box to find a student. A <b>Y</b> column appears "
    "between Total and Z-Score whenever the weights are not both 1; <b>Total</b> always stays "
    "the raw contribution count for checking.", S["body"]))

# ---------------------------------------------------------------- 8
A(Paragraph("8. Exporting Results", S["h1"]))
A(fig("fig_files", "Export files"))
A(Paragraph(
    "Download files individually, or take all five at once with <b>Download All (.zip)</b>. "
    "Filenames carry a timestamp so successive runs never overwrite each other.", S["body"]))
A(table([
    ["Type", "Filename", "Contents"],
    ["XLSX", "discussion_grades_{ts}.xlsx", "Grades, z-scores, summary statistics, the grading "
     "scheme, and both charts"],
    ["CSV", "discussion_raw_data_{ts}.csv", "Per-student post and reply counts for checking"],
    ["PNG", "discussion_analysis_{ts}.png", "Participation distribution and grade counts"],
    ["PNG", "discussion_composition_{ts}.png", "Posts-versus-replies charts"],
    ["TXT", "last_run_log_{ts}.txt", "Weights, mean, median, standard deviation, grade "
     "breakdown, and students with no participation"],
], [0.6 * inch, 2.05 * inch, CW - 2.65 * inch]))
A(Spacer(1, 9))
A(Paragraph(
    "<b>Download before quitting.</b> Results live in memory only. Once the app closes, or if "
    "it is left idle for two hours, they are gone and the analysis must be run again.",
    S["warn"]))
A(Paragraph(
    "The exports always reflect the weights and grading scheme currently applied, and the log "
    "and spreadsheet both record the score formula used, so an exported file can always be "
    "traced back to the settings that produced it.", S["body"]))

# ---------------------------------------------------------------- 9
A(Paragraph("9. Troubleshooting", S["h1"]))
A(table([
    ["Symptom", "Cause and remedy"],
    ["macOS: \"cannot be opened because the developer cannot be verified\"",
     "Expected on first launch. Follow section 2.2. Right-click → Open does not work on "
     "macOS 15 Sequoia or later."],
    ["Windows: \"Windows protected your PC\"",
     "Expected on first launch. Click More info, then Run anyway."],
    ["Connection fails with a 401",
     "The token is wrong, expired, or belongs to a different Canvas site. Generate a new one "
     "(section 3) and confirm the Canvas URL."],
    ["Connection fails with a 403",
     "The token works but cannot reach that course. Use the course list the app offers. If the "
     "course is absent it is probably unpublished or your enrolment has not started."],
    ["A student is missing from the results",
     "Check they are ticked in Include Students, that they are not the Canvas test student, and "
     "that they are not enrolled as staff."],
    ["Participation counts look too low",
     "Check Include Discussions — a filtered search plus a bulk action can leave topics "
     "unticked. The counter shows how many are included."],
    ["Grades changed without re-running",
     "Weights or grading tiers were edited; both re-score instantly. The formula is shown "
     "beside the distribution heading."],
    ["Results vanished",
     "Results are not stored. Re-run the analysis, and download the files before quitting."],
], [1.85 * inch, CW - 1.85 * inch]))

# ---------------------------------------------------------------- 10
A(Paragraph("10. Method and Assumptions", S["h1"]))
A(table([
    ["Item", "Definition"],
    ["Post", "A top-level entry in a discussion topic."],
    ["Reply", "Any entry nested beneath another. Deleted entries are skipped, but replies to "
     "them still count."],
    ["Participation score (Y)", "&#946;&#8321; &#215; posts + &#946;&#8322; &#215; replies, "
     "both weights defaulting to 1."],
    ["Standard deviation", "Sample standard deviation (ddof = 1)."],
    ["Z-score", "(Y &#8722; mean) &#247; standard deviation. Zero for everyone if the class has "
     "no variation."],
    ["Grade", "The first tier, highest first, whose threshold the z-score meets."],
    ["Students with zero posts", "Counted on raw contributions, so a student who only replies "
     "is never reported as inactive even when replies are weighted to zero."],
], [1.75 * inch, CW - 1.75 * inch]))
A(Spacer(1, 10))
A(Paragraph(
    "Z-scores are calculated from the <b>mean</b>, following the original procedure. The median "
    "is reported for comparison but does not determine grades. Grading relative to the median "
    "would be more robust to skew and is a straightforward change to the source if the class "
    "distribution ever warrants it.", S["body"]))
A(Paragraph(
    "<b>Judgement still applies.</b> The tool measures the volume of contributions, not their "
    "quality. A student may post frequently and add little, or post rarely and add a great "
    "deal. Treat the output as a consistent starting point, and review the students near tier "
    "boundaries before publishing grades.", S["warn"]))

doc.build(E)
print("wrote", OUT)
