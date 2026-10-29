"""Controlled, offline renderer for the validated Distill contracts."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from functools import cache
from pathlib import Path

from .chapters import NOTE_LEAF_LIMITS
from .deck_layouts import (ROOM, VARIANTS, Choice, Editable, arrange, column_choices, fits, level_choices, point_choices, small_icons,
                           stat_choices, step_choices, table_choices, timeline, timeline_choices)
from .deck_layouts import e as slide_text
from .deck_layouts import items as layout_items
from .figures import figure_ideas, figure_sections, figure_slides
from .looks import LOOKS_CSS, SLIDE_THEMES, designed_looks, font_faces
from .models import (Chapter, FigurePlan, KnowledgeModel, LectureColumn, LectureEntry, LecturePlan, LectureSlide, PresentationPlan, Transcript,
                     figure_unit_ids, validate_bundle, validate_figures, validate_lecture)

ASSET_DIR = Path(__file__).parent / "reader_assets"


DATA_LAYOUTS = {"pyramid", "pyramid-outline", "pyramid-left", "funnel", "big-numbers", "circle-stats", "bar-stats", "table", "table-3row"}
# Where the deck switches from the stacked phone list to the fixed canvas. Every asset spells the media query this way.
CANVAS = "(min-width:761px)"


def library_css(name: str) -> str:
    """A slide-design library file, applied to the fixed 1280x720 canvas only (presenting and every printed page).
    Phones read the slides as a plain stacked list instead. @page cannot sit inside @media; the deck sets it."""
    css = re.sub(r"@page\s*\{[^}]*\}", "", (ASSET_DIR / name).read_text(encoding="utf-8"))
    return f"@media {CANVAS}{{\n" + css + "\n}"


def canvas_everywhere(css: str) -> str:
    """A phone copy presents at any width: an iPhone held sideways is only 734px wide, so the canvas rules always apply.
    No narrow-screen rule does (the stacked list, figures that restack below 850px): the slide is always 1280px inside."""
    return re.sub(r"\(max-width:\s*\d+px\)", "(max-width:0px)", css.replace(CANVAS, "(min-width:0px)"))


def assets(name: str, figures: FigurePlan | None, layouts: set[str] = frozenset()) -> tuple[str, str]:
    """Inline stylesheet and script tags; figure assets only travel with figures, data layouts only with data slides."""
    css = (ASSET_DIR / f"{name}.css").read_text(encoding="utf-8")
    if layouts:
        css += "\n" + library_css("slide-layouts.css")
        if layouts & DATA_LAYOUTS:
            css += "\n" + library_css("slide-data.css")
        css += "\n" + (ASSET_DIR / f"{name}-layouts.css").read_text(encoding="utf-8")
    scripts = [(ASSET_DIR / f"{name}.js").read_text(encoding="utf-8")]
    if figures and figures.figures:
        css += "\n" + (ASSET_DIR / "figures.css").read_text(encoding="utf-8")
        scripts.append((ASSET_DIR / "figures.js").read_text(encoding="utf-8"))
    return css, "".join(f"<script>{script}</script>" for script in scripts)


def render_page(source: Transcript, knowledge: KnowledgeModel, presentation: PresentationPlan, output: Path,
                figures: FigurePlan | None = None) -> Path:
    """Write one portable HTML document; source text never becomes executable code."""
    validate_bundle(source, knowledge, presentation)
    if figures:
        validate_figures(knowledge, figures)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = {"source": source.model_dump(mode="json"), "knowledge": knowledge.model_dump(mode="json"),
            "presentation": presentation.model_dump(mode="json"), "reader": {"note_leaf_limits": NOTE_LEAF_LIMITS}}
    # Only include source fields required by the reader. Arbitrary import metadata
    # can contain local paths or service information and does not belong in exports.
    data["source"].pop("metadata", None)
    encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    vi = knowledge.language == "vi"
    escape = html.escape
    fallback = "".join(f'<details><summary>{escape(unit.title)}</summary><p>{escape(unit.summary)}</p><p>{escape(unit.explanation)}</p>'
                       + "".join(f'<p class="caveat">{escape(c)}</p>' for c in unit.caveats)
                       + "".join(f'<blockquote>{escape(e.quote)}</blockquote>' for e in unit.evidence) + "</details>"
                       for unit in knowledge.units)
    source_fallback = "".join(f'<p><b>{escape(s.id)}</b> {escape(s.text)}</p>' for s in source.snippets)
    css, scripts = assets("reader", figures)
    theme_script = (ASSET_DIR.parent / "web" / "theme.js").read_text(encoding="utf-8")
    page = f'''<!doctype html>
<html lang="{knowledge.language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light"><meta name="referrer" content="no-referrer"><script>{theme_script}</script>
<title>{escape(source.title)} · Distill</title><style>{css}</style></head>
<body><a class="skip-link" href="#overview">{'Đến nội dung' if vi else 'Skip to content'}</a>
<header class="reader-header"><a class="wordmark" href="#overview"><span aria-hidden="true">◈</span> Distill</a>
<span class="offline-label">{'Trang đã lưu · đọc ngoại tuyến' if vi else 'Saved page · offline reading'}</span>
<button id="theme-toggle" type="button">{'Chế độ sáng' if vi else 'Light mode'}</button>
<button id="print-button" type="button">{'In / PDF' if vi else 'Print / PDF'}</button></header>
<main id="reader"><section id="overview" class="orientation"><p class="eyebrow">{'BỨC TRANH TOÀN CẢNH' if vi else 'THE BIG PICTURE'}</p>
<h1>{escape(source.title)}</h1><p class="main-question">{escape(knowledge.main_question)}</p><p class="conclusion">{escape(knowledge.main_conclusion)}</p>
<div id="source-meta" class="source-meta"></div><div id="global-limitations"></div></section>
<nav id="view-nav" class="view-nav" aria-label="{'Các góc nhìn' if vi else 'Learning views'}"></nav>
<div class="learning-layout"><div id="visuals">{figure_sections(knowledge, figures)}</div>
<aside id="detail-panel" class="detail-panel" aria-label="{'Chi tiết ý tưởng' if vi else 'Idea detail'}"><div id="detail-content"></div></aside></div>
<details id="source-browser" class="source-browser"><summary class="transcript-heading">{'Bản chép lời gốc' if vi else 'Original transcript'}</summary><div class="section-heading"><p>{'Giữ nguyên ngôn ngữ và mốc thời gian của nguồn.' if vi else 'Original language and source times are preserved.'}</p></div>
<label class="search-label" for="source-search">{'Tìm trong bản chép lời' if vi else 'Search transcript'}</label><input id="source-search" type="search" autocomplete="off">
<p id="source-result-count" class="subtle" aria-live="polite"></p><div id="transcript-list"></div><button id="load-source" type="button"></button></details>
<noscript><section><h2>{'Các ý tưởng và bằng chứng' if vi else 'Ideas and evidence'}</h2>{fallback}<details><summary>{'Toàn bộ nguồn' if vi else 'Complete source'}</summary>{source_fallback}</details></section></noscript>
</main><p id="reader-status" class="sr-only" role="status" aria-live="polite"></p>
<footer>{'Một mô hình để khám phá nguồn. Liên kết video cần kết nối Internet.' if vi else 'A mental model for exploring the source. Video links need an internet connection.'}</footer>
<script type="application/json" id="learning-data">{encoded}</script>{scripts}</body></html>'''
    return write_page(output, page)


def write_page(output: Path, page: str) -> Path:
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(page, encoding="utf-8")
    os.replace(temporary, output)
    return output


def clock(seconds: float) -> str:
    seconds = int(seconds)
    hours, minutes, rest = seconds // 3600, seconds % 3600 // 60, seconds % 60
    return f"{hours}:{minutes:02d}:{rest:02d}" if hours else f"{minutes}:{rest:02d}"


def excerpt(text: str, limit: int = 420) -> str:
    """Shorten a verbatim quote at a word boundary; the notes keep the full quote."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + " …"


