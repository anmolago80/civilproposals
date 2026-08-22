# Spanish (Español) catalog. See translations/__init__.py -- any key missing
# here falls back to English rather than crashing, so this can be extended
# incrementally without ever breaking the Spanish UI.
from __future__ import annotations

STRINGS: dict[str, str] = {
    "language_picker_label": "Idioma",

    "nav_project_setup": "Configuración del proyecto",
    "nav_upload_docs": "Subir documentos",
    "nav_tender_analysis": "Análisis de la licitación",
    "nav_structure": "Estructura",
    "nav_page_allocation": "Asignación de páginas",
    "nav_draft_responses": "Redactar respuestas",
    "nav_graphics_design": "Gráficos y diseño",
    "nav_team_resourcing": "Equipo y recursos",
    "nav_fee_estimate": "Estimación de honorarios",
    "nav_export_pack": "Exportar paquete",

    "tab_upload_documents": "Subir documentos",
    "tab_proposal_structure": "Estructura de la propuesta",

    "sidebar_signed_in_as": "Sesión iniciada como **{email}**",
    "sidebar_unlimited_access": "Acceso ilimitado",
    "sidebar_past_due": "Pago pendiente -- actualiza tu tarjeta para mantener el acceso.",
    "sidebar_sub_active_remaining": "Plan: Suscripción activa -- quedan {remaining} de {limit} propuesta(s) este ciclo",
    "sidebar_sub_used_has_credits": "Propuestas mensuales usadas -- {credits} crédito(s) de pago por uso disponibles",
    "sidebar_sub_used_no_credits": "Propuestas mensuales usadas -- compra una propuesta para continuar, o espera la renovación.",
    "sidebar_limit_reached": "Se alcanzó el número máximo de propuestas gratuitas -- mejora tu plan para continuar.",
    "sidebar_trial_used_has_credits": "Pago por uso: {credits} crédito(s) de propuesta disponibles",
    "sidebar_trial_remaining": "Prueba gratuita: quedan {remaining} de {limit} propuesta(s)",
    "sidebar_ai_disclaimer": "Contenido generado por IA -- revísalo antes de enviarlo. [Términos de servicio completos](https://civilproposals.com/terms-of-service.html)",

    "btn_my_proposals": "📁 Mis propuestas",
    "btn_proposal_library": "📁 Biblioteca de propuestas",
    "btn_project_reference_library": "📁 Biblioteca de referencia de proyectos",
    "btn_manage": "Gestionar",
    "btn_upgrade": "Mejorar plan",
    "btn_log_out": "Cerrar sesión",

    "auth_headline": "Creado por ingenieros civiles, para ingenieros civiles",
    "auth_subhead": (
        "Conocemos los desafíos que enfrentas cada día porque nosotros también los enfrentamos. Ya sea un "
        "proyecto pequeño con un alcance simple, un brief perdido en un correo, un cliente que no está "
        "seguro de lo que quiere, o una gran licitación que toma días leer y semanas preparar, "
        "CivilProposals está diseñado para ayudar. Creado por ingenieros civiles, para ingenieros civiles, "
        "la plataforma te ayuda a crear propuestas profesionales y bien estructuradas más rápido, para que "
        "puedas concentrarte en entender las necesidades del cliente y desarrollar soluciones ganadoras."
    ),
    "auth_tab_login": "Iniciar sesión",
    "auth_tab_signup": "Crear cuenta",
    "auth_email": "Correo electrónico",
    "auth_password": "Contraseña",
    "auth_login_submit": "Iniciar sesión",
    "auth_forgot_password": "¿Olvidaste tu contraseña?",
    "auth_forgot_caption": "Ingresa el correo de tu cuenta y te enviaremos un enlace para restablecer tu contraseña.",
    "auth_forgot_submit": "Enviar enlace de restablecimiento",
    "auth_reset_not_configured": "El restablecimiento de contraseña aún no está configurado -- contacta a soporte directamente por ahora.",
    "auth_reset_sent": "Si existe una cuenta con ese correo, hemos enviado un enlace -- revisa tu bandeja de entrada (y spam). Es válido por 1 hora.",
    "auth_error_bad_login": "Correo electrónico o contraseña incorrectos.",
    "auth_signup_name": "Tu nombre",
    "auth_signup_firm": "Nombre de la empresa",
    "auth_signup_email": "Correo del trabajo",
    "auth_signup_password_help": "Al menos 8 caracteres.",
    "auth_signup_confirm_password": "Confirmar contraseña",
    "auth_signup_trial_caption": "Prueba gratuita: {limit} propuesta completa, sin tarjeta requerida. Luego paga por propuesta, o suscríbete mensualmente -- consulta los precios en la página principal.",
    "auth_signup_terms_expander": "Términos que estás aceptando",
    "auth_signup_terms_checkbox": "He leído y acepto los términos anteriores y los Términos de servicio.",
    "auth_signup_submit": "Crear cuenta",
    "auth_error_passwords_no_match": "Las contraseñas no coinciden -- vuelve a ingresarlas.",
    "auth_error_must_accept_terms": "Acepta los términos anteriores para crear una cuenta.",

    "terms_gate_title": "### Antes de continuar",
    "terms_gate_intro": "Por favor revisa y acepta los siguientes términos -- solo toma un segundo y no se te volverá a pedir.",
    "terms_gate_checkbox": "He leído y acepto estos términos y los Términos de servicio.",
    "terms_gate_accept": "Aceptar y continuar",
    "terms_gate_logout": "Cerrar sesión en su lugar",

    "pw_reset_success": "Contraseña actualizada -- ya puedes iniciar sesión con tu nueva contraseña.",
    "pw_reset_continue": "Continuar a iniciar sesión",

    "free_tier_artifact_used": (
        "Ya has usado tu descarga gratuita de este documento. Compra una propuesta para "
        "descargarlo de nuevo, o para desbloquear todo lo demás en este proyecto."
    ),
    "free_tier_generate_used": (
        "Ya has usado tu única pasada de generación gratuita en este proyecto. Compra una "
        "propuesta para generar de nuevo con tus últimos cambios."
    ),
    "free_tier_paid_only_caption": "Incluido con una propuesta paga -- no forma parte de la prueba gratuita.",
    "free_tier_whats_included_title": "Qué incluye tu prueba gratuita",
    "free_tier_whats_included_body": (
        "Una ejecución gratuita del Análisis de la licitación, y una descarga gratuita de cada uno de: "
        "la Propuesta (DOCX), el Resumen de la licitación (DOCX) y el Organigrama (PPTX) -- para un "
        "proyecto. Todo lo demás, y cualquier nueva descarga o regeneración, requiere una propuesta paga."
    ),

    "passes_remaining_caption": "Quedan {remaining} de {total} pasada(s) en este proyecto",
    "passes_exhausted": "No quedan pasadas en este proyecto. Compra un paquete adicional (+5 pasadas), o inicia un nuevo proyecto con tu suscripción.",
    "passes_topup_button": "Comprar 5 pasadas más ($50)",
    "passes_topup_success": "Se agregaron 5 pasadas a este proyecto.",
    "subscription_bid_limit_caption": "{limit} proyectos de propuesta incluidos por mes",
    "export_download_mark_failed_warning": (
        "No pudimos registrar esa descarga en este momento -- inténtalo de nuevo. Si sigue "
        "ocurriendo, escribe a hello@civilproposals.com."
    ),

    "bid_includes_popover_title": "Qué incluye una propuesta",
    "bid_includes_popover_body": (
        "Una sola propuesta de $50 cubre **un proyecto** (identificado por el nombre del proyecto, el "
        "nombre de la licitación, el nombre del cliente y el brief subido, en conjunto) con **5 pasadas "
        "de generación** y **descargas ilimitadas** de tus documentos actuales. Se consume una pasada al "
        "ejecutar el Análisis de la licitación, o al regenerar después de cambiar una entrada -- volver a "
        "descargar los mismos documentos sin cambios nunca consume una pasada. Renombrar un proyecto, o "
        "cambiar el brief, crea una nueva identidad de facturación -- te pediremos que lo confirmes, y tu "
        "análisis pagado, tus pasadas y tus descargas seguirán automáticamente al nuevo nombre."
    ),
    "rename_confirm_title": "¿Renombrar este proyecto?",
    "rename_confirm_body": (
        "Renombrar cambia la identidad de facturación de este proyecto. Tu análisis pagado, tus pasadas "
        "y tu historial de descargas seguirán automáticamente al nuevo nombre -- no se pierde nada. "
        "¿Continuar?"
    ),
    "rename_confirm_yes": "Sí, renombrar",
    "rename_confirm_cancel": "Cancelar",

    # Part A2 -- Structure / Page Allocation / Draft Responses tabs
    # (40_structure_allocation.py, 50_drafting.py)

    # --- Tab 4: Proposal Structure ---
    "structure_subheader": "Estructura de la propuesta",
    "structure_caption": (
        "Si el brief define sus propios criterios de selección, la estructura los refleja "
        "exactamente. De lo contrario, recurre al esquema estándar, ordenado por ponderación."
    ),
    "structure_run_analysis_first": "Ejecuta primero el Análisis de la licitación.",
    "structure_generate_button": "Generar estructura de la propuesta",
    "structure_generated_success": "Se generaron {n} sección(es).",
    "structure_format_stale_warning": (
        "Cambiaste el formato de la propuesta (Configuración del proyecto) después de generar "
        "estas secciones, por lo que la lista de abajo sigue construida para el formato "
        "*anterior* y no coincidirá con lo que espera la redacción/exportación (por ejemplo, "
        "sin la sección 'Comprensión del proyecto' en un paquete de alcance reducido). Haz clic "
        "en **Generar estructura de la propuesta** de nuevo arriba para actualizarla."
    ),
    "structure_col_number": "N.º",
    "structure_col_title": "Título",
    "structure_col_fixed": "Fija",
    "structure_fixed_yes": "Sí",
    "structure_fixed_no": "No",
    "structure_col_weighting": "Ponderación",
    "structure_col_weighting_source": "Origen de la ponderación",
    "structure_col_pages": "Páginas",
    "structure_col_page_source": "Origen de páginas",
    "structure_override_weighting_expander": "Anular manualmente la ponderación de una sección",
    "structure_section_label": "Sección",
    "structure_new_weighting_label": "Nueva ponderación (%)",
    "structure_apply_weighting_button": "Aplicar anulación de ponderación",
    "structure_weighting_applied_success": "La ponderación de '{target}' se fijó en {weight:.0f}%. Estructura recalculada.",
    "structure_compliance_heading": "#### Matriz de cumplimiento",
    "structure_generate_compliance_button": "Generar matriz de cumplimiento",
    "structure_compliance_col_id": "ID",
    "structure_compliance_col_description": "Descripción",
    "structure_compliance_col_type": "Tipo",
    "structure_compliance_col_mapped_section": "Sección asignada",
    "structure_compliance_col_priority": "Prioridad",
    "structure_compliance_col_status": "Estado",
    "structure_gap_heading": "#### Análisis de brechas",
    "structure_generate_gap_button": "Generar análisis de brechas",
    "structure_gap_col_risk": "Riesgo",
    "structure_gap_col_issue": "Problema",
    "structure_gap_col_impact": "Impacto",
    "structure_gap_col_recommended_action": "Acción recomendada",
    "structure_gap_col_section": "Sección",

    # --- Tab 5: Page Allocation ---
    "pageaalloc_subheader": "Asignación de páginas",
    "pageaalloc_caption": (
        "Orden de prioridad: límite exacto de la sección en el brief > proporción ponderada de "
        "un total indicado > plantilla predeterminada."
    ),
    "pageaalloc_small_scope_info": (
        "El paquete de alcance reducido no tiene un límite de páginas indicado que reflejar, "
        "así que este paso es solo indicativo -- la extensión real de las secciones proviene "
        "de la tabla de secciones (pestaña 4), no de la asignación de páginas."
    ),
    "pageaalloc_generate_structure_first": "Genera primero la estructura de la propuesta.",
    "pageaalloc_col_section": "Sección",
    "pageaalloc_col_weighting": "Ponderación",
    "pageaalloc_col_source": "Origen",
    "pageaalloc_col_allocated_pages": "Páginas asignadas",
    "pageaalloc_col_reason": "Motivo",
    "pageaalloc_override_pages_expander": "Anular manualmente el número de páginas de una sección",
    "pageaalloc_section_label": "Sección",
    "pageaalloc_new_pages_label": "Nuevo número de páginas",
    "pageaalloc_apply_pages_button": "Aplicar anulación de páginas",
    "pageaalloc_pages_applied_success": "'{target}' se fijó en {pages} página(s). Estructura actualizada.",

    # --- Tab 6: Draft Responses ---
    "drafting_subheader": "Redactar respuestas",
    "drafting_letter_caption": (
        "El paquete de alcance reducido tiene dos secciones que son verdaderamente de texto "
        "libre -- Introducción y Metodología y entregables, ambas redactadas más abajo. El "
        "Alcance del trabajo proviene directamente del brief, Equipo del proyecto/Honorarios/"
        "Programa tienen sus propios pasos dedicados (Equipo y recursos / Estimación de "
        "honorarios), y Términos de contratación, más abajo, siempre es tu propio texto, nunca "
        "redactado por IA."
    ),
    "drafting_standard_caption": (
        "Contenido de primera versión por sección, con notas de orientación en rojo y una "
        "lista de lo que aún necesita aporte real del usuario."
    ),
    "drafting_generate_structure_and_hint": "Genera la estructura de la propuesta y {hint}.",
    "drafting_format_stale_warning": (
        "El formato de la propuesta (Configuración del proyecto) se cambió después de generar "
        "las secciones actuales. Ve a Estructura y haz clic en **Generar estructura de la "
        "propuesta** de nuevo antes de redactar, o esto no redactará nada (sin aviso) para las "
        "secciones que solo existen en este formato."
    ),
    "drafting_generate_button": "Generar primeras versiones",
    "drafting_regen_will_use_pass_caption": "Los datos cambiaron desde tu última generación -- regenerar usará una pasada.",
    "drafting_regen_no_pass_caption": "Los datos no han cambiado desde tu última generación -- esto no usará una pasada.",
    "drafting_nothing_to_draft_error": (
        "Nada que redactar -- las secciones actuales no coinciden con ninguno de los títulos "
        "de sección redactados por IA de este formato. Esto suele significar que el formato de "
        "la propuesta (Configuración del proyecto) se cambió después de generar la Estructura "
        "de la propuesta. Ve a Estructura y haz clic en **Generar estructura de la propuesta** "
        "de nuevo, luego vuelve a intentarlo."
    ),
    "drafting_progress_text": "Redactando...",
    "drafting_done_text": "Listo.",
    "drafting_progress_detail": "Se redactó '{title}' ({done}/{total})...",
    "drafting_queued_text": "En cola para redactar...",
    "drafting_thin_warning": (
        "**La redacción terminó, pero algunas secciones volvieron vacías o muy breves:** "
        "{sections}. Vuelve a ejecutar la redacción para esas, o escríbelas tú mismo -- se "
        "exportarán como marcadores rojos hasta que lo hagas."
    ),
    "drafting_generation_complete_success": "Generación de borradores completa para {n} sección(es).",
    "drafting_generation_failed_error": "Falló la generación de borradores",
    "generated_language_stale_notice": (
        "Estos borradores se generaron en {from_lang} -- vuelve a generarlos para obtenerlos en {to_lang}."
    ),

    "drafting_risk_register_heading": "#### Registro de riesgos",
    "drafting_risk_register_caption": (
        "Una tabla de primera versión de riesgo / impacto / mitigación, estructurada a partir "
        "de los riesgos que plantea el propio brief y las brechas que encontró el análisis. "
        "**Una mitigación es un compromiso al que tu firma quedará sujeta**, así que la IA solo "
        "indica una que el brief ya describe -- todo lo demás vuelve como **TBC** para que tú "
        "decidas. Edita lo que quieras abajo."
    ),
    "drafting_risk_register_button": "Redactar registro de riesgos",
    "drafting_risk_run_analysis_caption": (
        "Ejecuta primero el Análisis de la licitación -- el registro se construye a partir de "
        "los propios riesgos del brief."
    ),
    "drafting_risk_register_failed_error": "Falló la redacción del registro de riesgos",
    "drafting_risk_none_warning": (
        "No se encontraron riesgos -- puede que el brief no plantee ninguno. No se ha cambiado "
        "nada; agrega filas manualmente abajo si de todos modos quieres un registro."
    ),
    "drafting_risk_structured_success": "Se estructuraron {n} riesgo(s) -- revisa abajo.",
    "drafting_risk_confirm_rerisk_warning": (
        "Ya tienes un registro de riesgos, y parte de él puede ser tus propias ediciones. "
        "Redactar de nuevo reemplaza cada fila. Haz clic en **Redactar registro de riesgos** "
        "una vez más para continuar."
    ),
    "drafting_cancel_button": "Cancelar",
    "drafting_risk_col_risk": "Riesgo",
    "drafting_risk_col_impact": "Impacto",
    "drafting_risk_col_mitigation": "Mitigación",
    "drafting_risk_col_source": "Origen",
    "drafting_risk_tbc_caption": (
        "Las filas que quedan como **TBC** se exportan en rojo, para que nadie envíe una "
        "mitigación sin completar por accidente."
    ),

    "drafting_design_stages_heading": "#### Etapas de diseño",
    "drafting_design_stages_caption": (
        "Las etapas de ejecución detrás de la tabla de metodología exportada. La IA asigna los "
        "propios elementos de alcance y entregables de tu brief a etapas y los reformula -- "
        "nunca agrega una tarea, actividad, entregable o fecha que no esté en el brief, y "
        "escribe **TBC** donde el brief no respalde una celda. Edita lo que quieras abajo; lo "
        "que haya aquí al exportar es exactamente lo que va en la tabla."
    ),
    "drafting_stages_button": "Redactar etapas de metodología",
    "drafting_stages_run_analysis_caption": (
        "Ejecuta primero el Análisis de la licitación -- las etapas se construyen a partir del "
        "propio alcance y entregables del brief."
    ),
    "drafting_stages_failed_error": "Falló la redacción de las etapas de metodología",
    "drafting_stages_none_warning": (
        "La IA no devolvió etapas -- no se ha cambiado nada. Puedes completar la cuadrícula a "
        "mano con **Comenzar una cuadrícula en blanco** abajo."
    ),
    "drafting_stages_drafted_success": "Se redactaron {n} etapa(s) -- revisa y edita abajo.",
    "drafting_stages_confirm_restage_warning": (
        "Ya tienes una cuadrícula de etapas abajo, y parte de ella puede ser tus propias "
        "ediciones. Redactar de nuevo reemplaza cada etapa. Haz clic en **Redactar etapas de "
        "metodología** una vez más para continuar, o edita la cuadrícula directamente."
    ),
    "drafting_blank_grid_button": "Comenzar una cuadrícula en blanco",
    "drafting_no_stages_caption": (
        "Aún no hay etapas. Sin ellas, la tabla de metodología exportada recurre a su diseño "
        "genérico de cuatro etapas con columnas de marcador de posición."
    ),
    "drafting_stage_title": "Etapa {n}: {name}",
    "drafting_stage_untitled": "Sin título",
    "drafting_stage_name_label": "Nombre de la etapa",
    "drafting_stage_first_week_label": "Primera semana",
    "drafting_stage_last_week_label": "Última semana",
    "drafting_week_numbers_caption": (
        "Los números de semana provienen del programa de ejecución en el paso Honorarios y "
        "programa. Define ahí una fecha de inicio prevista y estos se convertirán en fechas "
        "reales en la tabla exportada."
    ),
    "drafting_key_tasks_label": "Tareas clave (una por línea)",
    "drafting_engagement_activities_label": "Actividades de participación (una por línea)",
    "drafting_outcome_label": "Resultado",
    "drafting_deliverables_label": "Entregables (uno por línea)",
    "drafting_cell_tbc_caption": (
        "Deja una celda como **TBC** cuando el brief realmente no lo indique -- se exporta en "
        "rojo para que nadie la envíe por accidente."
    ),
    "drafting_remove_stage_button": "Eliminar esta etapa",
    "drafting_add_stage_button": "Agregar una etapa",
    "drafting_wvr_checkbox_label": (
        "Confirmar que esta firma emite Registros de Verificación de Obra (WVR) con los "
        "entregables de diseño"
    ),
    "drafting_wvr_checkbox_help": (
        "La tabla de metodología solía declarar esto como un hecho en cada exportación sin que "
        "se le preguntara a nadie. Déjala sin marcar y se exportará en rojo como "
        "[CONFIRMAR WVR / DECLARACIÓN DE CALIDAD]."
    ),

    "drafting_diff_pitch_caption": (
        "**Diferenciador y propuesta de venta** -- escribe esto con tus propias palabras: qué "
        "distingue a esta firma en esta propuesta, y el argumento de por qué debería ganar. La "
        "revisión con IA es opcional -- comenta el texto tal como está escrito y ofrece una "
        "reescritura más ajustada y reorientada según el alcance real de este brief, pero solo "
        "trabaja con lo que escribiste aquí, nunca inventa afirmaciones nuevas."
    ),
    "drafting_differentiator_label": "Diferenciador",
    "drafting_differentiator_placeholder": "¿Qué distingue a esta firma en esta propuesta?",
    "drafting_sales_pitch_label": "Propuesta de venta",
    "drafting_sales_pitch_placeholder": "El argumento de por qué esta firma debería ganar.",
    "drafting_review_ai_button": "Revisar con IA",
    "drafting_pitch_review_failed_error": "Falló la revisión de la propuesta de venta",
    "drafting_review_complete_success": "Revisión completa.",
    "drafting_sharpen_heading": "**Perfeccionar con preguntas de seguimiento**",
    "drafting_sharpen_caption": (
        "Genera algunas preguntas puntuales sobre lo que aún resulte vago o sin respaldo en lo "
        "que escribiste arriba (hasta 4 por campo), y luego incorpora tus respuestas "
        "directamente en una reescritura más precisa -- misma regla que en el resto de esta "
        "página, nada se agrega más allá de lo que tú escribes. Solo se ejecuta al hacer clic "
        "en el botón, nunca automáticamente."
    ),
    "drafting_get_questions_button": "Obtener preguntas de perfeccionamiento",
    "drafting_generate_questions_failed_error": "No se pudieron generar las preguntas",
    "drafting_both_specific_caption": (
        "Ambos textos ya se leen específicos y concretos -- no se necesitan preguntas de "
        "seguimiento."
    ),
    "drafting_sharpen_with_answers_button": "Perfeccionar con mis respuestas",
    "drafting_sharpened_success": "Perfeccionado usando tus respuestas -- consulta la reescritura abajo.",
    "drafting_sharpening_failed_error": "Falló el perfeccionamiento",
    "drafting_diff_ai_comment_heading": "**Diferenciador -- comentario de la IA**",
    "drafting_suggested_rewrite_heading": "**Reescritura sugerida**",
    "drafting_use_rewrite_button": "Usar esta reescritura",
    "drafting_pitch_ai_comment_heading": "**Propuesta de venta -- comentario de la IA**",

    "drafting_exec_summary_caption": (
        "**Resumen ejecutivo** -- una página sin ponderación que va justo después de la "
        "portada, antes de las secciones puntuadas (paquete de alcance grande) o justo después "
        "de la portada (paquete de alcance reducido). No tiene puntuación propia, pero es la "
        "primera impresión de los evaluadores, así que se redacta cálida y orientada a la venta "
        "en lugar de árida -- títulos atractivos, bloques breves y legibles, basados en el "
        "brief real y en el equipo nominado (incluido) real."
    ),
    "drafting_exec_summary_draft_first_caption": (
        "Redacta primero las secciones -- el resumen se escribe a partir de lo que la "
        "propuesta realmente dice, para que no pueda prometer un tema que el documento no cubre."
    ),
    "drafting_generate_exec_summary_button": "Generar resumen ejecutivo (IA)",
    "drafting_exec_summary_empty_warning": (
        "El resumen ejecutivo volvió vacío -- no se guardó nada sobre lo que tenías. Inténtalo "
        "de nuevo, o escríbelo tú mismo; la primera página del paquete se exporta como "
        "marcador rojo hasta que exista."
    ),
    "drafting_exec_summary_drafted_success": "Resumen ejecutivo redactado.",
    "drafting_exec_summary_failed_error": "Falló la generación del resumen ejecutivo",
    "drafting_exec_summary_expander": "Resumen ejecutivo",

    "drafting_team_intro_caption": (
        "**Introducción del equipo** -- un breve argumento de venta al inicio de Personal "
        "Clave, antes del organigrama y las reseñas del equipo: un titular llamativo y un par "
        "de párrafos que conectan los proyectos pasados reales del equipo nominado (incluido) "
        "con los desafíos reales de este brief, cerrando con una frase destacada. Basado "
        "enteramente en la reseña de valor para el proyecto y los proyectos relevantes de cada "
        "persona, ingresados en la pestaña Equipo y recursos -- nunca inventado."
    ),
    "drafting_generate_team_intro_button": "Generar introducción del equipo (IA)",
    "drafting_team_intro_empty_warning": (
        "La introducción del equipo volvió vacía. Esto suele significar que las personas "
        "nominadas aún no tienen reseñas -- completa su texto de \"en este proyecto ellos...\" "
        "en Equipo y recursos e inténtalo de nuevo."
    ),
    "drafting_team_intro_drafted_success": "Introducción del equipo redactada.",
    "drafting_team_intro_failed_error": "Falló la generación de la introducción del equipo",
    "drafting_assign_person_caption": "Asigna al menos una persona en la pestaña Equipo y recursos primero.",
    "drafting_team_intro_expander": "Introducción del equipo",

    "drafting_experience_intro_caption": (
        "**Introducción de experiencia en proyectos** -- un breve párrafo orientado a la venta "
        "al inicio de Experiencia relevante en proyectos, antes de las fichas de proyectos "
        "individuales: nombra los 2 a 4 proyectos de referencia comparables más sólidos y "
        "expone claramente por qué demuestran que esta firma puede cumplir con el brief, "
        "reemplazando la nota genérica de 'proyectos anteriores seleccionados'. Basado "
        "enteramente en los proyectos de referencia reales ingresados y redactados en Subir "
        "documentos -- nunca inventado."
    ),
    "drafting_generate_experience_intro_button": "Generar introducción de experiencia en proyectos (IA)",
    "drafting_experience_intro_help": "Necesita al menos un proyecto de referencia redactado -- ver abajo.",
    "drafting_experience_intro_empty_warning": (
        "La introducción de experiencia en proyectos volvió vacía -- puede que los proyectos "
        "de referencia aún no tengan descripción ni texto de relevancia. La sección recurre a "
        "su nota predeterminada hasta que esto exista."
    ),
    "drafting_experience_intro_drafted_success": "Introducción de experiencia en proyectos redactada.",
    "drafting_experience_intro_failed_error": "Falló la generación de la introducción de experiencia en proyectos",
    "drafting_no_reference_projects_caption": (
        "Aún no hay proyectos de referencia redactados. Ve a Subir documentos, sube material "
        "de 'Referencias de proyectos' si no lo has hecho, luego haz clic en **Redactar "
        "proyectos de referencia a partir del material subido** ahí -- o agrega uno "
        "manualmente en ese mismo paso."
    ),
    "drafting_experience_intro_expander": "Introducción de experiencia en proyectos",

    "drafting_page_limit_prefix": "Límite de páginas: {text}",
    "drafting_evaluation_weighting_prefix": "Ponderación de evaluación: {text}",
    "drafting_formatting_prefix": "Formato: {text}",
    "drafting_still_needs_heading": "**Aún necesita de ti:**",

    "drafting_terms_heading": "#### Términos de contratación",
    "drafting_terms_caption": (
        "Siempre tu propio texto -- esta herramienta nunca inventa ni supone qué condiciones "
        "contractuales/comerciales aplican, ya que equivocarse en esto es un riesgo legal real."
    ),
    "drafting_terms_label": "Términos de contratación",
    "drafting_terms_placeholder": (
        "p. ej., Esta oferta se realiza bajo nuestro Acuerdo Marco de Servicios vigente con "
        "Townsville City Council, referencia ..."
    ),

    "drafting_spinner_risk_register": "Estructurando el registro de riesgos...",
    "drafting_spinner_stages": "Redactando etapas de metodología...",
    "drafting_spinner_pitch_review": "Revisando diferenciador y propuesta de venta...",
    "drafting_spinner_questions": "Generando preguntas de seguimiento...",
    "drafting_spinner_sharpening": "Perfeccionando con tus respuestas...",
    "drafting_spinner_exec_summary": "Redactando resumen ejecutivo...",
    "drafting_spinner_team_intro": "Redactando introducción del equipo...",
    "drafting_spinner_experience_intro": "Redactando introducción de experiencia en proyectos...",

    # Part A2 -- Graphics & Design / Team & Resourcing tabs
    # (55_graphics.py, 60_team.py)

    # --- Pestaña 7: Gráficos y diseño ---
    "graphics_project_team_subheader": "Equipo del proyecto",
    "graphics_project_team_caption": (
        "Construido enteramente desde la pestaña Equipo y recursos (paso 8) -- las mismas "
        "personas, las mismas biografías redactadas a partir del CV, y las mismas marcas de "
        "'incluir en la propuesta' usadas ahí también alimentan la sección Equipo del proyecto "
        "de este paquete, así que solo hay un lugar para construir tu equipo, sea cual sea el "
        "tamaño de paquete que estés preparando. Ve al paso 8 para asignar personas, redactar "
        "biografías desde la biblioteca de CV, agregar un integrante bajo un líder de "
        "disciplina (con su propio título), y marcar quién queda incluido. Esta es una vista "
        "previa de solo lectura de lo que mostrará el paquete exportado."
    ),
    "graphics_project_team_empty_info": (
        "Aún no hay nadie asignado y marcado con 'Incluir en la propuesta' -- ve al paso 8 "
        "(Equipo y recursos) para construir el equipo."
    ),
    "graphics_not_assigned": "[sin asignar]",
    "graphics_subheader": "Gráficos y diseño",
    "graphics_caption": (
        "Banners divisores y portadas reales, generados a partir de tus propias fotos subidas "
        "y citas escritas -- nunca imágenes inventadas. Todo lo que esta herramienta no puede "
        "construir de verdad (organigramas, diagramas de metodología, cronogramas del programa) "
        "queda como un marcador de posición claramente indicado abajo."
    ),
    "graphics_need_structure_info": "Genera primero la Estructura de la propuesta.",
    "graphics_quotes_heading": "#### 1. Citas destacadas / testimonios (opcional)",
    "graphics_quotes_caption": "Solo citas reales que escribas aquí -- nada se inventa ni se toma de internet.",
    "graphics_quote_label": "Cita",
    "graphics_quote_placeholder": "p. ej., \"El equipo entregó un resultado técnicamente excelente...\"",
    "graphics_quote_attributed_label": "Atribuida a",
    "graphics_quote_attributed_placeholder": "p. ej., J. Smith, Director de Proyecto, XYZ Council",
    "graphics_quote_project_label": "Proyecto (opcional)",
    "graphics_quote_project_placeholder": "p. ej., Puente del Río Burnett",
    "graphics_add_quote_button": "Agregar cita",
    "graphics_unattributed": "sin atribuir",
    "graphics_remove_button": "Eliminar",
    "graphics_photos_heading": "#### 2. Fotos del proyecto",
    "graphics_photos_caption": (
        "Elige la foto de portada. Llena la primera página del paquete; el resto queda "
        "disponible para los divisores de sección más abajo."
    ),
    "graphics_photo_preview_failed": "(no se pudo previsualizar la foto {n})",
    "graphics_on_cover_caption": "**En la portada**",
    "graphics_use_as_cover_button": "Usar como portada",
    "graphics_divider_heading": "#### 3. Diseño de divisor por sección",
    "graphics_no_photos_info": (
        "No se han subido fotos del proyecto (Subir documentos) -- las secciones usan por "
        "defecto el diseño 'Color sólido'. Sube fotos ahí para desbloquear los diseños con foto."
    ),
    "graphics_layout_label": "Diseño",
    "graphics_photo_select_label": "Foto",
    "graphics_photo_option": "Foto {n}",
    "graphics_none_option": "(ninguna)",
    "graphics_quote_select_label": "Cita",
    "graphics_quote_fallback_label": "Cita",
    "graphics_photo_title_label": "Título de la foto",
    "graphics_photo_title_placeholder": "p. ej., Puente Mangaweka",
    "graphics_photo_title_help": (
        "Se muestra en la esquina inferior derecha de la foto misma, no en la banda de color. "
        "Solo se usa cuando esta sección tiene una foto."
    ),
    "graphics_current_banner_caption": "Banner actual de esta sección",
    "graphics_font_heading": "#### 3. Fuente del documento",
    "graphics_font_label": "Fuente de cuerpo y títulos",
    "graphics_font_help": "Se aplica al documento Word exportado y al texto de los divisores.",
    "graphics_generate_heading": "#### 4. Generar",
    "graphics_generate_button": "Generar paquete de gráficos",
    "graphics_default_tender_pack_name": "Paquete de respuesta a la licitación",
    "graphics_generated_success": "Se generaron {banners} banner(es) divisor(es) y {recs} recomendación(es) de gráficos.",
    "graphics_remaining_placeholders_heading": "#### Resumen de marcadores de posición restantes",
    "graphics_col_graphic": "Gráfico",
    "graphics_col_type": "Tipo",
    "graphics_col_placement": "Ubicación",
    "graphics_col_source_needed": "Fuente necesaria",
    "graphics_col_status": "Estado",
    "graphics_weighting_dashboard_heading": "#### Panel de ponderación de evaluación (generado)",

    # --- Pestaña 8: Equipo y recursos ---
    "team_subheader": "Equipo y recursos",
    "team_caption": (
        "Identifica quién cubre cada disciplina que exige el brief, además de los roles de "
        "gestión permanentes que lleva todo proyecto, y luego genera un organigrama del "
        "proyecto para la sección de Personal Clave. Los nombres provienen de tu biblioteca "
        "de CV subida cuando sea posible, pero también puedes escribir a cualquiera de quien "
        "no hayas subido un CV."
    ),
    "team_run_analysis_first_info": "Ejecuta primero el Análisis de la licitación -- las disciplinas requeridas provienen del brief.",
    "team_load_names_button": "Cargar nombres desde la biblioteca de CV",
    "team_load_names_help": "Sube una biblioteca de CV (Subir documentos) y {ai_hint}.",
    "team_spinner_load_names": "Leyendo toda la biblioteca de CV en busca de nombres (unos segundos por lote)...",
    "team_names_found_success": "Se encontraron {n} nombre(s): {names}",
    "team_load_names_error": "No se pudieron leer los nombres desde la biblioteca de CV",
    "team_available_names_caption": "Nombres disponibles: {names}",
    "team_no_names_caption": "Aún no hay nombres -- haz clic en 'Cargar nombres desde la biblioteca de CV', o agrega personas manualmente abajo.",
    "team_reupload_cv_tip_caption": (
        "💡 Consejo: para obtener la lista más completa y precisa, vuelve a subir los archivos "
        "de tu biblioteca de CV en Subir documentos -- cada nombre de archivo da el nombre "
        "completo de una persona al instante, sin que la IA tenga que adivinar. (Tu proyecto "
        "cargado conservó el texto de los CV pero no los nombres de archivo.)"
    ),
    "team_management_roles_heading": "#### Roles de gestión",
    "team_management_roles_caption": (
        "El PM del cliente está en la parte superior del organigrama, luego tu Director de "
        "Proyecto y tu Gerente de Proyecto -- esos tres siempre están presentes. El Gerente de "
        "Diseño es opcional: quítalo con la ✕ si esta comisión no tiene uno, y desaparece por "
        "completo del organigrama y del paquete en lugar de quedar como un TBC sin resolver."
    ),
    "team_add_role_button": "+ Agregar {role}",
    "team_role_off_chart_caption": (
        "{role} está actualmente fuera del organigrama de este proyecto. Volver a agregarlo "
        "restaura aquí una fila sin asignar -- nada más cambia."
    ),
    "team_discipline_leads_heading": "#### Líderes de disciplina",
    "team_discipline_leads_caption": (
        "Uno por cada disciplina que exige el brief. Agrega o quita disciplinas según sea "
        "necesario. Gestión de proyecto no aparece aquí -- la cubre el rol de Gerente de "
        "Proyecto arriba -- pero de todos modos tiene su propia línea en la pestaña de "
        "estimación de honorarios."
    ),
    "team_rescan_button": "Reexaminar el brief en busca de disciplinas",
    "team_rescan_help": "Necesita el brief de la licitación (Subir documentos) y {ai_hint}.",
    "team_spinner_rescan": "Releyendo el brief en busca de todas las disciplinas que implica el alcance...",
    "team_disciplines_added_success": "Agregadas: {names}",
    "team_no_new_disciplines_info": "No se encontraron disciplinas nuevas más allá de las ya listadas.",
    "team_rescan_failed_error": "Falló el reexamen de disciplinas",
    "team_rescan_caption": (
        "Lee el brief e infiere las disciplinas que implica el alcance (ambiental, "
        "constructibilidad, ferroviario, topografía, etc.), aunque no se hayan nombrado "
        "explícitamente."
    ),
    "team_add_discipline_label": "Agregar una disciplina",
    "team_add_discipline_placeholder": "p. ej., Paisajismo, Topografía, Constructibilidad",
    "team_add_discipline_button": "Agregar disciplina",
    "team_pm_not_separate_warning": (
        "Gestión de proyecto la cubre el rol de Gerente de Proyecto arriba, no se agrega aquí "
        "como una disciplina aparte. De todos modos tiene su propia línea en la pestaña de "
        "estimación de honorarios."
    ),
    "team_add_no_cv_heading": "#### Agregar a alguien sin CV",
    "team_add_no_cv_caption": (
        "Los nombres que escribas aquí quedan disponibles en todos los desplegables de arriba "
        "-- para personas que quieres en el organigrama pero que no tienen un CV subido."
    ),
    "team_person_name_label": "Nombre de la persona",
    "team_person_name_placeholder": "p. ej., Jordan Lee",
    "team_add_name_button": "Agregar nombre",
    "team_key_personnel_heading": "#### Detalles del perfil del personal clave",
    "team_key_personnel_caption": (
        "Alimenta los perfiles numerados de Personal Clave en el paquete exportado -- Director "
        "de Proyecto, Gerente de Proyecto, Gerente de Diseño (cuando el proyecto tiene uno), "
        "luego los líderes de disciplina, en ese orden. Todo esto "
        "es texto opcional, ingresado por el usuario (nunca adivinado): deja un campo en blanco "
        "y la exportación muestra en su lugar un marcador de posición claramente indicado."
    ),
    "team_overwrite_checkbox_label": "Sobrescribir valores existentes (releer desde los CV, reemplazando lo que hay)",
    "team_overwrite_checkbox_help": (
        "Desactivado (predeterminado): solo completa los campos en blanco, protegiendo lo que "
        "hayas escrito. Activado: relee el CV de cada persona asignada y reemplaza los valores "
        "actuales -- úsalo para corregir datos incorrectos que quedaron de una ejecución anterior."
    ),
    "team_fill_profile_button": "Completar campos del perfil desde los CV",
    "team_fill_profile_help": "Asigna personas a los roles de arriba, sube una biblioteca de CV (Subir documentos) y {ai_hint}.",
    "team_spinner_fill_profile": (
        "Leyendo el CV de cada persona en busca de estado de registro, experiencia y "
        "relevancia (unos segundos por lote)..."
    ),
    "team_verb_updated": "Actualizados",
    "team_verb_filled": "Completados",
    "team_profile_filled_success": (
        "{verb} los detalles del perfil de: {names}. Revísalos antes de exportar -- los campos "
        "que quedan en blanco significan que el CV no indicaba claramente ese dato."
    ),
    "team_profile_none_overwrite_info": (
        "No se encontraron detalles de perfil en los CV para escribir -- los CV no indican "
        "claramente estos datos, o ninguna persona asignada pudo emparejarse con un archivo de CV."
    ),
    "team_profile_none_info": (
        "No se encontraron nuevos detalles de perfil -- las entradas existentes se dejaron tal "
        "cual. Marca 'Sobrescribir valores existentes' para releerlas y reemplazarlas."
    ),
    "team_fill_profile_error": "No se pudieron completar los campos del perfil desde los CV",
    "team_fill_profile_caption": (
        "Lee el propio archivo de CV de cada persona asignada (de forma aislada, para que los "
        "datos de nadie se mezclen con los de otra persona) en busca de su estado de "
        "registro/colegiatura y sus años de experiencia declarados, y redacta una línea "
        "\"En este proyecto, [nombre] hará...\" a partir de su trayectoria real."
    ),
    "team_include_caption": (
        "**Incluir en la propuesta** -- marca qué reseñas realmente entran en la sección de "
        "Personal Clave exportada. Un perfil completo con foto y redacción ocupa espacio real "
        "de página, así que cuando una sección con límite de páginas esté llena, desmarca a "
        "cualquiera cuyo perfil no sea esencial incluir -- de todos modos siguen en el trabajo "
        "(siguen en el organigrama y en el cálculo de honorarios), simplemente no tendrán un "
        "perfil dedicado. Los roles de liderazgo que lleve este proyecto siempre se recomiendan "
        "(liderazgo del proyecto); el resto de las marcas puede predefinirse a partir de una "
        "lectura por IA del alcance de este proyecto abajo, y siempre puedes anular cualquier "
        "marca a mano."
    ),
    "team_suggest_button": "Sugerir qué personal incluir (IA)",
    "team_suggest_help": "Asigna roles arriba y {ai_hint}.",
    "team_spinner_suggest": "Leyendo el alcance de este proyecto para juzgar qué perfiles de disciplina vale la pena incluir...",
    "team_suggest_applied_success": "Recomendaciones aplicadas -- revisa las marcas y los motivos abajo, y ajústalos a mano según sea necesario.",
    "team_suggest_error": "No se pudieron obtener recomendaciones de la IA",
    "team_include_checkbox_label": "Incluir en la propuesta",
    "team_refresh_button": "Actualizar desde el CV",
    "team_refresh_help": "Asigna un nombre, sube una biblioteca de CV (Subir documentos) y {ai_hint}.",
    "team_spinner_refresh": "Releyendo el CV de {name}...",
    "team_refresh_success": "Se actualizó {name} desde su propio archivo de CV.",
    "team_refresh_thin_warning": (
        "Se leyó el archivo de CV de {name} pero no se encontraron detalles para completar. "
        "Esto suele significar que el texto almacenado de su CV está incompleto (por ejemplo, "
        "se subió antes de una corrección reciente en la extracción) y no que el CV esté "
        "realmente vacío -- intenta volver a subir el CV de {name} en Subir documentos, luego "
        "actualiza de nuevo."
    ),
    "team_refresh_not_found_warning": (
        "No se pudo encontrar/releer el archivo de CV de {name} -- verifica que su nombre de "
        "archivo derive exactamente a este nombre, o que su CV esté en la biblioteca (Subir "
        "documentos)."
    ),
    "team_refresh_error": (
        "No se pudo actualizar a {name} desde su CV -- inténtalo de nuevo. Si sigue "
        "ocurriendo, escribe a hello@civilproposals.com y lo revisaremos."
    ),
    "team_ai_note_prefix": "Nota de la IA: {reason}",
    "team_stance_recommended": "Recomendado",
    "team_stance_not_essential": "No esencial",
    "team_ai_note_stance_prefix": "Nota de la IA ({stance}): {reason}",
    "team_details_expander": "Detalles",
    "team_assign_name_first_caption": "Asigna un nombre a este rol arriba antes de agregar detalles del perfil.",
    "team_qualification_label": "Calificación",
    "team_rpeq_label": "RPEQ / estado de registro",
    "team_years_experience_label": "Años de experiencia",
    "team_value_to_project_label": "En este proyecto, {person} hará...",
    "team_relevant_projects_label": "Experiencia relevante en proyectos (uno por línea)",
    "team_local_experience_label": "Experiencia local en la región (una por línea)",
    "team_headshot_label": "Foto de perfil (opcional)",
    "team_org_chart_heading": "#### Organigrama del proyecto",
    "team_org_chart_caption": (
        "{assigned} de {total} puestos asignados. Un puesto sin asignar se muestra como un TBC "
        "en rojo en el organigrama -- un rol que quitaste no se muestra en absoluto."
    ),
    "team_chart_render_failed_caption": (
        "No se pudo dibujar el organigrama en este momento -- tu equipo no se ve afectado. "
        "Inténtalo de nuevo, y si sigue ocurriendo escribe a hello@civilproposals.com."
    ),
    "team_use_chart_button": "Usar este organigrama en el paquete exportado",
    "team_chart_saved_success": "Guardado. Este organigrama ahora aparece en la sección de Personal Clave del paquete exportado.",
    "team_chart_none_caption": "El paquete exportado aún no tiene organigrama -- haz clic para agregar este.",
    "team_chart_stale_warning": (
        "**El paquete exportado todavía tiene el organigrama "
        "{style}.** Haz clic para reemplazarlo por el de arriba."
    ),
    "team_chart_current_caption": "El paquete exportado tiene este organigrama.",

    # Part A2 -- Fee Estimate tabs (70_commercial_small.py, 71_commercial_large.py)

    # --- Pestaña 9: Estimación de honorarios -- paquete de alcance reducido (70_commercial_small.py) ---
    "fee_small_tab_title_fees_program": "Honorarios y programa",
    "fee_small_tab_title_fee_estimate": "Estimación de honorarios",
    "fee_small_letter_caption": (
        "El **desglose de honorarios por disciplina ($)** y el **reparto de honorarios por "
        "disciplina (%)** de abajo son las dos tablas que realmente se incluyen en el paquete, "
        "junto con el programa de ejecución. La tabla de elementos de alcance es solo para "
        "seguimiento interno y nunca se exporta."
    ),
    "fee_small_run_analysis_first": (
        "Ejecuta primero el Análisis de la licitación -- las tablas de honorarios se "
        "construyen a partir de las propias disciplinas y elementos de alcance del brief."
    ),
    "fee_small_run_tender_scope_items": "Ejecuta el Análisis de la licitación para extraer primero los elementos de alcance.",
    "fee_small_scope_items_heading": "#### Honorarios por elemento de alcance",
    "fee_small_scope_seed_explanation": (
        "Cómo se generan las cifras iniciales: cada elemento de alcance recibe un peso de "
        "1 + la cantidad de tareas que enumera (así que incluso un elemento sin tareas "
        "obtiene una parte base), y luego el total aproximado de abajo se reparte entre "
        "los elementos en proporción a ese peso, redondeado a los $50 más cercanos. Es un "
        "indicador aproximado del esfuerzo basado en el número de tareas, no una estimación "
        "real -- edita cada fila antes de confiar en ella. Esta tabla es solo para tu "
        "seguimiento interno; **no** se incluye en el paquete exportado -- lo que se exporta "
        "es el reparto de honorarios por disciplina más abajo (que refleja la tabla de "
        "desglose de honorarios)."
    ),
    "fee_small_ballpark_total_label": "Valor total aproximado del proyecto ($, sin incluir GST)",
    "fee_small_seed_button": "Generar tabla de honorarios a partir del total",
    "fee_small_scope_note_default": "Ingresa el honorario -- no se generó una estimación",
    "fee_small_col_scope_item_deliverable": "Elemento de alcance / entregable",
    "fee_small_col_fee_amount": "Honorario ($, sin incluir GST)",
    "fee_small_col_notes": "Notas",
    "fee_small_delete_row_hint": (
        "Para eliminar una fila: marca la casilla a su izquierda y luego presiona "
        "Suprimir/Retroceso en tu teclado, o haz clic en el ícono 🗑 que aparece "
        "encima de la tabla."
    ),
    "fee_small_scope_ticked_stale": (
        "El total de abajo corresponde a la última vez que marcaste la casilla de arriba -- "
        "vuelve a marcarla para actualizarlo."
    ),
    "fee_small_scope_ticked_current": "El total de abajo refleja los datos marcados arriba.",
    "fee_small_scope_total": "**Total: ${total}**",
    "fee_small_scope_unpriced_warning": (
        "Al menos un elemento de alcance todavía no tiene honorario ingresado -- el paquete "
        "exportado lo marca en rojo hasta que se cotice cada fila."
    ),
    "fee_small_scope_pm_readded_info": "Gestión de proyecto es una línea fija y se ha vuelto a agregar.",
    "fee_small_discipline_heading": "#### Desglose de honorarios por disciplina (primera versión)",
    "fee_small_discipline_caption": (
        "Tu propio honorario de primera versión por disciplina, calculado a partir de "
        "horas x tarifa -- el mismo desglose que la pestaña Estimación de honorarios del "
        "paquete de alcance grande, y las mismas cifras si cambias un proyecto entre "
        "tamaños de paquete. La tabla se genera a partir de las disciplinas que exige el "
        "brief, más Gestión de proyecto (siempre incluida). Ingresa el total de horas y "
        "una tarifa por hora para cada disciplina -- la columna Total se calcula "
        "automáticamente. Se incluye un total por disciplina (no las horas/tarifas en sí) "
        "en la sección de Honorarios del paquete exportado."
    ),
    "fee_small_rate_prefilled": (
        "Se completó la tarifa de {n} disciplina(s) a partir de la tarifa de tu Perfil de "
        "la empresa. Las horas siguen siendo tuyas para ingresar."
    ),
    "fee_small_col_discipline": "Disciplina",
    "fee_small_col_total_hours": "Horas totales",
    "fee_small_col_rate_per_hour": "Tarifa por hora ($)",
    "fee_small_col_total_amount": "Total ($, sin incluir GST)",
    "fee_small_col_total_amount_help": "Se calcula automáticamente -- horas totales x tarifa por hora.",
    "fee_small_col_note": "Nota",
    "fee_small_ticked_stale": (
        "Los totales, el gráfico y la exportación a Excel de abajo corresponden a la "
        "última vez que marcaste la casilla de arriba -- vuelve a marcarla para actualizarlos."
    ),
    "fee_small_ticked_current": "Los totales, el gráfico y la exportación a Excel de abajo reflejan los datos marcados arriba.",
    "fee_small_disc_total_label": "**Total de honorarios por disciplina: ${value}**",
    "fee_small_avg_rate_label": "**Tarifa promedio del proyecto: {value}**",
    "fee_small_avg_rate_unset": "-- (ingresa horas para calcularla)",
    "fee_small_pm_readded_info": "Gestión de proyecto siempre forma parte del desglose de honorarios y se ha vuelto a agregar.",
    "fee_small_export_excel_button": "Exportar a Excel",
    "fee_small_export_hours_help": (
        "Incluye una fila de Total y la tarifa promedio del proyecto (honorario total / horas totales)."
    ),
    "fee_small_export_unavailable_caption": (
        "La exportación a Excel no está disponible en este momento -- escribe a "
        "hello@civilproposals.com si esto sigue ocurriendo."
    ),
    "fee_small_scope_expander_title": "Honorarios por elemento de alcance (solo seguimiento interno -- no se exporta)",
    "fee_small_delivery_program_heading": "#### Programa de ejecución",
    "fee_small_num_weeks_label": "Número de semanas",
    "fee_small_start_date_label": "Fecha de inicio prevista (opcional)",
    "fee_small_start_date_help": (
        "Tu propia fecha de inicio prevista, no algo leído del brief. Al definirla, cada "
        "encabezado de semana se convierte en una fecha real (\"Wk 1 - 6 Oct\") en la "
        "tabla del programa y en el PowerPoint del programa. Déjala en blanco para "
        "mantener solo los números de semana."
    ),
    "fee_small_generate_program_button": "Generar programa predeterminado",
    "fee_small_col_scope_item": "Elemento de alcance",
    "fee_small_program_empty_info": (
        "Haz clic en 'Generar programa predeterminado' para obtener una cuadrícula inicial "
        "editable, dimensionada según cuántas tareas enumera cada elemento de alcance -- "
        "ajusta las semanas libremente después."
    ),
    "fee_small_pct_split_expander": "Reparto de honorarios por disciplina (%)",
    "fee_small_pct_split_caption": (
        "Su lista de disciplinas siempre coincide con la tabla de desglose de honorarios "
        "por disciplina de arriba -- agrega o quita disciplinas ahí, no aquí."
    ),
    "fee_small_total_fee_label": (
        "Honorario total del proyecto ($, sin incluir GST) -- se usa para convertir el % "
        "de honorario en una cifra en $ abajo"
    ),
    "fee_small_total_fee_help": (
        "Comienza prellenado con el total del desglose de honorarios por disciplina de "
        "arriba, y luego queda editable de forma independiente -- cámbialo aquí para usar "
        "un total distinto únicamente en la columna $ de este reparto por %, la "
        "exportación a Excel y el gráfico. No cambia la tabla de desglose en sí."
    ),
    "fee_small_reset_pct_button": "Restablecer % desde el desglose de honorarios por disciplina",
    "fee_small_benchmark_button": "Estimar a partir de referencias incluidas",
    "fee_small_enter_hours_first_warning": "Ingresa primero las horas y tarifas en la tabla de desglose de honorarios por disciplina de arriba.",
    "fee_small_ai_spinner": "Preguntando a la IA cómo se suele repartir un honorario como este...",
    "fee_small_col_fee_pct": "% de honorario",
    "fee_small_col_indicative_amount": "$ indicativo",
    "fee_small_col_indicative_amount_help": "% de honorario x el honorario total del proyecto ingresado arriba -- se recalcula automáticamente.",
    "fee_small_col_typical_range": "Rango habitual",
    "fee_small_col_typical_range_help": (
        "El rango que realmente respalda la fuente -- el % de honorario único es su punto "
        "medio. Queda en blanco cuando la fuente dio una estimación puntual en lugar de "
        "un rango."
    ),
    "fee_small_col_confidence": "Confianza",
    "fee_small_col_source": "Fuente",
    "fee_small_source_from_buildup": "Del desglose de honorarios por disciplina",
    "fee_small_confidence_user_set": "Definido por el usuario",
    "fee_small_note_always_included": "Siempre incluido -- se ha vuelto a agregar automáticamente",
    "fee_small_pie_title_discipline_buildup": "Distribución de honorarios por disciplina (horas x tarifa)",
    "fee_small_pie_title_pct_split": "Reparto de honorarios por disciplina",
    "fee_small_pct_total_caption": "Total: {pct}% (no es necesario que sume exactamente 100%).",

    # --- Pestaña 9: Estimación de honorarios -- paquete de alcance grande (71_commercial_large.py) ---
    "fee_large_run_analysis_first": (
        "Ejecuta primero el Análisis de la licitación -- las tablas de honorarios se "
        "construyen a partir de las propias disciplinas y elementos de alcance del brief."
    ),
    "fee_large_discipline_heading": "#### Desglose de honorarios por disciplina (primera versión)",
    "fee_large_discipline_caption": (
        "Tu propio honorario de primera versión por disciplina, calculado a partir de "
        "horas x tarifa. La tabla se genera a partir de las disciplinas que exige el "
        "brief, más Gestión de proyecto (siempre incluida). Ingresa el total de horas y "
        "una tarifa por hora para cada disciplina -- la columna Total se calcula "
        "automáticamente, no se escribe directamente. Agrega o quita filas según sea "
        "necesario -- estas son tus cifras, no una estimación de la IA."
    ),
    "fee_large_rate_prefilled": (
        "Se completó la tarifa de {n} disciplina(s) a partir de la tarifa de tu Perfil de "
        "la empresa. Las horas siguen siendo tuyas para ingresar."
    ),
    "fee_large_col_discipline": "Disciplina",
    "fee_large_col_total_hours": "Horas totales",
    "fee_large_col_rate_per_hour": "Tarifa por hora ($)",
    "fee_large_col_total_amount": "Total ($, sin incluir GST)",
    "fee_large_col_total_amount_help": "Se calcula automáticamente -- horas totales x tarifa por hora.",
    "fee_large_col_note": "Nota",
    "fee_large_delete_row_hint": (
        "Para eliminar una fila: marca la casilla a su izquierda y luego presiona "
        "Suprimir/Retroceso en tu teclado, o haz clic en el ícono 🗑 que aparece "
        "encima de la tabla."
    ),
    "fee_large_ticked_stale": (
        "Los totales, el gráfico y la exportación a Excel de abajo corresponden a la "
        "última vez que marcaste la casilla de arriba -- vuelve a marcarla para actualizarlos."
    ),
    "fee_large_ticked_current": "Los totales, el gráfico y la exportación a Excel de abajo reflejan los datos marcados arriba.",
    "fee_large_disc_total_label": "**Total de honorarios por disciplina: ${value}**",
    "fee_large_avg_rate_label": "**Tarifa promedio del proyecto: {value}**",
    "fee_large_avg_rate_unset": "-- (ingresa horas para calcularla)",
    "fee_large_pm_readded_info": "Gestión de proyecto siempre forma parte del desglose de honorarios y se ha vuelto a agregar.",
    "fee_large_export_excel_button": "Exportar a Excel",
    "fee_large_export_hours_help": (
        "Incluye una fila de Total y la tarifa promedio del proyecto (honorario total / horas totales)."
    ),
    "fee_large_export_unavailable_caption": (
        "La exportación a Excel no está disponible en este momento -- escribe a "
        "hello@civilproposals.com si esto sigue ocurriendo."
    ),
    "fee_large_hours_chart_hint_caption": (
        "Ingresa horas y una tarifa para al menos una disciplina arriba para ver el "
        "gráfico de distribución de honorarios."
    ),
    "fee_large_scope_heading": "#### Desglose de honorarios por elemento de alcance / entregable",
    "fee_large_scope_run_tender_info": "Ejecuta el Análisis de la licitación para extraer primero los elementos de alcance y entregables.",
    "fee_large_scope_caption": (
        "Prellenada con los elementos de alcance/entregables extraídos del brief, uno "
        "por fila, para tener una lista inicial real que cotizar en lugar de una tabla "
        "vacía -- edita, renombra, elimina o agrega filas libremente; nada de esto se "
        "exporta automáticamente (lo que alimenta el paquete es el desglose por "
        "disciplina de arriba)."
    ),
    "fee_large_scope_note_default": "Ingresa el honorario -- no se generó una estimación",
    "fee_large_col_scope_item_deliverable": "Elemento de alcance / entregable",
    "fee_large_col_fee_amount": "Honorario ($, sin incluir GST)",
    "fee_large_col_notes": "Notas",
    "fee_large_scope_ticked_stale": (
        "El total de abajo corresponde a la última vez que marcaste la casilla de arriba -- "
        "vuelve a marcarla para actualizarlo."
    ),
    "fee_large_scope_ticked_current": "El total de abajo refleja los datos marcados arriba.",
    "fee_large_scope_pm_readded_info": "Gestión de proyecto es una línea fija y se ha vuelto a agregar.",
    "fee_large_scope_total_label": "**Total: ${total}**",
    "fee_large_delivery_program_heading": "#### Programa de ejecución",
    "fee_large_delivery_program_caption": (
        "Un cronograma de ejecución inicial para tus elementos de alcance. A diferencia "
        "del paquete de alcance reducido, esto no se incorpora al DOCX -- descárgalo "
        "como una tabla de PowerPoint editable desde la pestaña Exportar paquete para "
        "pegarlo en una diapositiva de programa/metodología."
    ),
    "fee_large_num_weeks_label": "Número de semanas",
    "fee_large_start_date_label": "Fecha de inicio prevista (opcional)",
    "fee_large_start_date_help": (
        "Tu propia fecha de inicio prevista, no algo leído del brief. Al definirla, cada "
        "encabezado de semana se convierte en una fecha real (\"Wk 1 - 6 Oct\") en la "
        "tabla del programa y en el PowerPoint del programa. Déjala en blanco para "
        "mantener solo los números de semana."
    ),
    "fee_large_generate_program_button": "Generar programa predeterminado",
    "fee_large_col_scope_item": "Elemento de alcance",
    "fee_large_program_empty_info": (
        "Haz clic en 'Generar programa predeterminado' para obtener una cuadrícula inicial "
        "editable, dimensionada según cuántas tareas enumera cada elemento de alcance -- "
        "ajusta las semanas libremente después."
    ),
    "fee_large_pct_heading": "#### Reparto indicativo de honorarios por disciplina",
    "fee_large_pct_caption": (
        "Su lista de disciplinas siempre coincide con la tabla de desglose de honorarios "
        "por disciplina de arriba -- agrega o quita disciplinas ahí, no aquí. El % de "
        "honorario se puede editar directamente abajo; restablécelo a partir del propio "
        "reparto en $ del desglose, o genera un valor inicial con los botones de "
        "referencias/IA (en cualquier caso, remapeado a la lista de disciplinas del "
        "desglose)."
    ),
    "fee_large_total_fee_label": "Honorario total del proyecto ($, sin incluir GST) -- opcional",
    "fee_large_total_fee_help": (
        "Comienza prellenado con el total del desglose de honorarios por disciplina de "
        "arriba, y luego queda editable de forma independiente -- cámbialo aquí para usar "
        "un total distinto únicamente en la columna $ de este reparto, la exportación a "
        "Excel y el gráfico. No cambia la tabla de desglose en sí."
    ),
    "fee_large_reset_pct_button": "Restablecer % desde el desglose de honorarios por disciplina",
    "fee_large_benchmark_button": "Estimar a partir de referencias incluidas",
    "fee_large_enter_hours_first_warning": "Ingresa primero las horas y tarifas en la tabla de desglose de honorarios por disciplina de arriba.",
    "fee_large_ai_spinner": "Preguntando a la IA cómo se suele repartir un honorario como este...",
    "fee_large_col_fee_pct": "% de honorario",
    "fee_large_col_indicative_amount": "$ indicativo",
    "fee_large_col_indicative_amount_help": (
        "% de honorario x el total manual ingresado arriba (si se ingresó), o x el total "
        "del desglose de honorarios por disciplina en caso contrario."
    ),
    "fee_large_col_typical_range": "Rango habitual",
    "fee_large_col_typical_range_help": (
        "El rango que realmente respalda la fuente -- el % de honorario único es su punto "
        "medio. Queda en blanco cuando la fuente dio una estimación puntual en lugar de "
        "un rango."
    ),
    "fee_large_col_confidence": "Confianza",
    "fee_large_col_source": "Fuente",
    "fee_large_source_from_buildup": "Del desglose de honorarios por disciplina",
    "fee_large_confidence_user_set": "Definido por el usuario",
    "fee_large_note_always_included": "Siempre incluido -- se ha vuelto a agregar automáticamente",
    "fee_large_pie_title_discipline_buildup": "Distribución de honorarios por disciplina (horas x tarifa)",
    "fee_large_pie_title_pct_split": "Reparto indicativo de honorarios por disciplina",
    "fee_large_pct_total_caption": "Total: {pct}% (no es necesario que sume exactamente 100%).",

    # Part A2 -- Project Setup / Upload Documents tabs, plus Tender Analysis
    # stragglers (30_setup_upload_analysis.py)

    # --- Pestaña 1: Configuración del proyecto ---
    "setup_subheader": "Configuración del proyecto",
    "setup_caption": "Datos básicos del proyecto -- se usan en todo el flujo de trabajo y en la portada del paquete exportado.",
    "setup_format_heading": "**Formato de la propuesta**",
    "setup_format_caption": (
        "La herramienta es independiente de lo que realmente sea el proyecto -- el alcance, el "
        "equipo y los honorarios siempre provienen de lo que subas, nunca del formato que "
        "elijas. Esto solo cambia la forma del resultado: un paquete de alcance grande "
        "encuadernado con secciones nombradas y límites de páginas, o un paquete de alcance "
        "reducido más corto con las mismas secciones pero más liviano (típico para un brief "
        "pequeño, o una solicitud del cliente por correo electrónico)."
    ),
    "setup_format_select_label": "¿Qué necesita esta licitación?",
    "setup_project_name_label": "Nombre del proyecto",
    "setup_client_name_label": "Nombre del cliente",
    "setup_tender_name_label": "Nombre de la licitación / EOI",
    "setup_submission_date_label": "Fecha de presentación",
    "setup_submission_date_placeholder": "p. ej., 14 de julio de 2026",
    "setup_bidder_name_label": "Nombre del oferente / empresa",
    "setup_project_type_label": "Tipo de proyecto",
    "setup_proposal_theme_label": "Tema de la propuesta",
    "setup_autosave_caption": "Se guarda mientras escribes -- no hay un paso de guardado aparte.",
    "setup_date_mismatch_warning": (
        "**Discrepancia en la fecha de presentación.** Ingresaste **{typed_date}**, pero la "
        "fecha indicada en el propio brief dice **{brief_date}**. La fecha que escribes aquí es "
        "la que se imprime en la portada -- verifica cuál es la correcta antes de exportar."
    ),
    "setup_sender_name_label": "Nombre del remitente",
    "setup_sender_name_placeholder": "p. ej., Jane Smith",
    "setup_sender_title_label": "Cargo del remitente",
    "setup_sender_title_placeholder": "p. ej., Director de Proyecto",
    "setup_sender_phone_label": "Teléfono del remitente",
    "setup_sender_email_label": "Correo electrónico del remitente",
    "setup_sender_address_label": "Dirección registrada / comercial",
    "setup_sender_address_placeholder": "p. ej., Nivel 3, 100 Example St, Brisbane QLD 4000",
    "setup_sender_address_help": (
        "Se usa para completar las etiquetas de dirección en los formularios de retorno del "
        "cliente. Deliberadamente NO se agrega al bloque de cierre \"Atentamente\" de la carta, "
        "que se mantiene como nombre/cargo/teléfono/correo por diseño."
    ),
    "setup_signoff_heading": "#### Datos de cierre",
    "setup_signoff_caption": (
        "Quién firma este paquete -- se muestra en el bloque de cierre \"Atentamente\" al final "
        "del documento. La portada y el pie de página ya llevan los datos de proyecto/cliente/"
        "oferente ingresados arriba, así que no se necesita nada más aquí. La dirección solo se "
        "usa al completar los formularios de retorno del cliente."
    ),
    "setup_contact_expander": "Datos de contacto / firmante (opcional)",
    "setup_contact_expander_caption": (
        "No se usa en el propio documento de alcance grande. Estos son los valores que el "
        "completador de formularios de retorno coloca en los propios formularios del cliente "
        "junto a etiquetas como \"Persona de contacto\", \"Teléfono\", \"Correo electrónico\" y "
        "\"Domicilio registrado\" -- déjalos en blanco y esas etiquetas obtienen en su lugar un "
        "marcador de posición [POR COMPLETAR]."
    ),

    # --- Pestaña 2: Subir documentos ---
    "upload_subheader": "Subir documentos",
    "upload_caption": "El brief de la licitación es obligatorio. Todo lo demás es opcional, pero mejora mucho la calidad del borrador.",
    "upload_brief_intro": (
        "**Brief de la licitación (obligatorio)** -- PDF, DOCX, TXT, o un **ZIP** completo del "
        "paquete de licitación. A veces un brief llega como varios documentos separados (por "
        "ejemplo, el RFT principal más adendas, anexos o programas) -- súbelos todos aquí y se "
        "combinarán en un solo brief. Un ZIP se descomprime y clasifica automáticamente: el brief "
        "y las adendas van al análisis, los formularios de retorno se guardan aparte para "
        "completarlos, y los planos se dejan de lado. Si ya resaltaste o comentaste algún "
        "documento mientras lo leías, sube esa copia marcada -- tus notas también se leen."
    ),
    "upload_tender_files_label": "Sube el/los documento(s) de la licitación",
    "upload_extracting_single": "Extrayendo texto...",
    "upload_extracting_multi": "Extrayendo texto de {n} archivos...",
    "upload_zip_not_ingested_reason": (
        "**No incorporado -- límite de la prueba.** La prueba gratuita analiza hasta "
        "{trial_limit} archivo(s) de brief/adenda por carga; este no se "
        "incluyó en el análisis. Las cuentas de pago llegan hasta {paid_limit}. "
        "Clasificación original: {original_reason}"
    ),
    "upload_zip_skipped_summary": (
        "{n} archivo(s) dentro de los paquetes subidos no se incorporaron -- "
        "la prueba gratuita analiza hasta {trial_limit} archivos de brief/adenda en total "
        "(consulta el desglose de abajo para saber cuáles). Las cuentas de pago llegan hasta {paid_limit}."
    ),
    "upload_no_brief_found_error": (
        "No se encontró ningún brief ni adenda en ese paquete (consulta el desglose de abajo "
        "para ver cómo se clasificó cada archivo). Sube el brief en sí -- como PDF/DOCX, "
        "o en otro ZIP -- para ejecutar el análisis."
    ),
    "upload_breakdown_expander": "Desglose del paquete de licitación -- cómo se clasificó cada archivo",
    "upload_col_file": "Archivo",
    "upload_col_filed_as": "Clasificado como",
    "upload_col_why_what_to_do": "Por qué / qué hacer",
    "upload_schedules_kept_aside_info": (
        "Se guardaron aparte {n} formulario(s) de retorno -- consulta la sección "
        "**Formularios de retorno** en la pestaña Exportar paquete para completarlos "
        "con los datos de este proyecto."
    ),
    "upload_drawings_set_aside_caption": "Se dejaron de lado {n} archivo(s) de planos/imágenes -- los planos no se usan en el análisis de texto.",
    "upload_unreadable_markdown": (
        "{n} archivo(s) no se pudieron leer -- cada fila de arriba indica por qué y cómo "
        "solucionarlo, o [envíanos el archivo por correo]({mailto}) y lo procesaremos por ti."
    ),
    "upload_ocr_warning": (
        "Partes de este brief se leyeron con reconocimiento de texto (OCR) a partir de páginas "
        "escaneadas. {ocr_tag}: verifica los números, las fechas "
        "y los nombres contra el documento original."
    ),
    "upload_brief_loaded_success": (
        "Brief de la licitación cargado -- {chars} caracteres{pages_part}. Se encontraron "
        "{headings} encabezado(s) candidato(s), {tables} tabla(s) y {annotations} anotación(es) existente(s)."
    ),
    "upload_brief_loaded_pages_part": " en {pages} páginas",
    "upload_clear_all_button": "Borrar todo",
    "upload_clear_tender_help": "Eliminar el/los documento(s) de licitación subido(s) y empezar de nuevo",
    "upload_retained_caption": "↩︎ Conservado de tu proyecto guardado (o de una carga anterior). Vuelve a subirlo solo si el brief ha cambiado.",
    "upload_annotations_expander": "Vista previa de {n} anotación(es) encontrada(s) en el/los PDF",
    "upload_annotation_highlight_only": "(solo resaltado)",
    "upload_company_material_heading": "**Material opcional de la empresa** -- sube tantos archivos como quieras por categoría. Varios archivos por categoría se combinan.",
    "upload_material_uploader_help": (
        "Subir archivos agrega/actualiza estos archivos; lo que ya está almacenado en esta "
        "categoría se conserva, no se reemplaza. Usa 'Borrar todo' abajo para vaciar la "
        "categoría y empezar de nuevo."
    ),
    "upload_material_limit_warning": (
        "El plan {tier} admite hasta {limit:,} {label} "
        "para este proyecto -- {existing} ya almacenado(s), así que "
        "{added_clause} y el resto quedó fuera: {dropped}."
    ),
    "upload_material_added_some": "se agregaron {kept} de los {total} archivo(s) recién seleccionado(s)",
    "upload_material_added_none": "no se agregó ninguno de los archivos recién seleccionados",
    "upload_extracting_category_spinner": "Extrayendo {label}...",
    "upload_prev_proposals_caption": (
        "📁 Para incorporar una propuesta que ya archivaste, usa el botón 'Agregar como "
        "referencia al proyecto' en la ventana emergente de la Biblioteca de propuestas "
        "(banner superior) en lugar de volver a subirla aquí."
    ),
    "upload_project_references_caption": (
        "📁 Para incorporar un proyecto de referencia de la firma que subiste a la Biblioteca "
        "de referencia de proyectos, usa su botón 'Agregar a referencias del proyecto' en el "
        "banner superior en lugar de volver a subirlo aquí."
    ),
    "upload_material_file_count_bit": "{n} archivo(s), ",
    "upload_material_stored_caption": "✅ {label}: {count_bit}{chars:,} caracteres almacenados.",
    "upload_clear_category_help": "Eliminar todo el material de {label} y empezar de nuevo",
    "upload_photos_label": "Fotos del proyecto",
    "upload_photos_loaded_caption": "✅ {n} foto(s) del proyecto cargada(s) -- la primera es la imagen de portada{retained}.",
    "upload_retained_suffix": " (conservada del proyecto guardado)",
    "upload_clear_photos_help": "Eliminar todas las fotos del proyecto y empezar de nuevo",
    "upload_branding_label": "Biblioteca de imágenes / marca de la empresa",
    "upload_branding_loaded_caption": "✅ {n} imagen(es) de marca cargada(s){retained}.",
    "upload_clear_branding_help": "Eliminar todas las imágenes de marca y empezar de nuevo",
    "upload_refprojects_heading": "#### Proyectos de referencia (sección de Experiencia relevante)",
    "upload_refprojects_caption": (
        "Redacta, luego revisa y edita, los proyectos pasados distintos que el paquete "
        "exportado mostrará en Experiencia relevante -- revisados para un tono consistente y "
        "relevancia para ESTA licitación, no el texto subido en bruto pegado tal cual. Agrega "
        "una foto por proyecto si tienes una, y confirma cuál de tu personal clave trabajó en "
        "cada uno -- eso alimenta automáticamente la tabla de referencias cruzadas entre la "
        "Sección 2 y la Sección 3. Es mejor hacerlo aquí, temprano, para que esté listo antes "
        "de exportar."
    ),
    "upload_refprojects_upload_first_info": "Sube material de 'Referencias de proyectos' arriba para redactar proyectos de referencia a partir de él, o agrega uno manualmente abajo.",
    "upload_refprojects_draft_hint_info": (
        "Material subido y leído. Haz clic en **Redactar proyectos de referencia a partir del "
        "material subido** abajo para que la IA lo convierta en las entradas de proyecto "
        "individuales que se muestran más abajo -- subir el material por sí solo aún no las crea."
    ),
    "upload_draft_refprojects_button": "Redactar proyectos de referencia a partir del material subido",
    "upload_draft_refprojects_help": "Sube material de 'Referencias de proyectos' arriba y {ai_hint}.",
    "upload_draft_refprojects_spinner": "Leyendo el material de referencia de proyectos y redactando entradas revisadas y orientadas a la relevancia...",
    "upload_refprojects_drafted_success": "Se redactaron {n} proyecto(s) de referencia. Revisa y edita cada campo abajo antes de exportar.",
    "upload_refprojects_no_analysis_info": "El Análisis de la licitación aún no se ha ejecutado -- vuelve a ejecutar esto una vez que lo hayas hecho, para que la relevancia pueda ajustarse al brief real.",
    "upload_refprojects_drafting_failed_error": "Falló la redacción del proyecto de referencia",
    "upload_refproject_untitled": "Proyecto de referencia {n}",
    "upload_ref_project_title_label": "Título del proyecto",
    "upload_ref_client_label": "Cliente",
    "upload_ref_description_label": "Descripción (revisada por consistencia/relevancia)",
    "upload_ref_relevance_label": "Relevancia para esta licitación",
    "upload_ref_personnel_label": "Personal clave que trabajó en este proyecto",
    "upload_ref_photo_label": "Foto del proyecto (opcional)",
    "upload_ref_remove_button": "Eliminar este proyecto de referencia",
    "upload_add_ref_manual_heading": "**Agregar un proyecto de referencia manualmente**",
    "upload_add_ref_button": "Agregar proyecto de referencia",

    # --- Pestaña 3: Análisis de la licitación (rezagos no cubiertos por el pase anterior de la Parte B2) ---
    "analysis_subheader": "Análisis de la licitación",
    "analysis_caption": "Extrae el alcance, los objetivos, los requisitos obligatorios, los criterios de evaluación, las ponderaciones, los límites de páginas, los entregables, los formularios y los riesgos del brief subido.",
    "analysis_need_project_name_info": "Ingresa un nombre de proyecto en la pestaña Configuración del proyecto antes de ejecutar el Análisis de la licitación.",
    "analysis_need_brief_and_ai_info": "Sube un brief de licitación (Subir documentos) y {ai_hint} para ejecutar el análisis.",
    "analysis_past_due_warning": (
        "Tu pago está pendiente, y también has usado las "
        "{limit} propuesta(s) incluidas de este ciclo. Actualiza tu método de pago para "
        "mantener tu suscripción activa, o compra una propuesta de pago por uso para continuar ahora mismo."
    ),
    "analysis_subscribed_limit_warning": (
        "Has usado las {limit} propuesta(s) incluidas en el ciclo de facturación "
        "de este plan Mensual. Compra una propuesta de pago por uso para continuar ahora, o espera la renovación."
    ),
    "analysis_trial_exhausted_warning": (
        "Has usado las {limit} propuesta(s) de la prueba gratuita. "
        "Mejora tu plan para continuar -- paga por propuesta, o suscríbete mensualmente. Consulta los precios en la página principal."
    ),
    "analysis_subscription_bids_caption": "Esto usará 1 de tus {remaining} propuesta(s) restante(s) en este ciclo de facturación.",
    "analysis_payg_caption": "Esto usará 1 crédito de propuesta de pago por uso (te quedan {credits}).",
    "analysis_trial_remaining_caption": "Esto usará tu propuesta de prueba gratuita ({remaining} restante(s)) -- asegúrate de que este sea el documento correcto primero.",
    "analysis_run_button": "Ejecutar Análisis de la licitación",
    "analysis_progress_text": "Analizando...",
    "analysis_progress_detail": "Analizando parte {done}/{total}...",
    "analysis_queued_text": "En cola para el análisis...",
    "analysis_complete_success": "Análisis de la licitación completo.",
    "analysis_failed_error": "Falló el análisis",
    "analysis_checkout_failed_error": "No se pudo iniciar el pago",
    "analysis_ocr_warning": (
        "Este análisis se basa en texto leído con OCR de páginas escaneadas. "
        "{ocr_tag}: verifica los requisitos, "
        "fechas y números extraídos contra el documento original."
    ),
    "analysis_project_scope_heading": "#### Alcance del proyecto",
    "analysis_client_objectives_heading": "#### Objetivos del cliente",
    "analysis_mandatory_requirements_heading": "#### Requisitos obligatorios",
    "analysis_deliverables_heading": "#### Entregables",
    "analysis_not_extracted": "_no extraído_",
    "analysis_none_extracted": "_ninguno extraído_",
    "analysis_submission_date_label": "**Fecha de presentación:** {text}",
    "analysis_total_page_limit_label": "**Límite total de páginas:** {text}",
    "analysis_fee_cap_label": "**Tope de honorarios:** {text}",
    "analysis_not_stated": "_no indicado_",
    "analysis_uses_named_criteria_label": "**Usa criterios de selección nombrados (estilo SC1/SC2):** {answer}",
    "analysis_yes": "Sí",
    "analysis_no": "No",
    "analysis_required_forms_heading": "#### Formularios / anexos requeridos",
    "analysis_evaluation_criteria_heading": "#### Criterios de evaluación / selección",
    "analysis_col_code": "Código",
    "analysis_col_name": "Nombre",
    "analysis_col_weighting": "Ponderación",
    "analysis_mandatory_gate": "Filtro obligatorio",
    "analysis_col_page_limit": "Límite de páginas",
    "analysis_col_format_rules": "Reglas de formato",
    "analysis_no_evaluation_criteria": "_No se extrajeron criterios de evaluación._",
    "analysis_flagged_items_heading": "#### Elementos que marcaste mediante anotaciones",
    "analysis_risks_heading": "#### Riesgos indicados en el brief",
    "analysis_extraction_warnings_prefix": "Advertencias de extracción -- verifícalas manualmente contra el brief:\n\n",

    # Part A2 -- Export Pack tab (80_export.py)
    "export_subheader": "Exportar paquete",
    "export_continue_to_payment_button": "Continuar al pago",
    "export_readiness_expander": "⚠️ {n} cosa(s) aún pendiente(s) antes de que este paquete esté listo",
    "export_readiness_item": "- **{label}** -- ve a *{where}*",
    "export_readiness_caption": (
        "Puedes exportar de todos modos -- todo lo pendiente se muestra como un marcador de "
        "posición rojo en el documento, así que nada falta en silencio."
    ),
    "export_readiness_all_done_success": "Todo lo que necesita este paquete ya se ha completado.",
    "export_letter_intro_caption": "Genera la primera versión del Paquete de Respuesta a la Propuesta de alcance reducido. Revisa la lista de verificación dentro antes de que esto se acerque a un envío real.",
    "export_generate_structure_first_info": "Genera primero la Estructura de la propuesta.",
    "export_letter_structure_stale_warning": (
        "El formato de la propuesta (Configuración del proyecto) se cambió después de generar "
        "estas secciones -- ve a Estructura y haz clic en **Generar estructura de la "
        "propuesta** de nuevo primero, o al paquete exportado le faltarán los borradores de "
        "Introducción/Metodología aunque ya hayas ejecutado la redacción."
    ),
    "export_generate_letter_docx_button": "Generar DOCX del paquete de alcance reducido",
    "export_assembling_spinner": "Ensamblando el documento...",
    "export_document_generated_success": "Documento generado.",
    "export_formal_intro_caption": "Genera la primera versión del paquete de respuesta DOCX. Revisa la lista de verificación dentro del documento antes de que esto se acerque a un envío real.",
    "export_formal_generate_structure_first_info": "Genera primero la Estructura de la propuesta. Los borradores, gráficos y la estimación de honorarios son opcionales pero recomendados antes de exportar.",
    "export_formal_structure_stale_warning": (
        "El formato de la propuesta (Configuración del proyecto) se cambió después de generar "
        "estas secciones -- ve a Estructura y haz clic en **Generar estructura de la "
        "propuesta** de nuevo primero, o el paquete exportado podría no coincidir con lo que redactaste."
    ),
    "export_generate_docx_button": "Generar DOCX",
    "export_stale_files_warning": (
        "**Estos archivos se generaron antes de tus últimas ediciones.** Descargarlos ahora te "
        "da el paquete anterior. Genera de nuevo para incorporar los cambios."
    ),
    "export_download_docx_button": "Descargar DOCX",
    "export_download_orgchart_button": "Descargar organigrama (PPTX)",
    "export_orgchart_caption": (
        "Construido a partir del plan de recursos de este proyecto -- el líder de cada "
        "disciplina más cualquiera agregado bajo ellos, con \"TBC\" en rojo para roles sin "
        "asignar y [CONFIRMAR TÍTULO] donde un integrante de apoyo aún no tiene título. El PM "
        "propio del cliente y las firmas subconsultoras no se muestran -- la app no tiene datos "
        "de ellos. Completa los espacios en blanco y luego pega el organigrama terminado sobre "
        "la imagen de primera versión en el DOCX."
    ),
    "export_orgchart_build_failed_caption": "No se pudo construir el organigrama en este momento -- la descarga del DOCX de arriba no se ve afectada.",
    "export_download_methodology_button": "Descargar tabla de metodología (PPTX)",
    "export_methodology_caption_has_stages": (
        "Construida a partir de las etapas de diseño que revisaste en el paso Redactar "
        "respuestas -- cada columna es contenido real, con TBC en rojo donde el brief no "
        "respaldaba una celda. Sin una cuadrícula revisada, recurre al diseño genérico de "
        "cuatro etapas. Pega la tabla terminada en la propuesta donde la nota de marcador de "
        "posición rojo marca su lugar."
    ),
    "export_methodology_caption_no_stages": (
        "Aún no se han revisado etapas de diseño, así que esto es el reemplazo genérico de "
        "cuatro etapas: la columna 2 proviene de tus elementos de alcance reales, el resto son "
        "marcadores de posición rojos. Ejecuta **Redactar etapas de metodología** en el paso "
        "Redactar respuestas para completar las cuatro columnas."
    ),
    "export_methodology_build_failed_caption": "No se pudo construir la tabla de metodología en este momento -- la descarga del DOCX de arriba no se ve afectada.",
    "export_download_program_button": "Descargar programa (PPTX)",
    "export_program_caption": (
        "Construido a partir del programa de ejecución ingresado en la pestaña Estimación de "
        "honorarios -- muestra un marcador de posición rojo si aún no se ha generado un "
        "programa ahí."
    ),
    "export_program_build_failed_caption": "No se pudo construir el programa en este momento -- la descarga del DOCX de arriba no se ve afectada.",
    "export_download_tendersummary_button": "Descargar Resumen de la licitación (DOCX)",
    "export_tendersummary_caption": (
        "Documento interno complementario -- orientación sobre los requisitos principales del "
        "brief, más la matriz de cumplimiento, el análisis de brechas, la lista de "
        "verificación y la lista de aportes del usuario donde se generaron. No forma parte de "
        "la propuesta en sí."
    ),
    "export_tendersummary_pending_caption": "El documento Resumen de la licitación se generará junto con el DOCX de arriba.",
    "export_library_heading": "#### Biblioteca de propuestas",
    "export_library_caption": (
        "Archiva esta propuesta generada en la Biblioteca de propuestas "
        "(library/{project_type}/) para reutilizarla más tarde -- "
        "como referencia de 'Propuestas anteriores' en Subir documentos, o para explorarla y "
        "descargarla desde el botón 'Biblioteca de propuestas' en el banner superior. Nada se "
        "archiva automáticamente; haz clic abajo cuando estés conforme con esta versión. Solo "
        "se archiva el DOCX de la propuesta en sí, no el Resumen de la licitación ni los "
        "complementos de PowerPoint de arriba."
    ),
    "export_library_project_type_placeholder": "<tipo de proyecto>",
    "export_archive_button": "Archivar en la biblioteca",
    "export_archive_success": "Archivado en la biblioteca bajo '{project_type}' como {filename}.",
    "export_archive_failed_error": "No se pudo archivar en la biblioteca",
    "export_schedules_heading": "#### Formularios de retorno",
    "export_schedules_caption": (
        "Completa los propios formularios de respuesta del cliente con los datos de este "
        "proyecto -- datos de la empresa y contacto, personal clave, proyectos de referencia, "
        "desglose de honorarios -- dentro de su documento original, con el formato intacto. "
        "Todo lo que el proyecto realmente no sabe se deja como un marcador de posición "
        "claramente indicado **{placeholder_prefix}: ...]**, nunca una suposición. Los "
        "formularios encontrados en un ZIP de paquete de licitación subido aparecen aquí "
        "automáticamente; también puedes subir más abajo."
    ),
    "export_add_schedules_label": "Agregar formularios para completar (DOCX o XLSX)",
    "export_schedule_not_form_info": (
        "'{name}' no parece un formulario de respuesta (sus tablas ya están completas, o no "
        "tiene ninguna) -- de todos modos se intentará, pero revisa el resultado con cuidado."
    ),
    "export_no_schedules_caption": "Aún no hay formularios -- sube un ZIP de paquete de licitación en Subir documentos, o agrega archivos arriba.",
    "export_schedules_ready_prefix": "**{n} formulario(s) listo(s):** ",
    "export_remove_file_label": "Eliminar un archivo",
    "export_keep_all_option": "(conservar todos)",
    "export_remove_button": "Eliminar",
    "export_fill_schedules_button": "Completar formularios con los datos de este proyecto",
    "export_filling_spinner": "Completando {n} formulario(s)...",
    "export_download_filled_button": "Descargar copia completada",
    "export_schedule_fill_summary_caption": (
        "{filled} campo(s) completado(s) con datos del proyecto, "
        "{placeholdered} dejado(s) como marcadores de posición claramente indicados para "
        "completar. Revisa todo antes de enviarlo -- esto es una primera versión, y los "
        "marcadores de posición son deliberados: el proyecto no conoce esas respuestas."
    ),
    "export_schedule_detail_expander": "Qué se completó / se dejó como marcador de posición en {filename}",
    "export_filled_heading": "**Completado con datos del proyecto:**",
    "export_col_where": "Dónde",
    "export_col_field": "Campo",
    "export_col_value": "Valor",
    "export_placeholdered_heading": "**Dejado como marcador de posición (completar antes de enviar):**",

    # Part A2 -- limits.py (function-returned strings; module-level string
    # constants themselves stay hardcoded English -- see the TODO comments
    # next to each in limits.py)
    "limits_upgrade_clause": "Las cuentas de pago llegan hasta {paid_limit:,} {label}.",
    "limits_tier_paid": "de pago",
    "limits_tier_trial": "de prueba gratuita",
    "limits_count_limit_message": (
        "El plan {tier} admite hasta {limit:,} {label} a la vez -- hemos usado los primeros "
        "{limit:,} y dejado fuera: {shown}."
    ),
    "limits_tender_page_cap_message": (
        "Este brief tiene alrededor de {page_count:,} páginas, y la prueba gratuita analiza "
        "hasta {trial_limit:,}. Recorta el paquete a lo esencial (las condiciones estándar del "
        "contrato y textos similares generalmente se pueden quitar sin problema), o mejora a "
        "un plan de pago (hasta {paid_limit:,} páginas) para ejecutar este brief tal cual."
    ),
    "limits_trial_spend_ceiling_message": "Se agotó el límite de IA de tu prueba gratuita -- mejora tu plan para continuar; tu trabajo está guardado.",
    "limits_ai_rate_limit_trial": "Espera unos minutos -- la prueba tiene un límite de velocidad de uso razonable.",
    "limits_ai_rate_limit_paid": "Espera unos minutos -- hay un breve límite de velocidad de uso razonable.",

    # Part A3 -- pestaña Configuración del proyecto, selector de output_language
    # (idioma del contenido GENERADO por IA, independiente del idioma de la
    # interfaz de la propia app)
    "setup_output_language_label": "Idioma del contenido generado",
    "setup_output_language_help": (
        "Idioma en el que se redacta el contenido de la propuesta generado por IA "
        "(borradores, resumen ejecutivo y secciones similares) -- esto no cambia el "
        "idioma de la propia interfaz de la app, que es el selector aparte en la barra "
        "lateral."
    ),
}
