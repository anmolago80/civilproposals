# modules/export_i18n.py -- static-scaffolding translations for EXPORTED
# documents (DOCX proposal packs), Part A3 of the EN/ES dual-language brief.
#
# Deliberately separate from modules/i18n.py and modules/translations/en.py|
# es.py:
#   - modules/i18n.py drives the app's own on-screen UI language, chosen per
#     browser session (st.session_state["_lang"]) and persisted to the
#     signed-in user's account. It answers "what language does this person
#     see the Streamlit app in".
#   - export_i18n (this module) drives the STATIC scaffolding text baked
#     into a generated DOCX -- major section headings like "Executive
#     Summary" or "Compliance Matrix" -- chosen per PROJECT
#     (st.session_state["output_language"], set on Project Setup) and baked
#     into that project's exported files. It answers "what language does
#     THIS proposal pack come out in", completely independent of what
#     language the person building it is currently viewing the app in.
#
# The two are never coupled: a Spanish-speaking user could easily be
# preparing an English-language tender pack (or vice versa), so mixing this
# catalog with modules/i18n.py's would silently force one axis to follow the
# other. Kept as one small file (not a translations/ subpackage) because the
# catalog here only needs to cover major document headings, not the whole
# app's UI strings.
from __future__ import annotations

# English is the default/fallback catalog -- every key must exist here.
_EN: dict[str, str] = {
    # -- Shared / used by more than one document --
    "heading_toc": "Table of Contents",
    "heading_executive_summary": "Executive summary",
    "heading_risks_noted_in_brief": "Risks noted in the brief",
    "heading_fee_summary": "Fee summary",
    "heading_fee_by_scope_item": "Fee by scope item",
    "heading_cash_flow": "Cash flow",
    "heading_contractual_arrangements": "Contractual arrangements",
    "heading_local_benefits": "Local benefits",
    "heading_review_checklist": "Review Checklist",

    # -- Large Scope pack (build_docx) --
    "heading_page_allocation_plan": "Page Allocation Plan",
    "heading_fee_estimate_by_discipline": "Indicative Fee Estimate by Discipline",
    "heading_org_chart": "Project organisation chart",
    "heading_key_personnel_profiles": "Key personnel profiles",
    "heading_methodology_summary": "Methodology summary",
    "heading_relevant_experience_compact": "Relevant project experience",
    "heading_relevant_experience": "Our relevant project experience",
    "heading_personnel_experience_matrix": "Key personnel x relevant experience",
    "heading_relationship_management": "Our approach to relationship management",

    # -- Small Scope pack (build_letter_docx) --
    "heading_letter_intro": "1. Introduction",
    "heading_letter_scope_of_work": "2. Scope of Work",
    "heading_letter_methodology": "3. Methodology and Deliverables",
    "heading_letter_team": "4. Project Team",
    "heading_letter_fees": "5. Fees",
    "heading_letter_program": "6. Program",
    "heading_letter_assumptions": "7. Assumptions and Clarifications",
    "heading_letter_terms": "8. Terms of Engagement",
    "heading_risks_mitigation": "Risks and mitigation",
    "heading_discipline_fee_buildup": "Discipline fee build-up",
    "heading_fee_split_by_discipline": "Indicative fee split by discipline",
    "heading_letter_review_checklist": "Review Checklist (delete this page before sending)",

    # -- Tender Summary companion document (build_tender_summary_docx) --
    "heading_tender_summary": "Tender Summary",
    "heading_client_objectives": "Client objectives",
    "heading_mandatory_requirements": "Mandatory requirements",
    "heading_deliverables": "Deliverables",
    "heading_required_forms": "Required forms / returnable schedules",
    "heading_assumptions": "Assumptions",
    "heading_evaluation_weighting_dashboard": "Evaluation weighting dashboard",
    "heading_extraction_warnings": "Extraction warnings -- verify manually",
    "heading_compliance_matrix": "Compliance Matrix",
    "heading_gap_analysis": "Gap Analysis",
    "heading_user_input_required": "User Input Required List",
    "heading_placeholders_in_document": "Placeholders found in the proposal document itself",
}

# Spanish overrides -- only keys that differ from English need an entry here;
# export_t() falls back to _EN for anything missing. Terminology deliberately
# matches modules/translations/es.py (e.g. "propuesta" for proposal,
# "honorarios" for fees, "licitación" for tender) so a project's exported
# pack reads consistently with the rest of the app's Spanish UI.
_ES: dict[str, str] = {
    "heading_toc": "Tabla de contenido",
    "heading_executive_summary": "Resumen ejecutivo",
    "heading_risks_noted_in_brief": "Riesgos identificados en el brief",
    "heading_fee_summary": "Resumen de honorarios",
    "heading_fee_by_scope_item": "Honorarios por partida de alcance",
    "heading_cash_flow": "Flujo de caja",
    "heading_contractual_arrangements": "Arreglos contractuales",
    "heading_local_benefits": "Beneficios locales",
    "heading_review_checklist": "Lista de verificación",

    "heading_page_allocation_plan": "Plan de asignación de páginas",
    "heading_fee_estimate_by_discipline": "Estimación indicativa de honorarios por disciplina",
    "heading_org_chart": "Organigrama del proyecto",
    "heading_key_personnel_profiles": "Perfiles de personal clave",
    "heading_methodology_summary": "Resumen de la metodología",
    "heading_relevant_experience_compact": "Experiencia relevante en proyectos",
    "heading_relevant_experience": "Nuestra experiencia relevante en proyectos",
    "heading_personnel_experience_matrix": "Personal clave x experiencia relevante",
    "heading_relationship_management": "Nuestro enfoque de gestión de relaciones",

    "heading_letter_intro": "1. Introducción",
    "heading_letter_scope_of_work": "2. Alcance del trabajo",
    "heading_letter_methodology": "3. Metodología y entregables",
    "heading_letter_team": "4. Equipo del proyecto",
    "heading_letter_fees": "5. Honorarios",
    "heading_letter_program": "6. Programa",
    "heading_letter_assumptions": "7. Supuestos y aclaraciones",
    "heading_letter_terms": "8. Términos de contratación",
    "heading_risks_mitigation": "Riesgos y mitigación",
    "heading_discipline_fee_buildup": "Desglose de honorarios por disciplina",
    "heading_fee_split_by_discipline": "Reparto indicativo de honorarios por disciplina",
    "heading_letter_review_checklist": "Lista de verificación (elimina esta página antes de enviar)",

    "heading_tender_summary": "Resumen de la licitación",
    "heading_client_objectives": "Objetivos del cliente",
    "heading_mandatory_requirements": "Requisitos obligatorios",
    "heading_deliverables": "Entregables",
    "heading_required_forms": "Formularios / anexos requeridos",
    "heading_assumptions": "Supuestos",
    "heading_evaluation_weighting_dashboard": "Panel de ponderación de evaluación",
    "heading_extraction_warnings": "Advertencias de extracción -- verificar manualmente",
    "heading_compliance_matrix": "Matriz de cumplimiento",
    "heading_gap_analysis": "Análisis de brechas",
    "heading_user_input_required": "Lista de información pendiente del usuario",
    "heading_placeholders_in_document": "Marcadores de posición encontrados en el propio documento de la propuesta",
}

