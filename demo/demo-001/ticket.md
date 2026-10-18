# Table of contents shows raw `[text][label]` for headings with reference links

**Reporter:** docs tooling team
**Environment:** mistune 3.1.4 (installed from the provided workspace), Python 3.13

## Summary

We build a sidebar table of contents for our docs site with mistune. Most headings
look right, but any heading that contains a *reference-style* link shows up in the
TOC with its raw Markdown source, brackets and label included. The heading itself
renders fine on the page; only the TOC entry is wrong. Headings with ordinary inline
links (`[text](url)`) are fine.

We see the same thing whether we build the TOC ourselves with `add_toc_hook` or let
the `toc` directive render it inside the document.

## Steps to reproduce

```python
import mistune
from mistune.toc import add_toc_hook, render_toc_ul

md = mistune.create_markdown()
add_toc_hook(md)
text = """# Setup
## [Install guide][install]
## [Config](https://example.com/config)

[install]: https://example.com/install
"""
html, state = md.parse(text)
print(render_toc_ul(state.env["toc_items"]))
```

## Expected behavior

The second entry reads `Install guide`, the same as the link text on the page:

```html
<li><a href="#toc_2">Install guide</a></li>
```

## Actual behavior

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

## More examples

All with `[install]: https://example.com/install` defined in the same document:

| Heading source | TOC text today | TOC text expected |
|---|---|---|
| `## [Install guide][install]` | `[Install guide][install]` | `Install guide` |
| `## [Install][]` | `[Install][]` | `Install` |
| `## [Install]` | `[Install]` | `Install` |
| `## [Config](https://example.com/config)` | `Config` | `Config` (already fine) |

## Acceptance criteria

- **AC1:** When the TOC is collected with `add_toc_hook`, a heading that contains a
  reference-style link (full `[text][label]`, collapsed `[text][]`, or shortcut
  `[text]`) whose reference is defined in the document appears in the TOC as its link
  text, without brackets or label. Labels match case-insensitively, as they do in
  the page body.
- **AC2:** The same holds for the table of contents rendered by the `toc` directive,
  in both the RST (`.. toc::`) and fenced (```` ```{toc} ````) syntaxes.
- **AC3:** Nothing else changes: other inline formatting in headings is still reduced
  to plain text in the TOC, a reference whose label is *not* defined still appears
  literally, heading HTML and heading ids are unchanged, and the min/max heading
  level options still apply.
