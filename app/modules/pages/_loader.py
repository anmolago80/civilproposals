"""
modules/pages/_loader.py

Compiles and caches the ordered page segments app.py executes (see app.py's
docstring for the architecture). Cached per (absolute path, mtime): this
module object persists across Streamlit's script reruns even though the
script's own globals don't, so a rerun costs zero recompiles while an
edited file (new mtime) is picked up immediately in development.
"""

from __future__ import annotations

import os

_CODE_CACHE: dict[tuple[str, float], object] = {}


def load_page_code(path):
    path_str = str(path)
    mtime = os.path.getmtime(path_str)
    key = (path_str, mtime)
    code = _CODE_CACHE.get(key)
    if code is None:
        # Drop stale entries for this path (old mtimes) so the cache can't
        # grow without bound across many dev edits.
        for old_key in [k for k in _CODE_CACHE if k[0] == path_str]:
            del _CODE_CACHE[old_key]
        with open(path_str, encoding="utf-8") as f:
            source = f.read()
        code = compile(source, path_str, "exec")
        _CODE_CACHE[key] = code
    return code