# Slides that frame the talk arrive whole; the others reveal their items one advance at a time.
STILL = {"title", "objectives", "question", "agenda", "divider", "limits"}


@cache
def text_limit(model, name: str) -> int:
    """The most characters a contract allows in a text field, or in each text of a list field."""
    schema = model.model_json_schema()["properties"][name]
    return schema.get("maxLength") or schema["items"]["maxLength"]


def editable_plan(lecture: LecturePlan) -> LecturePlan:
    """The plan with each text a person may edit marked with its place in lecture.json, for the deck's edit mode."""
    def texts(values, field, model, name):
        return [Editable(value, f"{field}.{index}", text_limit(model, name)) for index, value in enumerate(values)]

    def slide(at, value):
        return value.model_copy(update={
            "title": Editable(value.title, f"{at}.title", text_limit(LectureSlide, "title")),
            "points": texts(value.points, f"{at}.points", LectureSlide, "points"),
            "columns": [column.model_copy(update={
                "heading": Editable(column.heading, f"{at}.columns.{k}.heading", text_limit(LectureColumn, "heading")),
                "points": texts(column.points, f"{at}.columns.{k}.points", LectureColumn, "points")}) for k, column in enumerate(value.columns)],
            "entries": [entry.model_copy(update={
                "label": Editable(entry.label, f"{at}.entries.{k}.label", text_limit(LectureEntry, "label")),
                "text": Editable(entry.text, f"{at}.entries.{k}.text", text_limit(LectureEntry, "text"))}) for k, entry in enumerate(value.entries)],
            "notes": Editable(value.notes, f"{at}.notes", text_limit(LectureSlide, "notes"))})

    parts = [part.model_copy(update={"slides": [slide(f"parts.{p}.slides.{s}", value) for s, value in enumerate(part.slides)]})
             for p, part in enumerate(lecture.parts)]
    return lecture.model_copy(update={"title": Editable(lecture.title, "title", text_limit(LecturePlan, "title")),
                                      "objectives": texts(lecture.objectives, "objectives", LecturePlan, "objectives"),
                                      "takeaways": texts(lecture.takeaways, "takeaways", LecturePlan, "takeaways"), "parts": parts})


