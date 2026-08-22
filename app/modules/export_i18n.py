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

    # -- Non-heading scaffolding (Audit Round 2, Part 5) --
    # Exporter-written body text/placeholders that a Spanish-output pack
    # was still getting in English. Scoped to what the audit brief actually
    # flagged (specific file:line citations) -- a full sweep of every
    # remaining English string in this module (personnel-profile field
    # labels, business-boilerplate paragraphs, etc.) is a larger follow-up.
    "export_footer_bidder_placeholder": "[BIDDER COMPANY NAME]",
    "export_footer_registered_address": "[REGISTERED ADDRESS]",
    "export_no_introduction": "[NO INTRODUCTION DRAFTED YET -- generate a draft or write one in the Draft Responses step]",
    "export_no_fees_entered_letter": "[NO FEES ENTERED -- price the discipline fee build-up, or generate the discipline fee split, in the Fees & Program step]",
    "export_fee_nothing_selected": "[SELECT WHICH FEE PRESENTATION TO INCLUDE -- Fee Estimate tab]",
    "export_no_assumptions": "[NO ASSUMPTIONS EXTRACTED -- add any that apply]",
    "export_no_terms_of_engagement": "[NO TERMS OF ENGAGEMENT ENTERED -- reference the applicable contract/commercial conditions]",
    "export_no_scope_items": "[NO SCOPE ITEMS EXTRACTED -- run Tender Analysis, or add scope items manually]",
    "export_no_tasks_for_item": "[NO TASKS EXTRACTED FOR {item}]",
    "export_no_methodology": "[NO METHODOLOGY DRAFTED YET -- generate first-pass drafts in the Draft Responses step]",
    "export_eyebrow_why_choose_us": "Why choose us",
    "export_no_team_members": "[NO TEAM MEMBERS ASSIGNED -- assign people (and tick 'Include in proposal') in the Team & Resourcing tab]",
    "export_no_program_entered": "[NO PROGRAM ENTERED -- set the delivery weeks in the Program step]",
    "export_letter_signoff_regards": "Regards",
    "export_letter_sender_placeholder": "[SENDER NAME]",
    "export_letter_checklist_placeholders": "Replace every red bracketed placeholder above with real, verified content.",
    "export_letter_checklist_fees": "Confirm every fee figure is a real, reviewed number -- not a seeded estimate.",
    "export_letter_checklist_team": "Confirm named team members' availability for the stated program.",
    "export_letter_checklist_program": "Confirm the program dates are realistic and reflect any award-date dependency.",
    "export_letter_checklist_terms": "Confirm the Terms of Engagement reference the correct/current contract.",
    "export_letter_checklist_footer": "Fill in the footer's ABN and registered address placeholders on every page.",
    "export_letter_checklist_proofread": "Proofread the document as a whole -- cover page, Executive Summary, and sign-off details.",
    "export_checklist_delete_boxes": "Delete every red 'DELETE BEFORE SUBMISSION' guidance box in this document.",
    "export_checklist_replace_placeholders": "Replace every red bracketed placeholder -- [INSERT ...], [CONFIRM ...] and [TO BE COMPLETED: ...] -- with verified, project-specific content.",
    "export_checklist_page_limits": "Confirm every page limit and formatting rule against the current brief and any addenda.",
    "export_checklist_schedules": "Complete and attach all returnable schedules / forms listed in the Compliance Matrix.",
    "export_checklist_personnel": "Confirm named personnel, CVs, certifications, and insurances are current and accurate.",
    "export_checklist_fee_cap": "Confirm the priced schedule against any stated fee cap.",
    "export_checklist_graphics": "Replace all graphic placeholders with final, approved graphics.",
    "export_checklist_toc": "Update the Table of Contents field before final export.",
    "export_checklist_compliance_check": "Run a final compliance check against every row in the Compliance Matrix.",
    "export_checklist_submission": "Confirm the submission method, format, and deadline one more time before lodging.",
    "export_cover_image_placeholder": "[COVER IMAGE PLACEHOLDER]",
    "export_cover_image_placeholder_detail": "[COVER IMAGE PLACEHOLDER: PROJECT / SITE PHOTO]",
    "export_cover_disclaimer": (
        "FIRST-PASS PREPARATION PACK -- NOT SUBMISSION READY. Generated {date}. Every red "
        "guidance box and bracketed placeholder must be reviewed, verified, and removed "
        "before this document is used for anything beyond internal drafting."
    ),
    "export_cover_fallback_title": "Tender Response Pack",
    "export_pull_quote_eyebrow_differentiator": "What sets us apart",
    "export_no_executive_summary": "[NO EXECUTIVE SUMMARY DRAFTED YET -- generate one in the Draft Responses step]",
    "export_block_untitled": "[UNTITLED]",
    "export_no_content_drafted": "[NO CONTENT DRAFTED]",
    "export_unweighted_note": (
        "[UNWEIGHTED -- carries no evaluation score, but sets the tone for everything that "
        "follows. Confirm every claim above before submission.]"
    ),
    "export_org_chart_firstpass_note": (
        "[FIRST-PASS CHART ABOVE, generated from the Team & Resourcing tab -- replace it with "
        "the finished chart. A companion PowerPoint org chart is exported alongside this "
        "document; finish it there, then paste it over the image above.]"
    ),
    "export_org_chart_insert_note": (
        "[INSERT ORGANISATION CHART HERE -- paste in the finished chart image. A companion "
        "PowerPoint org chart template is exported alongside this document; build the chart "
        "there, then paste it into this space.]"
    ),
    "export_photo_placeholder": "[INSERT PHOTO]",
    "export_photo_placeholder_instruction": "Click here, delete this text, then Insert ▸ Pictures",
    "export_cash_flow_insert": "[INSERT PROJECT CASH FLOW PROFILE, BASED ON THE FEE AND PROGRAM]",
    "export_local_benefits_intro_note": (
        "The brief calls for local-benefit / local-content commitments -- the headings below are "
        "a standard starting structure; every figure and claim must be confirmed for this bid "
        "before submission."
    ),
    "export_local_benefits_heading_resources": "Local resources and location",
    "export_local_benefits_heading_economy": "Contribution to the local economy",
    "export_local_benefits_heading_strategy": "Alignment with local strategy / vision",
    "export_local_benefits_heading_reinvestment": "Profit / community reinvestment",
    "export_local_benefits_confirm_local": "[CONFIRM % OF THE TEAM BASED LOCALLY AND WHICH OFFICE(S) WILL DELIVER THE WORK]",
    "export_local_benefits_describe_economy": (
        "[DESCRIBE HOW THIS BID SUPPORTS LOCAL EMPLOYMENT, LOCAL SUPPLIERS/SUBCONSULTANTS, AND "
        "REINVESTMENT IN {client}'S REGION]"
    ),
    "export_local_benefits_reference_strategy": "[REFERENCE ANY NAMED LOCAL/REGIONAL STRATEGY OR VISION DOCUMENT THE BRIEF CALLS OUT]",
    "export_local_benefits_confirm_reinvestment": "[CONFIRM A REAL, CURRENT FIRM COMMUNITY/REINVESTMENT PROGRAM TO REFERENCE HERE]",
    "export_local_benefits_from_profile": "[FROM YOUR FIRM PROFILE -- confirm it still reads correctly for this bid]",
    "export_user_input_intro": "Everything below still needs a human to supply real information.",
    "export_user_input_none": "(none identified -- verify manually)",

    # -- PPTX builders (org_chart_pptx.py / program_pptx.py / methodology_pptx.py) --
    "pptx_org_chart_title": "Project organisation",
    "pptx_org_band_client": "Client",
    "pptx_org_band_leadership": "Leadership",
    "pptx_org_band_delivery_team": "Delivery team",
    "pptx_org_band_assurance": "Assurance",
    "pptx_org_peer_review": "Peer review — {name}",
    "pptx_org_footnote_with_assurance": (
        "Solid reporting lines run top-down; the assurance band reviews independently of the "
        "delivery team."
    ),
    "pptx_org_footnote_plain": "Solid reporting lines run top-down.",
    "pptx_org_empty_note": (
        "[NO TEAM ASSIGNED -- add the management roles and discipline leads in the Team & "
        "Resourcing tab, then re-download this PowerPoint]"
    ),
    "pptx_program_title": "Delivery program",
    "pptx_insert_project_name": "[Insert project name]",
    "pptx_program_legend_scheduled": "Scheduled activity",
    "pptx_program_legend_milestone": "Milestone / hold point",
    "pptx_program_empty_note": (
        "[NO PROGRAM ENTERED -- build the delivery program in the Fee Estimate tab, then "
        "re-download this PowerPoint]"
    ),
    "pptx_methodology_title": "Our proposed methodology",
    "pptx_wvr_statement": "All design deliverables will be issued with completed Work Verification Records (WVRs)",
    "pptx_wvr_confirm_placeholder": "[CONFIRM WVR / QA STATEMENT FOR THIS FIRM]",
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

    # -- Non-heading scaffolding (Audit Round 2, Part 5) --
    "export_footer_bidder_placeholder": "[NOMBRE DE LA EMPRESA LICITANTE]",
    "export_footer_registered_address": "[DIRECCIÓN REGISTRADA]",
    "export_no_introduction": "[NO SE HA REDACTADO AÚN LA INTRODUCCIÓN -- genere un borrador o escríbala en el paso Redactar Respuestas]",
    "export_no_fees_entered_letter": "[NO SE HAN INGRESADO HONORARIOS -- calcule el desglose de honorarios por disciplina, o genere el reparto por disciplina, en el paso Honorarios y Programa]",
    "export_fee_nothing_selected": "[SELECCIONE QUÉ PRESENTACIÓN DE HONORARIOS INCLUIR -- pestaña Estimación de Honorarios]",
    "export_no_assumptions": "[NO SE EXTRAJERON SUPUESTOS -- agregue los que correspondan]",
    "export_no_terms_of_engagement": "[NO SE HAN INGRESADO TÉRMINOS DE CONTRATACIÓN -- haga referencia al contrato o condiciones comerciales aplicables]",
    "export_no_scope_items": "[NO SE EXTRAJERON PARTIDAS DE ALCANCE -- ejecute el Análisis de la Licitación, o agregue partidas de alcance manualmente]",
    "export_no_tasks_for_item": "[NO SE EXTRAJERON TAREAS PARA {item}]",
    "export_no_methodology": "[NO SE HA REDACTADO AÚN LA METODOLOGÍA -- genere borradores iniciales en el paso Redactar Respuestas]",
    "export_eyebrow_why_choose_us": "Por qué elegirnos",
    "export_no_team_members": "[NO SE HAN ASIGNADO INTEGRANTES DEL EQUIPO -- asigne personas (y marque 'Incluir en la propuesta') en la pestaña Equipo y Recursos]",
    "export_no_program_entered": "[NO SE HA INGRESADO EL PROGRAMA -- defina las semanas de ejecución en el paso Programa]",
    "export_letter_signoff_regards": "Saludos cordiales",
    "export_letter_sender_placeholder": "[NOMBRE DEL REMITENTE]",
    "export_letter_checklist_placeholders": "Reemplace todo marcador de posición en rojo entre corchetes anterior por contenido real y verificado.",
    "export_letter_checklist_fees": "Confirme que cada cifra de honorarios sea un número real y revisado -- no una estimación de referencia.",
    "export_letter_checklist_team": "Confirme la disponibilidad de los integrantes del equipo nombrados para el programa indicado.",
    "export_letter_checklist_program": "Confirme que las fechas del programa sean realistas y reflejen cualquier dependencia de la fecha de adjudicación.",
    "export_letter_checklist_terms": "Confirme que los Términos de Contratación hagan referencia al contrato correcto y vigente.",
    "export_letter_checklist_footer": "Complete los marcadores de posición del ABN y la dirección registrada en el pie de página de cada página.",
    "export_letter_checklist_proofread": "Revise el documento en su totalidad -- portada, resumen ejecutivo y datos de la firma.",
    "export_checklist_delete_boxes": "Elimine todos los cuadros de orientación en rojo 'ELIMINAR ANTES DE PRESENTAR' de este documento.",
    "export_checklist_replace_placeholders": "Reemplace todo marcador de posición en rojo entre corchetes -- [INSERTAR ...], [CONFIRMAR ...] y [POR COMPLETAR: ...] -- por contenido verificado y específico del proyecto.",
    "export_checklist_page_limits": "Confirme cada límite de páginas y regla de formato contra el brief vigente y sus adendas.",
    "export_checklist_schedules": "Complete y adjunte todos los anexos/formularios retornables listados en la Matriz de Cumplimiento.",
    "export_checklist_personnel": "Confirme que el personal nombrado, los CV, las certificaciones y los seguros estén vigentes y sean exactos.",
    "export_checklist_fee_cap": "Confirme el cuadro de precios contra cualquier tope de honorarios establecido.",
    "export_checklist_graphics": "Reemplace todos los marcadores de posición gráficos por gráficos finales y aprobados.",
    "export_checklist_toc": "Actualice el campo de la Tabla de Contenido antes de la exportación final.",
    "export_checklist_compliance_check": "Realice una verificación final de cumplimiento contra cada fila de la Matriz de Cumplimiento.",
    "export_checklist_submission": "Confirme una vez más el método de presentación, el formato y el plazo antes de enviar.",
    "export_cover_image_placeholder": "[MARCADOR DE IMAGEN DE PORTADA]",
    "export_cover_image_placeholder_detail": "[MARCADOR DE IMAGEN DE PORTADA: FOTO DEL PROYECTO / SITIO]",
    "export_cover_disclaimer": (
        "PAQUETE DE PREPARACIÓN DE PRIMERA VERSIÓN -- NO LISTO PARA PRESENTAR. Generado el "
        "{date}. Cada cuadro de orientación en rojo y cada marcador de posición entre corchetes "
        "deben revisarse, verificarse y eliminarse antes de usar este documento para algo más "
        "que un borrador interno."
    ),
    "export_cover_fallback_title": "Paquete de Respuesta a la Licitación",
    "export_pull_quote_eyebrow_differentiator": "Qué nos diferencia",
    "export_no_executive_summary": "[NO SE HA REDACTADO AÚN EL RESUMEN EJECUTIVO -- genere uno en el paso Redactar Respuestas]",
    "export_block_untitled": "[SIN TÍTULO]",
    "export_no_content_drafted": "[SIN CONTENIDO REDACTADO]",
    "export_unweighted_note": (
        "[SIN PONDERACIÓN -- no otorga puntaje de evaluación, pero marca el tono de todo lo que "
        "sigue. Confirme cada afirmación anterior antes de presentar.]"
    ),
    "export_org_chart_firstpass_note": (
        "[ORGANIGRAMA DE PRIMERA VERSIÓN ARRIBA, generado desde la pestaña Equipo y Recursos -- "
        "reemplácelo por el organigrama definitivo. Un organigrama complementario en PowerPoint "
        "se exporta junto con este documento; termínelo allí y luego péguelo sobre la imagen de "
        "arriba.]"
    ),
    "export_org_chart_insert_note": (
        "[INSERTAR ORGANIGRAMA AQUÍ -- pegue la imagen del organigrama terminado. Se exporta una "
        "plantilla de organigrama complementaria en PowerPoint junto con este documento; "
        "constrúyalo allí y luego péguelo en este espacio.]"
    ),
    "export_photo_placeholder": "[INSERTAR FOTO]",
    "export_photo_placeholder_instruction": "Haga clic aquí, elimine este texto y luego Insertar ▸ Imágenes",
    "export_cash_flow_insert": "[INSERTAR PERFIL DE FLUJO DE CAJA DEL PROYECTO, BASADO EN LOS HONORARIOS Y EL PROGRAMA]",
    "export_local_benefits_intro_note": (
        "El brief exige compromisos de beneficio/contenido local -- los encabezados a "
        "continuación son una estructura inicial estándar; cada cifra y afirmación debe "
        "confirmarse para esta oferta antes de presentar."
    ),
    "export_local_benefits_heading_resources": "Recursos y ubicación locales",
    "export_local_benefits_heading_economy": "Contribución a la economía local",
    "export_local_benefits_heading_strategy": "Alineación con la estrategia / visión local",
    "export_local_benefits_heading_reinvestment": "Reinversión de utilidades / en la comunidad",
    "export_local_benefits_confirm_local": "[CONFIRMAR EL % DEL EQUIPO CON BASE LOCAL Y QUÉ OFICINA(S) EJECUTARÁN EL TRABAJO]",
    "export_local_benefits_describe_economy": (
        "[DESCRIBIR CÓMO ESTA OFERTA APOYA EL EMPLEO LOCAL, LOS PROVEEDORES/SUBCONSULTORES "
        "LOCALES Y LA REINVERSIÓN EN LA REGIÓN DE {client}]"
    ),
    "export_local_benefits_reference_strategy": "[REFERENCIAR CUALQUIER ESTRATEGIA O DOCUMENTO DE VISIÓN LOCAL/REGIONAL QUE EL BRIEF MENCIONE]",
    "export_local_benefits_confirm_reinvestment": "[CONFIRMAR UN PROGRAMA REAL Y VIGENTE DE LA EMPRESA DE REINVERSIÓN COMUNITARIA PARA REFERENCIAR AQUÍ]",
    "export_local_benefits_from_profile": "[DESDE SU PERFIL DE EMPRESA -- confirme que siga siendo correcto para esta oferta]",
    "export_user_input_intro": "Todo lo que aparece a continuación aún necesita que una persona proporcione información real.",
    "export_user_input_none": "(no se identificó ninguno -- verifique manualmente)",

    # -- PPTX builders --
    "pptx_org_chart_title": "Organización del proyecto",
    "pptx_org_band_client": "Cliente",
    "pptx_org_band_leadership": "Liderazgo",
    "pptx_org_band_delivery_team": "Equipo de ejecución",
    "pptx_org_band_assurance": "Aseguramiento",
    "pptx_org_peer_review": "Revisión por pares — {name}",
    "pptx_org_footnote_with_assurance": (
        "Las líneas continuas de reporte van de arriba hacia abajo; la banda de aseguramiento "
        "revisa de forma independiente del equipo de ejecución."
    ),
    "pptx_org_footnote_plain": "Las líneas continuas de reporte van de arriba hacia abajo.",
    "pptx_org_empty_note": (
        "[NO SE HA ASIGNADO EQUIPO -- agregue los roles de gestión y los líderes de disciplina "
        "en la pestaña Equipo y Recursos, luego vuelva a descargar este PowerPoint]"
    ),
    "pptx_program_title": "Programa de ejecución",
    "pptx_insert_project_name": "[Insertar nombre del proyecto]",
    "pptx_program_legend_scheduled": "Actividad programada",
    "pptx_program_legend_milestone": "Hito / punto de espera",
    "pptx_program_empty_note": (
        "[NO SE HA INGRESADO EL PROGRAMA -- construya el programa de ejecución en la pestaña "
        "Estimación de Honorarios, luego vuelva a descargar este PowerPoint]"
    ),
    "pptx_methodology_title": "Nuestra metodología propuesta",
    "pptx_wvr_statement": "Todos los entregables de diseño se emitirán con Registros de Verificación de Trabajo (WVR) completos",
    "pptx_wvr_confirm_placeholder": "[CONFIRMAR DECLARACIÓN DE WVR / CALIDAD PARA ESTA EMPRESA]",
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
