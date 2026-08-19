"""
test_blog_sanitise.py -- checks that rendered post HTML can't execute script.

Post bodies are markdown, and markdown passes raw HTML through, so anything
an author types lands on a public page as-is. blog._sanitise_html() closes
that off; this test pins the two halves of the contract:

  1. the three script-execution routes (a <script> element, an on* handler,
     a javascript: URL) are neutralised, on BOTH render paths -- the
     `markdown` package and the built-in fallback used when it isn't
     installed;
  2. ordinary markdown output is returned completely untouched, which is
     the property that lets the sanitiser sit in the publish path without
     anyone having to re-check how existing posts render.

Run from this directory:

    python test_blog_sanitise.py
"""

from __future__ import annotations

import os
import re
import sys

HOSTILE_MD = """\
Some ordinary text.

<script>alert(1)</script>

<img src="hero.png" onerror="alert(1)" alt="a picture">

[click me](javascript:alert(1))
"""

ORDINARY_MD = """\
# A heading

A paragraph with **bold**, *italic*, `code` and a
[real link](https://civilproposals.com/security.html).

## A subheading

- first item
- second item

1. numbered
2. list

> A quote.

![A diagram](/blog/media/diagram.png)

```python
print("<script>not really a script</script>")
```

| Column | Column |
|---|---|
| a | b |
"""


def _check_hostile(label: str, out: str, failures: list[str]) -> None:
    """The three routes, checked on the rendered output.

    Checked as live markup, not as substrings: the fallback renderer
    escapes raw HTML to text, so a post can legitimately end up *showing*
    the characters `onerror=` while containing no attribute at all. What
    must not survive is a tag a browser would act on."""
    lowered = out.lower()
    if re.search(r"<\s*script\b", lowered):
        failures.append(f"[{label}] a <script> element survived rendering")
    if re.search(r"<[^>]*\son\w+\s*=", lowered):
        failures.append(f"[{label}] an on* event-handler attribute survived rendering")
    if re.search(r"""<[^>]*\s(?:href|src)\s*=\s*["']?\s*javascript:""", lowered):
        failures.append(f"[{label}] a javascript: URL survived rendering")
    # The surrounding post must still be there -- a sanitiser that ate the
    # whole body would pass the three checks above and be useless.
    if "ordinary text" not in lowered:
        failures.append(f"[{label}] the post's real content was destroyed")


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from modules import blog

    failures: list[str] = []

    # Path 1: the markdown package (what production uses).
    _check_hostile("markdown", blog._md_to_html(HOSTILE_MD), failures)

    # Path 2: the built-in fallback, exercised directly so the test still
    # covers it on a machine where the markdown package IS installed.
    _check_hostile("fallback", blog._sanitise_html(blog._fallback_md(HOSTILE_MD)), failures)

    # A data:image/ src is a legitimate inline image and must survive, or
    # the sanitiser is quietly changing what authors can write.
    kept = blog._sanitise_html('<img src="data:image/png;base64,iVBORw0KGgo=" alt="dot">')
    if "data:image/png" not in kept:
        failures.append("[allowlist] a legitimate data:image/ src was stripped")

    # ...while data:text/html in the same position is script in disguise.
    dropped = blog._sanitise_html('<img src="data:text/html;base64,PHNjcmlwdD4=" alt="x">')
    if "data:text/html" in dropped:
        failures.append("[allowlist] a data:text/html src was kept")

    # The other half of the contract: ordinary markdown output is passed
    # through byte for byte. Compared against the UNSANITISED render of the
    # same source, so this fails if the sanitiser ever starts rewriting
    # legitimate markup.
    import markdown as _markdown

    raw = _markdown.markdown(
        ORDINARY_MD,
        extensions=["extra", "sane_lists", "smarty", "toc"],
        output_format="html5",
    )
    if blog._sanitise_html(raw) != raw:
        failures.append("[ordinary] sanitising altered ordinary markdown output")
    if blog._md_to_html(ORDINARY_MD) != raw:
        failures.append("[ordinary] _md_to_html no longer matches a plain markdown render")

    fallback_raw = blog._fallback_md(ORDINARY_MD)
    if blog._sanitise_html(fallback_raw) != fallback_raw:
        failures.append("[ordinary] sanitising altered the fallback renderer's output")

    if failures:
        print("BLOG SANITISE TEST FAILED:")
        for failure in failures:
            print("  -", failure)
        return 1
    print("BLOG SANITISE TEST PASSED: script, on* handlers and javascript: URLs "
          "are stripped on both render paths; ordinary markdown is unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
