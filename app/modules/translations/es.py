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

    "bid_includes_popover_title": "Qué incluye una propuesta",
    "bid_includes_popover_body": (
        "Una sola propuesta de $50 cubre **un proyecto** (identificado por el nombre del proyecto, el "
        "nombre de la licitación, el nombre del cliente y el brief subido, en conjunto) con **5 pasadas "
        "de generación** y **descargas ilimitadas** de tus documentos actuales. Se consume una pasada al "
        "ejecutar el Análisis de la licitación, o al regenerar después de cambiar una entrada -- volver a "
        "descargar los mismos documentos sin cambios nunca consume una pasada. Renombrar un proyecto, o "
        "cambiar el brief, crea una nueva identidad de facturación -- tu análisis pagado permanece "
        "vinculado a la identidad anterior."
    ),
    "rename_confirm_title": "¿Renombrar este proyecto?",
    "rename_confirm_body": (
        "Renombrar cambia la identidad de este proyecto -- tu análisis pagado permanece con el nombre "
        "anterior. ¿Continuar?"
    ),
    "rename_confirm_yes": "Sí, renombrar",
    "rename_confirm_cancel": "Cancelar",
}
