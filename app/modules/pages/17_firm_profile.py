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
        st.error(
            "**Couldn't open your firm profile just now.** Nothing has been lost -- your "
            "profile is stored separately from your projects. Try again in a moment, and if it "
            "keeps happening email hello@civilproposals.com."
        )
        if st.button("← Back to the app", key="_firm_exit_error"):
            _exit_firm_profile()
            st.rerun()
        st.stop()

    _hl, _hr = st.columns([4, 1])
    with _hl:
        st.title("🏢 Firm profile")
        st.caption(
            "Your firm's standing facts, entered once and reused on every bid. Everything "
            "here fills in placeholders that would otherwise be red in every exported pack "
            "-- the ABN and address in the footer, the logo on the cover, the insurance and "
            "certification rows on a client's returnable schedules. Anything you leave blank "
            "keeps showing its placeholder, exactly as it does today: nothing here is ever "
            "guessed or filled in for you."
        )
    with _hr:
        st.write("")
        if st.button("← Back to the app", use_container_width=True, key="_firm_exit"):
            _exit_firm_profile()
            st.rerun()

    _tab_identity, _tab_insurance, _tab_commercial, _tab_narrative = st.tabs(
        ["🏢 Identity", "🛡️ Insurance & certifications", "💲 Commercial", "📝 Standing text"]
    )

    # -----------------------------------------------------------------
    # Identity
    # -----------------------------------------------------------------
    with _tab_identity:
        _c1, _c2 = st.columns(2)
        with _c1:
            _company_name = st.text_input("Legal entity name", value=_profile.company_name or "",
                                          key="_fp_company_name",
                                          placeholder="e.g. Example Engineering Pty Ltd")
            _abn = st.text_input("ABN", value=_profile.abn or "", key="_fp_abn",
                                 placeholder="12 345 678 901")
            _acn = st.text_input("ACN (optional)", value=_profile.acn or "", key="_fp_acn")
        with _c2:
            _registered_address = st.text_area(
                "Registered address", value=_profile.registered_address or "",
                key="_fp_address", height=100,
                placeholder="Level 3, 100 Example St\nBrisbane QLD 4000",
            )

        st.markdown("**Company logo**")
        st.caption(
            "Rendered on the cover page of every pack. Without one the cover keeps its red "
            "[COMPANY LOGO] box."
        )
        if _profile.logo_bytes:
            _lc1, _lc2 = st.columns([1, 3])
            with _lc1:
                try:
                    st.image(_profile.logo_bytes, width=180)
                except Exception:
                    st.caption("(the stored logo couldn't be displayed -- upload it again)")
            with _lc2:
                st.caption(f"Current: {_profile.logo_filename or 'uploaded logo'}")
                if st.button("Remove logo", key="_fp_logo_remove"):
                    firm_profile.save_profile(_profile_user_id, logo_bytes=None, logo_filename="")
                    st.rerun()
        _logo_upload = st.file_uploader("Upload a logo (PNG or JPG)", type=["png", "jpg", "jpeg"],
                                        key="_fp_logo_upload")

        st.divider()
        st.markdown("**Standard signatory**")
        st.caption(
            "Seeded into each new project's sign-off and contact details. You can still "
            "override it per bid -- seeding only ever fills a field that is empty."
        )
        _s1, _s2 = st.columns(2)
        with _s1:
            _signatory_name = st.text_input("Name", value=_profile.signatory_name or "", key="_fp_sig_name")
            _signatory_title = st.text_input("Title", value=_profile.signatory_title or "", key="_fp_sig_title")
        with _s2:
            _signatory_phone = st.text_input("Phone", value=_profile.signatory_phone or "", key="_fp_sig_phone")
            _signatory_email = st.text_input("Email", value=_profile.signatory_email or "", key="_fp_sig_email")

    # -----------------------------------------------------------------
    # Insurance & certifications
    # -----------------------------------------------------------------
    with _tab_insurance:
        st.caption(
            "These answer the insurance and certification labels on a client's returnable "
            "schedules, and the matching rows of the compliance matrix. A blank row is "
            "ignored, not exported as an empty insurance."
        )
        _existing = {row["type"]: row for row in firm_profile.insurances(_profile)}
        _insurance_rows = []
        for _kind in firm_profile.INSURANCE_TYPES:
            _row = _existing.get(_kind, {})
            with st.expander(_kind, expanded=bool(_row)):
                _i1, _i2 = st.columns(2)
                with _i1:
                    _insurer = st.text_input("Insurer", value=_row.get("insurer", ""), key=f"_fp_ins_{_kind}_insurer")
                    _policy = st.text_input("Policy number", value=_row.get("policy_no", ""), key=f"_fp_ins_{_kind}_policy")
                with _i2:
                    _cover = st.text_input("Cover / limit", value=_row.get("cover", ""),
                                           key=f"_fp_ins_{_kind}_cover", placeholder="e.g. $10,000,000")
                    _expiry = st.text_input("Expiry", value=_row.get("expiry", ""),
                                            key=f"_fp_ins_{_kind}_expiry", placeholder="e.g. 30 June 2027")
            _insurance_rows.append({
                "type": _kind, "insurer": _insurer, "policy_no": _policy,
                "cover": _cover, "expiry": _expiry,
            })

        st.markdown("**Certifications**")
        _certifications_text = st.text_area(
            "One per line", value="\n".join(firm_profile.certifications(_profile)),
            key="_fp_certs", height=100,
            placeholder="ISO 9001:2015 Quality Management\nISO 45001:2018 Occupational Health & Safety",
        )

    # -----------------------------------------------------------------
    # Commercial
    # -----------------------------------------------------------------
    with _tab_commercial:
        st.caption(
            "Your standard charge-out rates, used to seed a new project's fee build-up. "
            "Hours always stay yours to enter -- only the rate is carried over."
        )
        _rate_rows = [{"Discipline": d, "Rate ($/hr)": r}
                      for d, r in sorted(firm_profile.rate_card(_profile).items())]
        if not _rate_rows:
            _rate_rows = [{"Discipline": "", "Rate ($/hr)": 0.0}]
        _edited_rates = st.data_editor(
            _rate_rows, key="_fp_rates", num_rows="dynamic", use_container_width=True,
            column_config={
                "Discipline": st.column_config.TextColumn("Discipline"),
                "Rate ($/hr)": st.column_config.NumberColumn("Rate ($/hr)", min_value=0.0, step=5.0),
            },
        )

    # -----------------------------------------------------------------
    # Standing text
    # -----------------------------------------------------------------
    with _tab_narrative:
        st.caption(
            "Standing narrative reused across bids. Each of these replaces a red placeholder "
            "in the exported pack when filled in, and leaves it exactly as it is when blank."
        )
        _offices_text = st.text_area(
            "Offices and local presence", value=_profile.offices_text or "", key="_fp_offices",
            height=110,
            placeholder="Where your offices are and how long you've been in the region -- "
                        "fills the Local Content section's placeholders.",
        )
        _community_text = st.text_area(
            "Community and reinvestment programs", value=_profile.community_text or "",
            key="_fp_community", height=110,
        )
        _leadership_text = st.text_area(
            "Standing leadership team", value=_profile.leadership_text or "", key="_fp_leadership",
            height=90,
            placeholder="Names and roles of the leadership who oversee delivery -- used in "
                        "the relationship-management section.",
        )
        _terms_text = st.text_area(
            "Standard terms of engagement", value=_profile.terms_of_engagement_text or "",
            key="_fp_terms", height=110,
            placeholder="e.g. This offer is made under AS 4122-2010 General Conditions of "
                        "Contract for Consultants.",
        )
        _qa_statement = st.text_area(
            "QA / Work Verification statement", value=_profile.qa_statement or "",
            key="_fp_qa", height=80,
            placeholder="e.g. All design deliverables are issued with completed Work "
                        "Verification Records (WVRs).",
        )

    # -----------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------
    st.divider()
    if st.button("Save firm profile", type="primary", key="_fp_save"):
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
            st.success("Firm profile saved. New projects will start from it.")
        except Exception as exc:  # noqa: BLE001 -- never show a stack trace mid-bid
            st.error(
                f"**Couldn't save the firm profile.** {exc} Nothing was changed -- try again, "
                "and if it keeps failing email hello@civilproposals.com."
            )

    st.stop()
