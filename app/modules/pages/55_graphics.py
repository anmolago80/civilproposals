# modules/pages/55_graphics.py -- one segment of the CivilProposals app script.
# Tab 7 Graphics & Design.
#
# HOW THIS FILE RUNS: app.py executes the files in modules/pages/ in order,
# in ONE shared script namespace (see app.py's loader) -- exactly as when
# all of this was a single 315KB app.py, just split along its natural seams
# so each area of the app lives in its own reviewable file. Code here is
# UNCHANGED from the pre-split app.py; names defined in earlier segments
# (helpers, current_user, _access, the tabs list) are used directly, and
# st.session_state remains the single shared state, same as before.
# Deliberately NOT a function-per-page refactor: that would change scoping
# and evaluation order (the thing a mid-tender regression hides in), and is
# better done tab-by-tab with live click-through testing.
from __future__ import annotations
# ---------------------------------------------------------------------------
# Tab 7: Graphics & Design
# ---------------------------------------------------------------------------

with tabs[6]:
    if _is_letter():
        st.subheader(i18n.t("graphics_project_team_subheader"))
        st.caption(i18n.t("graphics_project_team_caption"))
        entries = resourcing.letter_team_entries(st.session_state.resource_plan)
        if not entries:
            st.info(i18n.t("graphics_project_team_empty_info"))
        else:
            for entry in entries:
                marker = "↳ " if entry["indent"] else ""
                name = entry["name"] or i18n.t("graphics_not_assigned")
                st.markdown(f"{marker}**{name}** -- {entry['role_label']}")
    else:
        st.subheader(i18n.t("graphics_subheader"))
        st.caption(i18n.t("graphics_caption"))

    ready = st.session_state.sections is not None
    if not ready:
        st.info(i18n.t("graphics_need_structure_info"))
    elif _is_letter():
        pass  # Project Team preview above already covers this pack size -- nothing else to render here.
    else:
        _ensure_divider_config(st.session_state.sections)
        photos = st.session_state.project_photo_bytes
        theme_name = st.session_state.proposal_theme

        st.markdown(i18n.t("graphics_quotes_heading"))
        st.caption(i18n.t("graphics_quotes_caption"))
        with st.form("add_quote_form", clear_on_submit=True):
            qcol1, qcol2 = st.columns(2)
            with qcol1:
                q_text = st.text_area(i18n.t("graphics_quote_label"), placeholder=i18n.t("graphics_quote_placeholder"), height=80)
            with qcol2:
                q_attr = st.text_input(i18n.t("graphics_quote_attributed_label"), placeholder=i18n.t("graphics_quote_attributed_placeholder"))
                q_project = st.text_input(i18n.t("graphics_quote_project_label"), placeholder=i18n.t("graphics_quote_project_placeholder"))
            if st.form_submit_button(i18n.t("graphics_add_quote_button"), type="primary") and q_text.strip():
                st.session_state.quotes.append({"text": q_text.strip(), "attribution": q_attr.strip(), "project": q_project.strip()})

        if st.session_state.quotes:
            for i, q in enumerate(st.session_state.quotes):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"_{q['text']}_ — **{q['attribution'] or i18n.t('graphics_unattributed')}**" + (f" ({q['project']})" if q['project'] else ""))
                with col2:
                    if st.button(i18n.t("graphics_remove_button"), key=f"remove_quote_{i}", type="primary"):
                        st.session_state.quotes.pop(i)
                        st.rerun()

        st.divider()
        st.markdown(i18n.t("graphics_photos_heading"))
        if photos:
            # Thumbnails, because "Photo 1 / Photo 2 / Photo 3" in a dropdown
            # asks the user to remember which upload was which -- and the one
            # that ends up on the cover is the single most visible image in
            # the whole pack.
            st.caption(i18n.t("graphics_photos_caption"))
            _cover_index = st.session_state.get("cover_photo_index") or 0
            if _cover_index >= len(photos):
                _cover_index = 0
            _photo_cols = st.columns(min(4, len(photos)))
            for _i, _photo in enumerate(photos):
                with _photo_cols[_i % len(_photo_cols)]:
                    try:
                        st.image(_photo, use_container_width=True)
                    except Exception:
                        st.caption(i18n.t("graphics_photo_preview_failed", n=_i + 1))
                    if _i == _cover_index:
                        st.caption(i18n.t("graphics_on_cover_caption"))
                    elif st.button(i18n.t("graphics_use_as_cover_button"), key=f"_cover_pick_{_i}", use_container_width=True):
                        st.session_state.cover_photo_index = _i
                        # The cover image is baked into the generated pack, so
                        # a previously-generated DOCX no longer matches.
                        st.session_state.docx_buffer = None
                        st.rerun()
            st.session_state.cover_photo_index = _cover_index

        st.divider()
        st.markdown(i18n.t("graphics_divider_heading"))
        if not photos:
            st.info(i18n.t("graphics_no_photos_info"))

        # TODO A2 i18n: layout names below are functional values consumed
        # verbatim by divider_designer.py (DIVIDER_LAYOUTS / string equality
        # checks there) -- out of scope to translate without editing that
        # module too, so the layout *options* stay in English while the
        # surrounding UI text above is translated.
        available_layouts = ["Solid colour"] + (["Photo + gradient", "Photo + quote", "Split (colour + photo)"] if photos else [])
        config = st.session_state.section_divider_config

        _none_option = i18n.t("graphics_none_option")
        for section in st.session_state.sections:
            cfg = config[section.title]
            with st.expander(f"{section.section_number}. {section.title}"):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    layout = st.selectbox(
                        i18n.t("graphics_layout_label"), available_layouts,
                        index=available_layouts.index(cfg["layout"]) if cfg["layout"] in available_layouts else 0,
                        key=f"layout_{section.title}",
                    )
                with c2:
                    photo_options = [_none_option] + [i18n.t("graphics_photo_option", n=i + 1) for i in range(len(photos))]
                    photo_idx = cfg["photo_index"]
                    photo_choice = st.selectbox(
                        i18n.t("graphics_photo_select_label"), photo_options,
                        index=(photo_idx + 1) if photo_idx is not None else 0,
                        key=f"photo_{section.title}", disabled=not photos,
                    )
                with c3:
                    quote_options = [_none_option] + [f"{q['attribution'] or i18n.t('graphics_quote_fallback_label')} {i+1}" for i, q in enumerate(st.session_state.quotes)]
                    quote_idx = cfg["quote_index"]
                    quote_choice = st.selectbox(
                        i18n.t("graphics_quote_select_label"), quote_options,
                        index=(quote_idx + 1) if quote_idx is not None else 0,
                        key=f"quote_{section.title}", disabled=not st.session_state.quotes,
                    )
                with c4:
                    photo_caption = st.text_input(
                        i18n.t("graphics_photo_title_label"), value=cfg.get("photo_caption", ""),
                        placeholder=i18n.t("graphics_photo_title_placeholder"),
                        key=f"photo_caption_{section.title}", disabled=not photos,
                        help=i18n.t("graphics_photo_title_help"),
                    )
                cfg["layout"] = layout
                cfg["photo_index"] = None if photo_choice == _none_option else int(photo_choice.split()[-1]) - 1
                # Show which photo "Photo 2" actually is, rather than making
                # the user generate the banner to find out.
                if cfg["photo_index"] is not None and cfg["photo_index"] < len(photos):
                    with c2:
                        try:
                            st.image(photos[cfg["photo_index"]], use_container_width=True)
                        except Exception:
                            pass
                cfg["quote_index"] = None if quote_choice == _none_option else quote_options.index(quote_choice) - 1
                cfg["photo_caption"] = photo_caption.strip()

                existing = st.session_state.divider_images.get(section.title)
                if existing:
                    st.image(existing, caption=i18n.t("graphics_current_banner_caption"), use_container_width=True)

        st.divider()
        st.markdown(i18n.t("graphics_font_heading"))
        st.selectbox(
            i18n.t("graphics_font_label"), ["Arial", "Calibri", "Helvetica", "Times New Roman", "Georgia", "Verdana"],
            key="body_font", help=i18n.t("graphics_font_help"),
        )

        st.markdown(i18n.t("graphics_generate_heading"))
        if st.button(i18n.t("graphics_generate_button"), type="primary"):
            new_divider_images = {}
            for section in st.session_state.sections:
                cfg = config[section.title]
                photo_bytes = photos[cfg["photo_index"]] if cfg["photo_index"] is not None and photos else None
                _quote_idx = cfg.get("quote_index")
                _picked_quote = (
                    st.session_state.quotes[_quote_idx]
                    if _quote_idx is not None and _quote_idx < len(st.session_state.quotes) else None
                )
                png = divider_designer.render_full_page_divider(
                    section.title, cfg["layout"], theme_name, photo_bytes=photo_bytes,
                    section_label=str(section.section_number),
                    quote_text=_picked_quote["text"] if _picked_quote else None,
                    quote_attribution=_picked_quote["attribution"] if _picked_quote else None,
                    photo_caption=cfg.get("photo_caption") or None,
                )
                if png:
                    new_divider_images[section.title] = png
            st.session_state.divider_images = new_divider_images

            if not st.session_state.project_photo_bytes:
                st.session_state.cover_hero_png = divider_designer.render_banner(
                    st.session_state.tender_name or i18n.t("graphics_default_tender_pack_name"), "Solid colour", theme_name,
                )
            else:
                st.session_state.cover_hero_png = None

            flags = _company_materials_flags()
            st.session_state.graphics = graphics_engine.recommend_graphics(
                st.session_state.sections, flags["has_project_photos"], flags["has_company_image_library"],
                divider_image_sections=set(new_divider_images.keys()),
                cover_generated=bool(st.session_state.project_photo_bytes or st.session_state.cover_hero_png),
                project_type=st.session_state.get("project_type"),
            )
            if st.session_state.weighted_criteria:
                st.session_state.weighting_chart_png = graphics_engine.generate_weighting_chart(st.session_state.weighted_criteria)
            st.success(i18n.t("graphics_generated_success", banners=len(new_divider_images), recs=len(st.session_state.graphics)))

    if st.session_state.graphics:
        st.divider()
        st.markdown(i18n.t("graphics_remaining_placeholders_heading"))
        st.dataframe(
            [{
                i18n.t("graphics_col_graphic"): g.graphic_title, i18n.t("graphics_col_type"): g.graphic_type,
                i18n.t("graphics_col_placement"): g.suggested_placement,
                i18n.t("graphics_col_source_needed"): g.source_data_required, i18n.t("graphics_col_status"): g.status,
            } for g in st.session_state.graphics],
            use_container_width=True,
        )
        if st.session_state.weighting_chart_png:
            st.markdown(i18n.t("graphics_weighting_dashboard_heading"))
            st.image(st.session_state.weighting_chart_png)


