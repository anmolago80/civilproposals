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
        st.subheader("Project Team")
        st.caption(
            "Built entirely from the Team & Resourcing tab (step 8) -- the same people, the same "
            "CV-drafted bios, and the same 'include in proposal' ticks used there also drive this "
            "pack's Project Team section, so there's only one place to build your team, whichever "
            "pack size you're preparing. Head to step 8 to assign people, draft bios from the CV "
            "library, add a team member under a discipline lead (with their own title), and tick "
            "who's included. This is a read-only preview of what the exported pack will show."
        )
        entries = resourcing.letter_team_entries(st.session_state.resource_plan)
        if not entries:
            st.info(
                "No one is assigned and ticked 'Include in proposal' yet -- head to step 8 "
                "(Team & Resourcing) to build the team."
            )
        else:
            for entry in entries:
                marker = "↳ " if entry["indent"] else ""
                name = entry["name"] or "[not assigned]"
                st.markdown(f"{marker}**{name}** -- {entry['role_label']}")
    else:
        st.subheader("Graphics & Design")
        st.caption(
            "Real, generated divider banners and cover art built from your own uploaded photos and "
            "typed quotes -- never invented imagery. Everything this tool can't build for real "
            "(org charts, methodology diagrams, programme timelines) stays a clearly marked placeholder below."
        )

    ready = st.session_state.sections is not None
    if not ready:
        st.info("Generate the Proposal Structure first.")
    elif _is_letter():
        pass  # Project Team preview above already covers this pack size -- nothing else to render here.
    else:
        _ensure_divider_config(st.session_state.sections)
        photos = st.session_state.project_photo_bytes
        theme_name = st.session_state.proposal_theme

        st.markdown("#### 1. Pull-quotes / testimonials (optional)")
        st.caption("Only real quotes you type in here -- nothing is invented or pulled from the web.")
        with st.form("add_quote_form", clear_on_submit=True):
            qcol1, qcol2 = st.columns(2)
            with qcol1:
                q_text = st.text_area("Quote", placeholder="e.g. \"The team delivered a technically excellent outcome...\"", height=80)
            with qcol2:
                q_attr = st.text_input("Attributed to", placeholder="e.g. J. Smith, Project Director, XYZ Council")
                q_project = st.text_input("Project (optional)", placeholder="e.g. Burnett River Bridge")
            if st.form_submit_button("Add quote", type="primary") and q_text.strip():
                st.session_state.quotes.append({"text": q_text.strip(), "attribution": q_attr.strip(), "project": q_project.strip()})

        if st.session_state.quotes:
            for i, q in enumerate(st.session_state.quotes):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"_{q['text']}_ — **{q['attribution'] or 'unattributed'}**" + (f" ({q['project']})" if q['project'] else ""))
                with col2:
                    if st.button("Remove", key=f"remove_quote_{i}", type="primary"):
                        st.session_state.quotes.pop(i)
                        st.rerun()

        st.divider()
        st.markdown("#### 2. Divider design per section")
        if not photos:
            st.info("No project photos uploaded (Upload Docs) -- sections default to the 'Solid colour' layout. Upload photos there to unlock photo-based layouts.")

        available_layouts = ["Solid colour"] + (["Photo + gradient", "Photo + quote", "Split (colour + photo)"] if photos else [])
        config = st.session_state.section_divider_config

        for section in st.session_state.sections:
            cfg = config[section.title]
            with st.expander(f"{section.section_number}. {section.title}"):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    layout = st.selectbox(
                        "Layout", available_layouts,
                        index=available_layouts.index(cfg["layout"]) if cfg["layout"] in available_layouts else 0,
                        key=f"layout_{section.title}",
                    )
                with c2:
                    photo_options = ["(none)"] + [f"Photo {i+1}" for i in range(len(photos))]
                    photo_idx = cfg["photo_index"]
                    photo_choice = st.selectbox(
                        "Photo", photo_options,
                        index=(photo_idx + 1) if photo_idx is not None else 0,
                        key=f"photo_{section.title}", disabled=not photos,
                    )
                with c3:
                    quote_options = ["(none)"] + [f"{q['attribution'] or 'Quote'} {i+1}" for i, q in enumerate(st.session_state.quotes)]
                    quote_idx = cfg["quote_index"]
                    quote_choice = st.selectbox(
                        "Quote", quote_options,
                        index=(quote_idx + 1) if quote_idx is not None else 0,
                        key=f"quote_{section.title}", disabled=not st.session_state.quotes,
                    )
                with c4:
                    photo_caption = st.text_input(
                        "Photo title", value=cfg.get("photo_caption", ""),
                        placeholder="e.g. Mangaweka Bridge",
                        key=f"photo_caption_{section.title}", disabled=not photos,
                        help="Shown bottom-right of the photo itself, not the coloured band. "
                             "Only used when this section has a photo.",
                    )
                cfg["layout"] = layout
                cfg["photo_index"] = None if photo_choice == "(none)" else int(photo_choice.split()[-1]) - 1
                cfg["quote_index"] = None if quote_choice == "(none)" else quote_options.index(quote_choice) - 1
                cfg["photo_caption"] = photo_caption.strip()

                existing = st.session_state.divider_images.get(section.title)
                if existing:
                    st.image(existing, caption="Current banner for this section", use_container_width=True)

        st.divider()
        st.markdown("#### 3. Document font")
        st.selectbox(
            "Body & heading font", ["Arial", "Calibri", "Helvetica", "Times New Roman", "Georgia", "Verdana"],
            key="body_font", help="Applied to the exported Word document and the divider text.",
        )

        st.markdown("#### 4. Generate")
        if st.button("Generate Graphics Package", type="primary"):
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
                    st.session_state.tender_name or "Tender Response Pack", "Solid colour", theme_name,
                )
            else:
                st.session_state.cover_hero_png = None

            flags = _company_materials_flags()
            st.session_state.graphics = graphics_engine.recommend_graphics(
                st.session_state.sections, flags["has_project_photos"], flags["has_company_image_library"],
                divider_image_sections=set(new_divider_images.keys()),
                cover_generated=bool(st.session_state.project_photo_bytes or st.session_state.cover_hero_png),
            )
            if st.session_state.weighted_criteria:
                st.session_state.weighting_chart_png = graphics_engine.generate_weighting_chart(st.session_state.weighted_criteria)
            st.success(f"Generated {len(new_divider_images)} divider banner(s) and {len(st.session_state.graphics)} graphic recommendation(s).")

    if st.session_state.graphics:
        st.divider()
        st.markdown("#### Remaining placeholders overview")
        st.dataframe(
            [{
                "Graphic": g.graphic_title, "Type": g.graphic_type, "Placement": g.suggested_placement,
                "Source needed": g.source_data_required, "Status": g.status,
            } for g in st.session_state.graphics],
            use_container_width=True,
        )
        if st.session_state.weighting_chart_png:
            st.markdown("#### Evaluation weighting dashboard (generated)")
            st.image(st.session_state.weighting_chart_png)


