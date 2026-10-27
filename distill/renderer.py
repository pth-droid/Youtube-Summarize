"""Controlled, offline renderer for the validated Distill contracts."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

from .chapters import NOTE_LEAF_LIMITS
from .figures import figure_ideas, figure_sections, figure_slides
from .models import (FigurePlan, KnowledgeModel, LecturePlan, PresentationPlan, Transcript, figure_unit_ids, validate_bundle,
                     validate_figures, validate_lecture)

ASSET_DIR = Path(__file__).parent / "reader_assets"


def assets(name: str, figures: FigurePlan | None) -> tuple[str, str]:
    """Inline stylesheet and script tags; figure assets only travel with figures."""
    css = (ASSET_DIR / f"{name}.css").read_text(encoding="utf-8")
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


def render_lecture(source: Transcript, knowledge: KnowledgeModel, lecture: LecturePlan, output: Path,
                   figures: FigurePlan | None = None) -> Path:
    """Write one portable slide deck. Slides teach validated knowledge; quotes and times come from the source."""
    validate_lecture(knowledge, lecture)
    if figures:
        validate_figures(knowledge, figures)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
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
        caveats = [caveat for uid in ids for caveat in units[uid].caveats][:3]
        if caveats:
            body += f'<p class="notes-label">{t("Caveats", "Lưu ý")}</p>' + items(caveats, cls="caveats")
        if cited(ids):
            body += f'<p class="notes-label">{t("From the source", "Trích nguồn")}</p>' + quotes(cited(ids)[:3])
        return body

    def chapter_times(chapter):
        timed = [snippets[sid] for section_id in chapter.section_ids for sid in sections[section_id].snippet_ids
                 if snippets[sid].start is not None]
        if not timed:
            return ""
        return f"{clock(min(s.start for s in timed))} – {clock(max(s.end or s.start for s in timed))}"

    slides = []

    def add(kind, title, content, *, eyebrow="", heading=True, notes="", footer="", marks=""):
        slides.append({"kind": kind, "title": title, "eyebrow": eyebrow, "marks": marks, "content": content,
                       "heading": f"<h2>{e(title)}</h2>" if heading else "", "notes": notes, "footer": footer})

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
    meta = [e(source.title)]
    if timed:
        minutes = max(1, round(max(s.end or s.start for s in timed) / 60))
        meta.append(t(f"{minutes} min", f"{minutes} phút"))
    if len(speakers) > 1:
        meta.append(t(f"{len(speakers)} speakers", f"{len(speakers)} người nói"))
    add("title", lecture.title, f'<h1>{e(lecture.title)}</h1><p class="lead">{" · ".join(meta)}</p>',
        eyebrow=t("LECTURE", "BÀI GIẢNG"), heading=False)
    add("objectives", t("After this lecture you can", "Sau bài này, bạn có thể"), items(lecture.objectives, "ol", "objectives"),
        eyebrow=t("LEARNING OBJECTIVES", "MỤC TIÊU BÀI HỌC"))
    add("question", knowledge.main_question, f'<p class="big-question">{e(knowledge.main_question)}</p>',
        eyebrow=t("THE CENTRAL QUESTION", "CÂU HỎI TRUNG TÂM"), heading=False)
    titles = [chapters[part.chapter_id].title if part.chapter_id in chapters else knowledge.main_question for part in lecture.parts]
    if len(lecture.parts) > 1:
        add("agenda", t("Agenda", "Nội dung"), items(titles, "ol", "agenda" + (" two-columns" if len(titles) > 6 else "")),
            eyebrow=t("ROADMAP", "LỘ TRÌNH"))
    for number, (part, title) in enumerate(zip(lecture.parts, titles), 1):
        if len(lecture.parts) > 1:
            span = chapter_times(chapters[part.chapter_id]) if part.chapter_id in chapters else ""
            add("divider", title, f'<p class="part-number">{number:02d}</p><h2 class="part-title">{e(title)}</h2>'
                + (f'<p class="part-time">{span}</p>' if span else ""), eyebrow=t(f"PART {number}", f"PHẦN {number}"), heading=False)
        for slide in part.slides:
            if slide.layout == "compare":
                versus = '<span class="versus" aria-hidden="true">vs</span>'
                content = '<div class="compare">' + versus.join(
                    f'<div class="column"><h3>{e(column.heading)}</h3>{items(column.points)}</div>' for column in slide.columns) + "</div>"
            elif slide.layout == "steps":
                across = len(slide.points) <= 4 and all(len(point) <= 120 for point in slide.points)
                content = items(slide.points, "ol", "steps across" if across else "steps")
            elif slide.layout == "quote":
                evidence = min(cited(slide.unit_ids)[:3], key=lambda ev: len(ev.quote))
                content = (f'<figure class="quote"><blockquote>{e(excerpt(evidence.quote))}</blockquote>'
                           f"<figcaption>{attribution(evidence)}</figcaption></figure>" + items(slide.points, cls="points small"))
            else:
                content = items(slide.points)
            add(slide.layout, slide.title, content, eyebrow=e(title), marks=badges({units[uid].status for uid in slide.unit_ids}),
                notes=notes_for(slide.notes, slide.unit_ids), footer=source_times(slide.unit_ids))
        add_figures(number - 1, e(title))
    add_figures(None, t("FIGURE", "HÌNH"))
    recap = f'<p class="conclusion">{e(knowledge.main_conclusion)}</p>' + items(lecture.takeaways, cls="points takeaways")
    if knowledge.main_conclusion_caveats:
        recap += items(knowledge.main_conclusion_caveats, cls="caveats")
    recap_notes = (f'<p class="notes-label">{t("From the source", "Trích nguồn")}</p>' + quotes(knowledge.main_conclusion_evidence[:3])
                   if knowledge.main_conclusion_evidence else "")
    add("recap", t("What to remember", "Điều cần nhớ"), recap, eyebrow=t("SUMMARY", "TÓM TẮT"),
        marks=badges({knowledge.main_conclusion_status}), notes=recap_notes)
    letters = "ABCD"
    for number, question in enumerate(lecture.questions, 1):
        options = "".join(f'<li><button type="button" class="option" data-correct="{str(index == question.answer).lower()}">'
                          f"<b>{letters[index]}</b> {e(option)}</button></li>" for index, option in enumerate(question.options))
        answer = f'{t("Answer", "Đáp án")}: {letters[question.answer]}. {question.explanation}'
        add("quiz", question.question, f'<ol class="options">{options}</ol><p class="answer">{e(answer)}</p>'
            f'<button type="button" class="reveal">{t("Show answer", "Hiện đáp án")}</button>',
            eyebrow=t(f"CHECK YOUR UNDERSTANDING · {number}/{len(lecture.questions)}", f"KIỂM TRA HIỂU BÀI · {number}/{len(lecture.questions)}"),
            notes=notes_for(answer, question.unit_ids))
    limits = (items(knowledge.limitations[:5], cls="points small") if knowledge.limitations
              else f'<p>{t("No limitations were recorded for this source.", "Không có giới hạn nào được ghi nhận cho nguồn này.")}</p>')
    link = (f'<a href="https://www.youtube.com/watch?v={source.video_id}" target="_blank" rel="noopener noreferrer">{e(source.title)}</a>'
            if source.video_id else e(source.title))
    add("limits", t("Limits and source", "Giới hạn và nguồn"), limits + f'<p class="source-line">{t("Source", "Nguồn")}: {link}</p>'
        f'<p class="source-line">{t("Slides teach a knowledge model checked against original quotations. AI explanations can still be wrong.", "Slide được viết từ mô hình kiến thức đã đối chiếu với trích dẫn gốc. Phần giải thích của AI vẫn có thể sai.")}</p>',
        eyebrow=t("BEFORE YOU REUSE THIS", "TRƯỚC KHI DÙNG LẠI"))

    total = len(slides)
    no_notes = f'<p class="muted">{t("No presenter notes for this slide.", "Slide này không có ghi chú.")}</p>'
    frames = []
    for index, slide in enumerate(slides, 1):
        head = f'<header class="slide-head"><p class="eyebrow">{slide["eyebrow"]}</p>{slide["marks"]}</header>'
        frames.append(f'<article class="slide-frame" id="slide-{index}" role="group" aria-roledescription="slide" aria-label="{index} / {total}: {e(slide["title"])}">'
                      f'<div class="slide-box"><section class="slide kind-{slide["kind"]}">{head}{slide["heading"]}<div class="slide-content">{slide["content"]}</div>'
                      f'<footer class="slide-foot"><span class="sources">{slide["footer"]}</span><span class="count">{index} / {total}</span></footer></section></div>'
                      f'<aside class="notes" aria-label="{t("Presenter notes", "Ghi chú người trình bày")}">{slide["notes"] or no_notes}</aside></article>')
    outline = "".join(f'<li><button type="button" data-go="{index}">{e(slide["title"])}</button></li>' for index, slide in enumerate(slides, 1))
    css, scripts = assets("lecture", figures)
    theme_script = (ASSET_DIR.parent / "web" / "theme.js").read_text(encoding="utf-8")
    page = f'''<!doctype html>
<html lang="{knowledge.language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light"><meta name="referrer" content="no-referrer"><script>{theme_script}</script>
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
<span class="keys">{t("← → move · N notes · F full screen", "← → chuyển slide · N ghi chú · F toàn màn hình")}</span></nav>
<dialog id="outline" aria-labelledby="outline-title"><form method="dialog"><h2 id="outline-title">{t("Slides", "Danh sách slide")}</h2><ol class="outline">{outline}</ol><button value="close">{t("Close", "Đóng")}</button></form></dialog>
<p id="deck-status" class="sr-only" role="status" aria-live="polite"></p>
{scripts}</body></html>'''
    return write_page(output, page)
