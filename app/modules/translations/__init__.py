# modules/translations/ -- per-language string catalogs for modules/i18n.py.
# Each submodule (en.py, es.py) exports a single flat dict, STRINGS,
# key -> translated string. Keep keys identical across every catalog;
# modules/i18n.t() falls back to English (then to a visible [[key]] marker)
# for anything missing in a non-English catalog, so an incomplete Spanish
# catalog degrades safely rather than crashing.