_CATALOGS: dict[str, dict[str, str]] = {
    "en": _EN,
    "es": _ES,
}


# ---------------------------------------------------------------------------
# Canonical placeholder markers (Audit Round 2, Part 4).
#
# Every red bracketed placeholder written by a DETERMINISTIC code path
# (returnable_schedules.py's make_placeholder(), the DOCX/PPTX exporters,
# draft_generator's own prompt instructions) must use exactly one of these
# prefixes -- never a free translation coined on the spot -- so that
# export_docx.collect_placeholders()'s sweep (which matches on these literal
# prefixes, see ALL_PLACEHOLDER_PREFIXES below) never silently misses what a
# Spanish pack actually contains. The Spanish UI already promises
# "[POR COMPLETAR: ...]" (modules/translations/es.py) -- this is what
# actually makes that promise true.
#
# Keyed by a short logical "kind" so callers ask for what they mean
# ("tbc" == to-be-completed, the common case) rather than repeating literal
# bracket text everywhere.
PLACEHOLDER_PREFIXES: dict[str, dict[str, str]] = {
    "en": {
        "tbc": "[TO BE COMPLETED",
        "insert": "[INSERT",
        "confirm": "[CONFIRM",
        "no": "[NO",
        "describe": "[DESCRIBE",
        "enter": "[ENTER",
        "reference": "[REFERENCE",
        "first_pass": "[FIRST-PASS",
        "standard_text": "[STANDARD TEXT",
        "length": "[LENGTH:",
    },
    "es": {
        "tbc": "[POR COMPLETAR",
        "insert": "[INSERTAR",
        "confirm": "[CONFIRMAR",
        "no": "[SIN",
        "describe": "[DESCRIBIR",
        "enter": "[INGRESAR",
        "reference": "[REFERENCIA",
        "first_pass": "[PRIMERA VERSIÓN",
        "standard_text": "[TEXTO ESTÁNDAR",
        "length": "[LONGITUD:",
    },
}

# Flattened across every language -- what collect_placeholders() sweeps a
# generated document for, so a pack that mixes languages (e.g. after a
# mid-project output-language switch) still gets every placeholder listed,
# not just the ones matching whatever language the project is in right now.
ALL_PLACEHOLDER_PREFIXES: tuple[str, ...] = tuple(
    prefix for lang_map in PLACEHOLDER_PREFIXES.values() for prefix in lang_map.values()
)


def placeholder_marker(detail: str, language: str | None = None, kind: str = "tbc") -> str:
    """Builds one canonical red placeholder in the project's output language,
    e.g. placeholder_marker("ABN", "es") -> "[POR COMPLETAR: ABN]". `kind`
    selects which prefix family (default "tbc", the to-be-completed marker
    make_placeholder() uses); falls back to English for an unrecognised
    language or kind, same fallback behaviour as export_t()."""
    lang = (language or "").strip().lower()[:2]
    prefixes = PLACEHOLDER_PREFIXES.get(lang, PLACEHOLDER_PREFIXES["en"])
    prefix = prefixes.get(kind) or PLACEHOLDER_PREFIXES["en"].get(kind, "[TO BE COMPLETED")
    detail = (detail or "").strip()
    return f"{prefix}: {detail}]" if detail else f"{prefix}]"


def export_t(key: str, language: str | None, **fmt) -> str:
    """Looks up `key` in `language`'s export catalog, falling back to English,
    then to a visibly-broken `[[key]]` marker if the key exists in neither --
    mirrors modules/i18n.t()'s fallback behaviour so a missing translation
    fails loud instead of silently, but is otherwise an entirely independent
    system (see module docstring above -- this is a per-PROJECT output
    language, not the per-session UI language modules/i18n.py drives).
    `**fmt` is applied with str.format_map against the resolved string when
    given, e.g. export_t("heading_letter_intro", "es", n=1)."""
    lang = (language or "").strip().lower()[:2]
    catalog = _CATALOGS.get(lang, _EN)
    text = catalog.get(key) or _EN.get(key)
    if text is None:
        return f"[[{key}]]"
    if fmt:
        try:
            return text.format(**fmt)
        except Exception:
            return text
    return text
