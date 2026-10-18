# demo-001 solution notes

## Upstream

- Issue: https://github.com/lepture/mistune/issues/426 ("Reference links not rendered in
  table of contents links")
- Fix: https://github.com/lepture/mistune/commit/a0a0148af57970c62f6fb437674f88753522ef51
  ("fix: render ref links in TOC", lemon24, 2025-12-21)
- Buggy ref: `c85632528f6f3d9d974bfae300716ac997a8d2c1` (parent of the fix, `v3.1.4-7`)

## Root cause

Reference definitions (`[install]: https://...`) are collected by the **block parser**
while it scans the document, and stored in the parse state's environment
(`state.env["ref_links"]`). The **inline parser** resolves `[text][label]`, `[text][]` and
`[text]` by looking up the label in that same `env`. If the label isn't found, the
brackets are left as literal text. That is correct CommonMark behavior for an
*undefined* reference.

The TOC code doesn't reuse the heading's already-rendered HTML. It re-parses each
heading's raw text to produce plain TOC text:

```python
# src/mistune/toc.py, normalize_toc_item()
tokens = md.inline(text, {})          # <-- fresh, empty env
```

Because it passes a brand-new empty `env`, no reference definitions are visible, so every
reference-style link in a heading looks undefined and stays as `[text][label]`. Inline
links (`[text](url)`) carry their URL with them, which is why they work.

There are two call sites, which is why the ticket has both AC1 and AC2:

1. `src/mistune/toc.py` `add_toc_hook()` → `toc_hook()` (the hook API, AC1)
2. `src/mistune/directives/toc.py` `TableOfContents.toc_hook()` (the `.. toc::` and
   ```` ```{toc} ```` directives, AC2)

The trace a candidate follows: TOC text → `normalize_toc_item` → `md.inline(text, {})`
→ inline parser link handling (`src/mistune/inline_parser.py`, ref lookup in `env`)
→ where `ref_links` gets populated (`src/mistune/block_parser.py`, ref definitions)
→ realize the TOC passes an empty env.

## Upstream fix (4 changed source lines, 2 files)

`normalize_toc_item` gains `parent=None` and uses `parent.env if parent else {}`. Both
call sites pass `parent=state`. Any fix that makes the TOC see the document's reference
definitions passes. Examples: passing `state.env`, or deriving TOC text from the
already-rendered heading HTML.

## Repro outputs (ticket script)

At the buggy ref:

```html
<ul>
<li><a href="#toc_1">Setup</a>
<ul>
<li><a href="#toc_2">[Install guide][install]</a></li>
<li><a href="#toc_3">Config</a></li>
</ul>
</li>
</ul>
```

At the fixed ref:

```html
<ul>
<li><a href="#toc_1">Setup</a>
<ul>
<li><a href="#toc_2">Install guide</a></li>
<li><a href="#toc_3">Config</a></li>
</ul>
</li>
</ul>
```

Example table, buggy → `['[Install guide][install]', '[Install][]', '[Install]', 'Config']`;
fixed → `['Install guide', 'Install', 'Install', 'Config']`.

## Private test design

- **AC1 (hook):** full, collapsed and shortcut references, a case-insensitive label, and
  the exact `render_toc_ul` HTML. Every example uses different values from the ticket,
  so hard-coding "Install guide" fails.
- **AC2 (directive):** RST and fenced syntax. A fix that patches only the hook call
  site fails AC2.
- **AC3 (guard, passes at both refs):** bold, inline-link and code-span headings still
  stripped; an *undefined* reference stays literal (so "just strip all brackets" fails);
  heading HTML and ids unchanged; `min_level`/`max_level` still respected.