def render_lecture(source: Transcript, knowledge: KnowledgeModel, lecture: LecturePlan, output: Path,
                   figures: FigurePlan | None = None, theme: str = "forest", phone: bool = False) -> Path:
    """Write one portable slide deck (see lecture_page)."""
    output = Path(output)
    page = lecture_page(source, knowledge, lecture, figures, theme, phone)
    output.parent.mkdir(parents=True, exist_ok=True)
    return write_page(output, page)


def lecture_page(source: Transcript, knowledge: KnowledgeModel, lecture: LecturePlan, figures: FigurePlan | None = None,
                 theme: str = "forest", phone: bool = False, editable: bool = False) -> str:
    """One portable slide deck. Slides teach validated knowledge; quotes and times come from the source.

    The theme names the deck's look; light and dark mode stay the viewer's choice. A phone copy is for presenting from
    a phone whose screen is mirrored to a TV: it always presents, and only the slide shows until ⋯ brings the controls.
    An editable deck is the app's edit mode: the same slides, with the text a person may change marked in place."""
    validate_lecture(knowledge, lecture)
    if figures:
        validate_figures(knowledge, figures)
    if editable:
        lecture = editable_plan(lecture)
    vi = knowledge.language == "vi"
    t = lambda en, vn: vn if vi else en
    e = html.escape
    units = {u.id: u for u in knowledge.units}
    snippets = {s.id: s for s in source.snippets}
    sections = {s.id: s for s in knowledge.sections}
    chapters = {c.id: c for c in knowledge.chapters}
    status_labels = {"uncertain": t("Uncertain", "Chưa chắc chắn"), "inference": t("Inference", "Suy luận"),
                     "background": t("Added background", "Kiến thức bổ sung")}

    def time_link(seconds):
        if source.video_id:
            return (f'<a class="time" href="https://www.youtube.com/watch?v={source.video_id}&amp;t={int(seconds)}s" '
                    f'target="_blank" rel="noopener noreferrer">▶ {clock(seconds)}</a>')
        return f'<span class="time">{clock(seconds)}</span>'

    def attribution(evidence):
        first = snippets[evidence.snippet_ids[0]]
        parts = [e(first.speaker)] if first.speaker else []
        if first.start is not None:
            parts.append(time_link(first.start))
        return " · ".join(parts)

    def cited(ids):
        return [evidence for uid in ids for evidence in units[uid].evidence[:1]]

    def badges(statuses):
        return "".join(f'<span class="status {name}">{label}</span>' for name, label in status_labels.items() if name in statuses)

    def source_times(ids):
        starts = {snippets[ev.snippet_ids[0]].start for ev in cited(ids)} - {None}
        return " ".join(time_link(start) for start in sorted(starts)[:3])

    def items(values, tag="ul", cls="points"):
        return f'<{tag} class="{cls}">' + "".join(f"<li>{e(value)}</li>" for value in values) + f"</{tag}>"

    def quotes(evidence):
        return "".join(f"<blockquote>{e(ev.quote)}<cite>{attribution(ev)}</cite></blockquote>" for ev in evidence)

    def notes_for(text, ids=()):
        body = "".join(f"<p>{e(paragraph)}</p>" for paragraph in text.split("\n") if paragraph.strip())
        if isinstance(text, Editable):  # the notes are one text to edit, an empty one included
            body = (f'<div class="notes-text" data-field="{text.field}" data-limit="{text.limit}" data-lines '
                    f'data-placeholder="{t("Type what you will say on this slide.", "Nhập lời bạn sẽ nói ở slide này.")}">{body}</div>')
        caveats = [caveat for uid in ids for caveat in units[uid].caveats][:3]
        if caveats:
            body += f'<p class="notes-label">{t("Caveats", "Lưu ý")}</p>' + items(caveats, cls="caveats")
        if cited(ids):
            body += f'<p class="notes-label">{t("From the source", "Trích nguồn")}</p>' + quotes(cited(ids)[:3])
        return body

    def chapter_start(chapter):
        timed = [snippets[sid].start for section_id in chapter.section_ids for sid in sections[section_id].snippet_ids
                 if snippets[sid].start is not None]
        return clock(min(timed)) if timed else ""

    def chapter_times(chapter):
        timed = [snippets[sid] for section_id in chapter.section_ids for sid in sections[section_id].snippet_ids
                 if snippets[sid].start is not None]
        if not timed:
            return ""
        return f"{clock(min(s.start for s in timed))} – {clock(max(s.end or s.start for s in timed))}"

    slides = []

    def add(kind, title, content="", *, eyebrow="", heading=None, notes="", footer="", marks="", choices=None):
        """A slide; `choices` lists the library layouts its content fits, and `arrange` picks one."""
        slides.append({"kind": kind, "title": title, "eyebrow": eyebrow, "marks": marks, "content": content,
                       "heading": f'<h2 data-part="0">{slide_text(title)}</h2>' if heading is None else heading, "notes": notes,
                       "footer": footer, "choices": choices})

    def chapter_ideas(chapter_id):
        chapter = chapters.get(chapter_id)
        roots = [*chapter.unit_ids, *(uid for sid in chapter.section_ids for uid in sections[sid].unit_ids)] if chapter else list(knowledge.overview_ids)
        found, stack = set(), roots
        while stack:
            uid = stack.pop()
            if uid in units and uid not in found:
                found.add(uid)
                stack.extend(units[uid].child_ids)
        return found

    # A figure follows the part whose chapter holds most of the ideas it cites; the rest come before the summary.
    placed = {}
    for number, figure in enumerate(figures.figures if figures else [], 1):
        cited_ideas = figure_unit_ids(figure)
        overlap, index = max(((len(cited_ideas & chapter_ideas(part.chapter_id)), -index) for index, part in enumerate(lecture.parts)), default=(0, 0))
        placed.setdefault(-index if overlap else None, []).append((number, figure))

    def add_figures(key, eyebrow):
        for number, figure in placed.get(key, []):
            ids = figure_ideas(figure)
            text = "\n".join([figure.reader_question, figure.caption, *([f"{p.label}: {p.note}" for p in figure.process.phases if p.note] if figure.process else [])])
            for slide in figure_slides(knowledge, figure, number):
                add("figure", slide["title"], slide["content"], eyebrow=eyebrow, marks=badges({units[uid].status for uid in ids}),
                    notes=notes_for(text, ids[:6]), footer=source_times(ids))

    timed = [s for s in source.snippets if s.start is not None]
    speakers = {s.speaker for s in source.snippets if s.speaker}
    meta = []
    if timed:
        minutes = max(1, round(max(s.end or s.start for s in timed) / 60))
        meta.append((t("Length", "Thời lượng"), t(f"{minutes} min", f"{minutes} phút")))
    if len(speakers) > 1:
        meta.append((t("Speakers", "Người nói"), str(len(speakers))))
    meta.append((t("Parts", "Số phần"), str(len(lecture.parts))))
    cover = (f'<p class="lead" data-part="1">{e(excerpt(source.title, 120))}</p><dl class="meta" data-part="2">'
             + "".join(f"<div><dt>{e(name)}</dt><dd>{e(value)}</dd></div>" for name, value in meta) + "</dl>")
    add("title", lecture.title, eyebrow=t("LECTURE", "BÀI GIẢNG"), heading=f'<h1 data-part="0">{slide_text(lecture.title)}</h1>',
        choices=[Choice("title", VARIANTS if len(lecture.title) <= 48 * ROOM else (1, 2, 4), lambda: cover)])
    add("objectives", t("After this lecture you can", "Sau bài này, bạn có thể"), eyebrow=t("LEARNING OBJECTIVES", "MỤC TIÊU BÀI HỌC"),
        choices=[c for c in point_choices("", lecture.objectives, t) if c.layout != "accent"])
    # The central question reads as a statement; the heading gives it context.
    question = f'<figure class="quote" data-part="1"><blockquote><p>{e(knowledge.main_question)}</p></blockquote></figure>'
    add("question", knowledge.main_question, eyebrow=t("THE CENTRAL QUESTION", "CÂU HỎI TRUNG TÂM"),
        heading=f'<h2 data-part="0">{t("This talk answers", "Bài giảng trả lời")}</h2>', choices=[Choice("quote", (2, 4), lambda: question)])
    # Part titles are the chapter titles of the knowledge model; edit mode changes them there.
    part_titles = {chapter.id: Editable(chapter.title, f"chapters.{index}.title", text_limit(Chapter, "title")) if editable else chapter.title
                   for index, chapter in enumerate(knowledge.chapters)}
    titles = [part_titles[part.chapter_id] if part.chapter_id in chapters else knowledge.main_question for part in lecture.parts]
    starts = [chapter_start(chapters[part.chapter_id]) if part.chapter_id in chapters else "" for part in lecture.parts]
    if len(lecture.parts) > 1:
        agenda = [c for c in point_choices("", titles, t) if c.layout in ("bullets", "big-bullets")]
        if 4 <= len(titles) <= 8 and fits(titles, 60):
            agenda.append(Choice("small-icons", VARIANTS, lambda: small_icons(titles)))
        if 3 <= len(titles) <= 5 and all(starts) and fits(titles, 32):
            agenda.append(Choice("timeline-v", (1, 2, 3), lambda: timeline([(when, title, None) for when, title in zip(starts, titles)])))
        add("agenda", t("Agenda", "Nội dung"), eyebrow=t("ROADMAP", "LỘ TRÌNH"), choices=agenda)
    # Section slides list every part, the current one marked, when the titles are short enough to index.
    indexed = 3 <= len(titles) <= 6 and fits(titles, 28)
    for number, (part, title) in enumerate(zip(lecture.parts, titles), 1):
        if len(lecture.parts) > 1:
            span = chapter_times(chapters[part.chapter_id]) if part.chapter_id in chapters else ""
            section = (f'<p class="part-num" data-part="1">{number:02d}</p>' + (f'<p class="lead" data-part="2">{span}</p>' if span else "")
                       + ('<ol class="parts" data-part="3">' + "".join(f'<li{" aria-current=\"true\"" if k == number else ""}>{e(name)}</li>'
                                                                        for k, name in enumerate(titles, 1)) + "</ol>" if indexed else ""))
            add("divider", title, eyebrow=t(f"PART {number}", f"PHẦN {number}"),
                choices=[Choice("section", VARIANTS if indexed else (1, 2, 3), lambda section=section: section)])
        for slide in part.slides:
            if slide.layout == "points":
                choices = point_choices(slide.title, slide.points, t)
            elif slide.layout == "steps":
                choices = step_choices(slide.points, t)
            elif slide.layout == "timeline":
                choices = timeline_choices(slide.entries, t)
            elif slide.layout in ("compare", "columns"):
                choices = column_choices(slide.layout, slide.columns)
            elif slide.layout == "table":
                choices = table_choices(slide.columns)
            elif slide.layout in ("pyramid", "funnel"):
                choices = level_choices(slide.layout, slide.entries)
            elif slide.layout == "stats":
                choices = stat_choices(slide.entries)
            else:  # quote: the original passage, its speaker and time, then why it matters
                evidence = min(cited(slide.unit_ids)[:3], key=lambda ev: len(ev.quote))
                passage = (f'<figure class="quote" data-part="1"><blockquote><p>{e(excerpt(evidence.quote, 200))}</p></blockquote>'
                           f'<figcaption><span class="who">{attribution(evidence) or e(source.title)}</span>'
                           f'<span class="role">{e(excerpt(source.title, 50))}</span></figcaption></figure>'
                           + layout_items(slide.points, "quote-points"))
                choices = [Choice("quote", VARIANTS, lambda passage=passage: passage)]
            add(slide.layout, slide.title, eyebrow=e(title), marks=badges({units[uid].status for uid in slide.unit_ids}),
                notes=notes_for(slide.notes, slide.unit_ids), footer=source_times(slide.unit_ids), choices=choices)
        add_figures(number - 1, e(title))
    add_figures(None, t("FIGURE", "HÌNH"))
    conclusion = f'<p class="lede conclusion" data-part="1">{e(knowledge.main_conclusion)}</p>'
    caveats = items(knowledge.main_conclusion_caveats, cls="caveats") if knowledge.main_conclusion_caveats else ""
    # A short summary sits in the tinted panel; a long one needs the full width of plain rows.
    summary_length = len(knowledge.main_conclusion) + sum(map(len, lecture.takeaways)) + sum(map(len, knowledge.main_conclusion_caveats))
    recap = [Choice("bullets", (3,) if summary_length <= 600 else (1,), lambda: conclusion + layout_items(lecture.takeaways, "bullets") + caveats)]
    if 2 <= len(lecture.takeaways) <= 4 and fits(lecture.takeaways, 56):
        # The first takeaway restates the main conclusion, so the lead variant's emphasis is true here.
        recap.append(Choice("big-bullets", VARIANTS, lambda: conclusion + layout_items(lecture.takeaways, "big-list", "ol") + caveats))
    recap_notes = (f'<p class="notes-label">{t("From the source", "Trích nguồn")}</p>' + quotes(knowledge.main_conclusion_evidence[:3])
                   if knowledge.main_conclusion_evidence else "")
    add("recap", t("What to remember", "Điều cần nhớ"), eyebrow=t("SUMMARY", "TÓM TẮT"),
        marks=badges({knowledge.main_conclusion_status}), notes=recap_notes, choices=recap)
    limits = (small_icons(knowledge.limitations[:5]) if knowledge.limitations
              else f'<p>{t("No limitations were recorded for this source.", "Không có giới hạn nào được ghi nhận cho nguồn này.")}</p>')
    link = (f'<a href="https://www.youtube.com/watch?v={source.video_id}" target="_blank" rel="noopener noreferrer">{e(source.title)}</a>'
            if source.video_id else e(source.title))
    limits += (f'<p class="source-line">{t("Source", "Nguồn")}: {link}</p>'
               f'<p class="source-line">{t("Slides teach a knowledge model checked against original quotations. AI explanations can still be wrong.", "Slide được viết từ mô hình kiến thức đã đối chiếu với trích dẫn gốc. Phần giải thích của AI vẫn có thể sai.")}</p>')
    add("limits", t("Limits and source", "Giới hạn và nguồn"), eyebrow=t("BEFORE YOU REUSE THIS", "TRƯỚC KHI DÙNG LẠI"),
        choices=[Choice("small-icons", (3,), lambda: limits)])  # a full-width checklist, unlike the summary before it

    total = len(slides)
    no_notes = f'<p class="muted">{t("No presenter notes for this slide.", "Slide này không có ghi chú.")}</p>'
    frames = []
    # The deck title sets where each rotation starts, so one-off slides such as the title also vary from deck
    # to deck, and a re-render of the same deck is stable. A renamed deck keeps the title it was made with here.
    arrange(slides, int(hashlib.sha256((lecture.layout_seed or lecture.title).encode("utf-8")).hexdigest()[:8], 16))
    for index, slide in enumerate(slides, 1):
        layout = f' layout-{slide["layout"]} variant-{slide["variant"]}' if slide.get("layout") else ""
        # Only content slides build step by step; the frame slides arrive whole.
        content = slide["content"] if slide["kind"] not in STILL else slide["content"].replace(" data-build", "")
        # Top bar: label, status marks and the slide number. Foot line: source times and the deck title.
        head = f'<header class="slide-head"><p class="eyebrow">{slide["eyebrow"]}</p>{slide["marks"]}<span class="count">{index:02d} / {total:02d}</span></header>'
        frames.append(f'<article class="slide-frame" id="slide-{index}" role="group" aria-roledescription="slide" aria-label="{index} / {total}: {e(slide["title"])}">'
                      f'<div class="slide-box"><section class="slide kind-{slide["kind"]}{layout}">{head}{slide["heading"]}<div class="slide-content">{content}</div>'
                      f'<footer class="slide-foot"><span class="sources">{slide["footer"]}</span><span class="deck-name">{e(lecture.title)}</span></footer></section></div>'
                      f'<aside class="notes" aria-label="{t("Presenter notes", "Ghi chú người trình bày")}">{slide["notes"] or no_notes}</aside></article>')
    outline = "".join(f'<li><button type="button" data-go="{index}">{e(slide["title"])}</button></li>' for index, slide in enumerate(slides, 1))
    css, scripts = assets("lecture", figures, {slide["layout"] for slide in slides if slide.get("layout")})
    theme = theme if theme in SLIDE_THEMES else "forest"
    # A look whose type most devices lack carries its font, so the deck looks the same on a phone or another computer.
    type_stacks = designed_looks()[theme]["display"], designed_looks()[theme]["sans"]
    css = font_faces(*type_stacks) + LOOKS_CSS.read_text(encoding="utf-8") + "\n" + css
    theme_script = (ASSET_DIR.parent / "web" / "theme.js").read_text(encoding="utf-8")
    mode, viewport, phone_head, phone_controls = "", "width=device-width,initial-scale=1", "", ""
    if phone:
        css = canvas_everywhere(css)
        # Added to the home screen, the deck opens without the browser's bars; the slide sits clear of the notch.
        mode, viewport = ' data-mode="phone"', viewport + ",viewport-fit=cover"
        phone_head = ('<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes">'
                      '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">')
        phone_controls = (f'<button id="controls-toggle" class="controls-toggle" type="button" aria-expanded="false" '
                          f'aria-label="{t("Show controls", "Hiện điều khiển")}">⋯</button>'
                          f'<p class="rotate-hint">{t("Turn the phone sideways to present.", "Xoay ngang điện thoại để trình chiếu.")}</p>')
    if editable:
        css += "\n" + (ASSET_DIR / "lecture-edit.css").read_text(encoding="utf-8")
        scripts += f'<script>{(ASSET_DIR / "lecture-edit.js").read_text(encoding="utf-8")}</script>'
    return f'''<!doctype html>
<html lang="{knowledge.language}" data-look="{theme}"{mode}><head><meta charset="utf-8"><meta name="viewport" content="{viewport}">
<meta name="color-scheme" content="dark light"><meta name="referrer" content="no-referrer">{phone_head}<script>{theme_script}</script>
<script>document.documentElement.classList.add('js-deck')</script>
<title>{e(lecture.title)} · Distill</title><style>{css}</style><noscript><style>.deck-bar button{{display:none}}</style></noscript></head>
<body><header class="deck-bar"><span class="wordmark"><span aria-hidden="true">◈</span> Distill</span>
<span class="deck-title">{e(lecture.title)}</span>
<button id="outline-button" type="button" aria-haspopup="dialog">{t("Slides", "Danh sách slide")}</button>
<button id="notes-toggle" type="button" aria-pressed="false" title="N">{t("Presenter notes", "Ghi chú")}</button>
<button id="theme-toggle" type="button">{t("Light mode", "Chế độ sáng")}</button>
<button id="print-button" type="button">{t("Print / PDF", "In / PDF")}</button>
<button id="fullscreen-button" type="button" title="F" hidden>{t("Full screen", "Toàn màn hình")}</button></header>
<main id="deck" class="deck" aria-label="{t("Lecture slides", "Slide bài giảng")}">{"".join(frames)}</main>
<nav class="deck-nav" aria-label="{t("Slide navigation", "Chuyển slide")}"><button id="prev" type="button" aria-label="{t("Previous slide", "Slide trước")}">‹</button>
<span id="counter">1 / {total}</span><button id="next" type="button" aria-label="{t("Next slide", "Slide sau")}">›</button>
<span class="progress" aria-hidden="true"><span id="progress-bar"></span></span>
<span class="keys">{t("Click, scroll or ← → to go on · N notes · F full screen", "Bấm, cuộn hoặc ← → để tiếp · N ghi chú · F toàn màn hình")}</span></nav>
<dialog id="outline" aria-labelledby="outline-title"><form method="dialog"><h2 id="outline-title">{t("Slides", "Danh sách slide")}</h2><ol class="outline">{outline}</ol><button value="close">{t("Close", "Đóng")}</button></form></dialog>
{phone_controls}<p id="deck-status" class="sr-only" role="status" aria-live="polite"></p>
{scripts}</body></html>'''
