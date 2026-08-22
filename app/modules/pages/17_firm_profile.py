"""
modules/pages/17_firm_profile.py

The Firm Profile editor. Runs as an ordered page segment (see app.py's
docstring -- these files are exec'd in one shared namespace, they are NOT
importable modules), positioned after 15_admin_blog.py and BEFORE
20_chrome.py.

Why before the chrome, exactly like the blog editor: when firm-profile mode
is active this segment renders full-width and then st.stop()s, so the
sidebar and the ten workflow tabs never get built. Sitting after
20_chrome.py would leave an empty tab bar stranded above the editor.

Unlike the blog editor, this is NOT admin-gated. Every account has its own
firm profile -- it is the firm's own standing facts, and it is what stops
the same ABN, insurances, logo and signatory being re-typed (or left as red
placeholders) on every single bid.
"""

import sys

import streamlit as st

from modules import firm_profile

# ---------------------------------------------------------------------------
# Entry / exit
# ---------------------------------------------------------------------------

if st.query_params.get("page") == "firm":
    st.session_state._firm_profile_mode = True

if st.session_state.get("_firm_profile_mode"):

    def _exit_firm_profile() -> None:
        st.session_state._firm_profile_mode = False
        try:
            if "page" in st.query_params:
                del st.query_params["page"]
        except Exception:
            pass

    _profile_user_id = current_user.id if (IS_SAAS_MODE and current_user) else None  # noqa: F821
    try:
        _profile = firm_profile.get_or_create(_profile_user_id)
    except Exception as exc:  # noqa: BLE001
        # The one unguarded database call on this page. A user mid-bid must
        # never see a traceback -- and this page is optional, so failing it
        # cleanly costs them nothing except this screen.
        print(f"[firm profile] {exc}", file=sys.stderr)
        st.error(i18n.t("firmprofile_load_failed_error"))  # noqa: F821
        if st.button(i18n.t("firmprofile_back_to_app_button"), key="_firm_exit_error"):  # noqa: F821
            _exit_firm_profile()
            st.rerun()
        st.stop()

    _hl, _hr = st.columns([4, 1])
    with _hl:
        st.title(i18n.t("firmprofile_title"))
        st.caption(i18n.t("firmprofile_intro_caption"))
    with _hr:
        st.write("")
        if st.button(i18n.t("firmprofile_back_to_app_button"), use_container_width=True, key="_firm_exit"):
            _exit_firm_profile()
            st.rerun()

    _tab_identity, _tab_insurance, _tab_commercial, _tab_narrative = st.tabs([
        i18n.t("firmprofile_tab_identity"), i18n.t("firmprofile_tab_insurance"),
        i18n.t("firmprofile_tab_commercial"), i18n.t("firmprofile_tab_narrative"),
    ])

    # -----------------------------------------------------------------
    # Identity
    # -----------------------------------------------------------------
    with _tab_identity:
        _c1, _c2 = st.columns(2)
        with _c1:
            _company_name = st.text_input(i18n.t("firmprofile_legal_entity_name_label"), value=_profile.company_name or "",
                                          key="_fp_company_name",
                                          placeholder=i18n.t("firmprofile_legal_entity_name_placeholder"))
            _abn = st.text_input(i18n.t("firmprofile_abn_label"), value=_profile.abn or "", key="_fp_abn",
                                 placeholder="12 345 678 901")
            _acn = st.text_input(i18n.t("firmprofile_acn_label"), value=_profile.acn or "", key="_fp_acn")
        with _c2:
            _registered_address = st.text_area(
                i18n.t("firmprofile_registered_address_label"), value=_profile.registered_address or "",
                key="_fp_address", height=100,
                placeholder="Level 3, 100 Example St\nBrisbane QLD 4000",
            )

        st.markdown(i18n.t("firmprofile_company_logo_heading"))
        st.caption(i18n.t("firmprofile_company_logo_caption"))
        if _profile.logo_bytes:
            _lc1, _lc2 = st.columns([1, 3])
            with _lc1:
                try:
                    st.image(_profile.logo_bytes, width=180)
                except Exception:
                    st.caption(i18n.t("firmprofile_logo_display_failed_caption"))
            with _lc2:
                st.caption(i18n.t("firmprofile_current_logo_caption", filename=_profile.logo_filename or i18n.t("firmprofile_uploaded_logo_fallback")))
                if st.button(i18n.t("firmprofile_remove_logo_button"), key="_fp_logo_remove"):
                    firm_profile.save_profile(_profile_user_id, logo_bytes=None, logo_filename="")
                    st.rerun()
        _logo_upload = st.file_uploader(i18n.t("firmprofile_upload_logo_label"), type=["png", "jpg", "jpeg"],
                                        key="_fp_logo_upload")

        st.divider()
        st.markdown(i18n.t("firmprofile_signatory_heading"))
        st.caption(i18n.t("firmprofile_signatory_caption"))
        _s1, _s2 = st.columns(2)
        with _s1:
            _signatory_name = st.text_input(i18n.t("firmprofile_name_label"), value=_profile.signatory_name or "", key="_fp_sig_name")
            _signatory_title = st.text_input(i18n.t("firmprofile_title_label"), value=_profile.signatory_title or "", key="_fp_sig_title")
        with _s2:
            _signatory_phone = st.text_input(i18n.t("firmprofile_phone_label"), value=_profile.signatory_phone or "", key="_fp_sig_phone")
            _signatory_email = st.text_input(i18n.t("firmprofile_email_label"), value=_profile.signatory_email or "", key="_fp_sig_email")

    # -----------------------------------------------------------------
    # Insurance & certifications
    # -----------------------------------------------------------------
    with _tab_insurance:
        st.caption(i18n.t("firmprofile_insurance_caption"))
        _existing = {row["type"]: row for row in firm_profile.insurances(_profile)}
        _insurance_rows = []
        for _kind in firm_profile.INSURANCE_TYPES:
            _row = _existing.get(_kind, {})
            with st.expander(_kind, expanded=bool(_row)):
                _i1, _i2 = st.columns(2)
                with _i1:
                    _insurer = st.text_input(i18n.t("firmprofile_insurer_label"), value=_row.get("insurer", ""), key=f"_fp_ins_{_kind}_insurer")
                    _policy = st.text_input(i18n.t("firmprofile_policy_number_label"), value=_row.get("policy_no", ""), key=f"_fp_ins_{_kind}_policy")
                with _i2:
                    _cover = st.text_input(i18n.t("firmprofile_cover_limit_label"), value=_row.get("cover", ""),
                                           key=f"_fp_ins_{_kind}_cover", placeholder=i18n.t("firmprofile_cover_placeholder"))
                    _expiry = st.text_input(i18n.t("firmprofile_expiry_label"), value=_row.get("expiry", ""),
                                            key=f"_fp_ins_{_kind}_expiry", placeholder=i18n.t("firmprofile_expiry_placeholder"))
            _insurance_rows.append({
                "type": _kind, "insurer": _insurer, "policy_no": _policy,
                "cover": _cover, "expiry": _expiry,
            })

        st.markdown(i18n.t("firmprofile_certifications_heading"))
        _certifications_text = st.text_area(
            i18n.t("firmprofile_one_per_line_label"), value="\n".join(firm_profile.certifications(_profile)),
            key="_fp_certs", height=100,
            placeholder="ISO 9001:2015 Quality Management\nISO 45001:2018 Occupational Health & Safety",
        )

    # -----------------------------------------------------------------
    # Commercial
    # -----------------------------------------------------------------
    with _tab_commercial:
        st.caption(i18n.t("firmprofile_commercial_caption"))
        _rate_rows = [{"Discipline": d, "Rate ($/hr)": r}
                      for d, r in sorted(firm_profile.rate_card(_profile).items())]
        if not _rate_rows:
            _rate_rows = [{"Discipline": "", "Rate ($/hr)": 0.0}]
        _edited_rates = st.data_editor(
            _rate_rows, key="_fp_rates", num_rows="dynamic", use_container_width=True,
            column_config={
                "Discipline": st.column_config.TextColumn(i18n.t("firmprofile_discipline_column")),
                "Rate ($/hr)": st.column_config.NumberColumn(i18n.t("firmprofile_rate_column"), min_value=0.0, step=5.0),
            },
        )

    # -----------------------------------------------------------------
    # Standing text
    # -----------------------------------------------------------------
    with _tab_narrative:
        st.caption(i18n.t("firmprofile_narrative_caption"))
        _offices_text = st.text_area(
            i18n.t("firmprofile_offices_label"), value=_profile.offices_text or "", key="_fp_offices",
            height=110,
            placeholder=i18n.t("firmprofile_offices_placeholder"),
        )
        _community_text = st.text_area(
            i18n.t("firmprofile_community_label"), value=_profile.community_text or "",
            key="_fp_community", height=110,
        )
        _leadership_text = st.text_area(
            i18n.t("firmprofile_leadership_label"), value=_profile.leadership_text or "", key="_fp_leadership",
            height=90,
            placeholder=i18n.t("firmprofile_leadership_placeholder"),
        )
        _terms_text = st.text_area(
            i18n.t("firmprofile_terms_label"), value=_profile.terms_of_engagement_text or "",
            key="_fp_terms", height=110,
            placeholder=i18n.t("firmprofile_terms_placeholder"),
        )
        _qa_statement = st.text_area(
            i18n.t("firmprofile_qa_label"), value=_profile.qa_statement or "",
            key="_fp_qa", height=80,
            placeholder=i18n.t("firmprofile_qa_placeholder"),
        )

    # -----------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------
    st.divider()
    if st.button(i18n.t("firmprofile_save_button"), type="primary", key="_fp_save"):
        _fields = dict(
            company_name=_company_name.strip(),
            abn=_abn.strip(),
            acn=_acn.strip(),
            registered_address=_registered_address.strip(),
            signatory_name=_signatory_name.strip(),
            signatory_title=_signatory_title.strip(),
            signatory_phone=_signatory_phone.strip(),
            signatory_email=_signatory_email.strip(),
            insurances_json=firm_profile.dumps_insurances(_insurance_rows),
            certifications_json=firm_profile.dumps_certifications(_certifications_text.split("\n")),
            rate_card_json=firm_profile.dumps_rate_card({
                (row.get("Discipline") or "").strip(): row.get("Rate ($/hr)") or 0
                for row in _edited_rates
                if (row.get("Discipline") or "").strip() and (row.get("Rate ($/hr)") or 0) > 0
            }),
            offices_text=_offices_text.strip(),
            community_text=_community_text.strip(),
            leadership_text=_leadership_text.strip(),
            terms_of_engagement_text=_terms_text.strip(),
            qa_statement=_qa_statement.strip(),
        )
        if _logo_upload is not None:
            _fields["logo_bytes"] = _logo_upload.getvalue()
            _fields["logo_filename"] = _logo_upload.name
        try:
            firm_profile.save_profile(_profile_user_id, **_fields)
            # The fee tab caches the rate card for the session (it reads it on
            # every rerun); drop the cache so an edited rate takes effect now
            # rather than at the next login.
            st.session_state.pop("_firm_rate_card_cache", None)
            st.success(i18n.t("firmprofile_save_success"))
        except Exception as exc:  # noqa: BLE001 -- never show a stack trace mid-bid
            st.error(i18n.t("firmprofile_save_failed_error", exc=exc))

    st.stop()
