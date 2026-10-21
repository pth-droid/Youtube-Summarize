"""Controlled, offline renderer for the validated visual-learning contracts."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

from .chapters import NOTE_LEAF_LIMITS
from .models import KnowledgeModel, PresentationPlan, Transcript, validate_bundle

ASSET_DIR = Path(__file__).parent / "reader_assets"


def render_page(source: Transcript, knowledge: KnowledgeModel, presentation: PresentationPlan, output: Path) -> Path:
    """Write one portable HTML document; source text never becomes executable code."""
    validate_bundle(source, knowledge, presentation)
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
    css = (ASSET_DIR / "reader.css").read_text(encoding="utf-8")
    javascript = (ASSET_DIR / "reader.js").read_text(encoding="utf-8")
    theme_script = (ASSET_DIR.parent / "web" / "theme.js").read_text(encoding="utf-8")
    page = f'''<!doctype html>
<html lang="{knowledge.language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light"><meta name="referrer" content="no-referrer"><script>{theme_script}</script>
<title>{escape(source.title)} · Visual Learning</title><style>{css}</style></head>
<body><a class="skip-link" href="#overview">{'Đến nội dung' if vi else 'Skip to content'}</a>
<header class="reader-header"><a class="wordmark" href="#overview"><span aria-hidden="true">◈</span> Visual Learning</a>
<span class="offline-label">{'Trang đã lưu · đọc ngoại tuyến' if vi else 'Saved page · offline reading'}</span>
<button id="theme-toggle" type="button">{'Chế độ sáng' if vi else 'Light mode'}</button>
<button id="print-button" type="button">{'In / PDF' if vi else 'Print / PDF'}</button></header>
<main id="reader"><section id="overview" class="orientation"><p class="eyebrow">{'BỨC TRANH TOÀN CẢNH' if vi else 'THE BIG PICTURE'}</p>
<h1>{escape(source.title)}</h1><p class="main-question">{escape(knowledge.main_question)}</p><p class="conclusion">{escape(knowledge.main_conclusion)}</p>
<div id="source-meta" class="source-meta"></div><div id="global-limitations"></div></section>
<nav id="view-nav" class="view-nav" aria-label="{'Các góc nhìn' if vi else 'Learning views'}"></nav>
<div class="learning-layout"><div id="visuals"></div>
<aside id="detail-panel" class="detail-panel" aria-label="{'Chi tiết ý tưởng' if vi else 'Idea detail'}"><div id="detail-content"></div></aside></div>
<details id="source-browser" class="source-browser"><summary class="transcript-heading">{'Bản chép lời gốc' if vi else 'Original transcript'}</summary><div class="section-heading"><p>{'Giữ nguyên ngôn ngữ và mốc thời gian của nguồn.' if vi else 'Original language and source times are preserved.'}</p></div>
<label class="search-label" for="source-search">{'Tìm trong bản chép lời' if vi else 'Search transcript'}</label><input id="source-search" type="search" autocomplete="off">
<p id="source-result-count" class="subtle" aria-live="polite"></p><div id="transcript-list"></div><button id="load-source" type="button"></button></details>
<noscript><section><h2>{'Các ý tưởng và bằng chứng' if vi else 'Ideas and evidence'}</h2>{fallback}<details><summary>{'Toàn bộ nguồn' if vi else 'Complete source'}</summary>{source_fallback}</details></section></noscript>
</main><p id="reader-status" class="sr-only" role="status" aria-live="polite"></p>
<footer>{'Một mô hình để khám phá nguồn. Liên kết video cần kết nối Internet.' if vi else 'A mental model for exploring the source. Video links need an internet connection.'}</footer>
<script type="application/json" id="learning-data">{encoded}</script><script>{javascript}</script></body></html>'''
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(page, encoding="utf-8")
    os.replace(temporary, output)
    return output
