"""demo-001 private regression tests (mistune: reference links in table-of-contents text).

Public API only, all of which exists at the buggy ref: mistune.create_markdown,
mistune.toc.add_toc_hook / render_toc_ul, and the TableOfContents directive.
Assertions are on TOC text, not on how it is computed, so any correct fix passes.
"""

import mistune
from mistune.directives import FencedDirective, RSTDirective, TableOfContents
from mistune.toc import add_toc_hook, render_toc_ul


def toc_texts(text):
    md = mistune.create_markdown()
    add_toc_hook(md)
    _, state = md.parse(text)
    return [item[2] for item in state.env["toc_items"]]


# AC1: the TOC hook shows link text for reference-style links in headings.

def test_hook_full_reference_link():
    # Different values from the ticket, so special-casing its example fails.
    text = "# Changelog\n## See [release notes][rn] first\n\n[rn]: https://example.org/rn\n"
    assert toc_texts(text) == ["Changelog", "See release notes first"]


def test_hook_collapsed_and_shortcut_reference_links():
    text = "# [Overview][]\n# [Roadmap]\n\n[overview]: /o\n[roadmap]: /r\n"
    assert toc_texts(text) == ["Overview", "Roadmap"]


def test_hook_reference_label_is_case_insensitive():
    text = "# [Upgrading][UPG]\n\n[upg]: /upgrade\n"
    assert toc_texts(text) == ["Upgrading"]


def test_hook_rendered_toc_html():
    md = mistune.create_markdown()
    add_toc_hook(md)
    _, state = md.parse("# Intro\n## [API][api]\n\n[api]: /api\n")
    assert render_toc_ul(state.env["toc_items"]) == (
        '<ul>\n<li><a href="#toc_1">Intro</a>\n<ul>\n'
        '<li><a href="#toc_2">API</a></li>\n</ul>\n</li>\n</ul>\n'
    )


# AC2: the toc directive (both syntaxes) shows link text for reference-style links.

def test_rst_toc_directive_reference_link():
    md = mistune.create_markdown(plugins=[RSTDirective([TableOfContents()])])
    html = md(".. toc::\n\n# [Billing][b]\n# Support\n\n[b]: /billing\n")
    assert '<li><a href="#toc_1">Billing</a></li>' in html
    assert "[Billing]" not in html


def test_fenced_toc_directive_reference_link():
    md = mistune.create_markdown(plugins=[FencedDirective([TableOfContents()])])
    html = md("# Start\n# [Glossary][g]\n\n[g]: /glossary\n\n```{toc}\n```\n")
    assert '<li><a href="#toc_2">Glossary</a></li>' in html
    assert "[Glossary]" not in html


# AC3 (guard): behavior that already works must not change.

def test_guard_other_inline_formatting_is_stripped():
    text = "# **Bold** title\n# [Inline](https://example.com/x)\n# Uses `code`\n"
    assert toc_texts(text) == ["Bold title", "Inline", "Uses code"]


def test_guard_undefined_reference_stays_literal():
    assert toc_texts("# [Nothing][missing]\n") == ["[Nothing][missing]"]


def test_guard_heading_html_and_ids_unchanged():
    md = mistune.create_markdown()
    add_toc_hook(md)
    html, state = md.parse("# [Docs][d]\n## Plain\n\n[d]: /docs\n")
    assert html == '<h1 id="toc_1"><a href="/docs">Docs</a></h1>\n<h2 id="toc_2">Plain</h2>\n'
    assert [(lvl, hid) for lvl, hid, _ in state.env["toc_items"]] == [(1, "toc_1"), (2, "toc_2")]


def test_guard_toc_levels_respected():
    md = mistune.create_markdown()
    add_toc_hook(md, min_level=2, max_level=2)
    _, state = md.parse("# Top\n## [Mid][m]\n### Low\n\n[m]: /m\n")
    assert [item[0] for item in state.env["toc_items"]] == [2]
