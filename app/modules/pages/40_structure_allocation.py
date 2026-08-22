# modules/pages/40_structure_allocation.py -- one segment of the CivilProposals app script.
# Tab 4 Proposal Structure and Tab 5 Page Allocation.
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
# Tab 4: Proposal Structure
# ---------------------------------------------------------------------------

with tabs[3]:
    st.subheader(i18n.t("structure_subheader"))
    st.caption(i18n.t("structure_caption"))

    ready = st.session_state.analysis is not None
    if not ready:
        st.info(i18n.t("structure_run_analysis_first"))

    if st.button(i18n.t("structure_generate_button"), type="primary", disabled=not ready):
        _rebuild_structure()
        st.success(i18n.t("structure_generated_success", n=len(st.session_state.sections)))

    if _structure_format_stale():
        st.warning(i18n.t("structure_format_stale_warning"))

    sections = st.session_state.sections
    if sections:
        st.dataframe(
            [{
                i18n.t("structure_col_number"): s.section_number, i18n.t("structure_col_title"): s.title,
                i18n.t("structure_col_fixed"): i18n.t("structure_fixed_yes") if s.is_fixed else i18n.t("structure_fixed_no"),
                i18n.t("structure_col_weighting"): f"{s.weighting:.0f}%" if s.weighting else "-",
                i18n.t("structure_col_weighting_source"): s.weighting_source, i18n.t("structure_col_pages"): s.allocated_pages,
                i18n.t("structure_col_page_source"): s.page_limit_source,
            } for s in sections],
            use_container_width=True,
        )

        with st.expander(i18n.t("structure_override_weighting_expander")):
            criteria = st.session_state.weighted_criteria
            names = [c.criterion_name for c in criteria if not c.is_mandatory_gate]
            if names:
                target = st.selectbox(i18n.t("structure_section_label"), names, key="weight_override_target")
                new_weight = st.number_input(i18n.t("structure_new_weighting_label"), 0.0, 100.0, step=1.0, key="weight_override_value")
                if st.button(i18n.t("structure_apply_weighting_button"), type="primary"):
                    updated = weighting_engine.apply_manual_override(criteria, {target: new_weight})
                    st.session_state.weighted_criteria = updated
                    allocations = page_allocation.allocate_pages(updated, st.session_state.analysis)
                    new_sections = proposal_structure.build_proposal_structure(
                        st.session_state.analysis, updated, allocations, proposal_format=st.session_state.proposal_format,
                    )
                    st.session_state.allocations = allocations
                    st.session_state.sections = new_sections
                    st.session_state.guidance_notes = guidance_generator.generate_all_guidance_notes(new_sections)
                    st.success(i18n.t("structure_weighting_applied_success", target=target, weight=new_weight))
                    st.rerun()

        st.divider()
        st.markdown(i18n.t("structure_compliance_heading"))
        if st.button(i18n.t("structure_generate_compliance_button"), type="primary"):
            st.session_state.compliance_items = compliance_matrix.build_compliance_matrix(
                st.session_state.analysis, sections, _company_materials_flags(),
            )
        if st.session_state.compliance_items:
            st.dataframe(
                [{
                    i18n.t("structure_compliance_col_id"): i.requirement_id, i18n.t("structure_compliance_col_description"): i.description,
                    i18n.t("structure_compliance_col_type"): i.requirement_type,
                    i18n.t("structure_compliance_col_mapped_section"): i.mapped_section or "-",
                    i18n.t("structure_compliance_col_priority"): i.priority, i18n.t("structure_compliance_col_status"): i.status,
                } for i in st.session_state.compliance_items],
                use_container_width=True,
            )

        st.markdown(i18n.t("structure_gap_heading"))
        if st.button(i18n.t("structure_generate_gap_button"), disabled=st.session_state.compliance_items is None, type="primary"):
            st.session_state.gap_items = gap_analysis.analyse_gaps(
                st.session_state.analysis, st.session_state.compliance_items,
                st.session_state.weighted_criteria, _company_materials_flags(),
            )
        if st.session_state.gap_items:
            st.dataframe(
                [{
                    i18n.t("structure_gap_col_risk"): g.risk_level, i18n.t("structure_gap_col_issue"): g.issue,
                    i18n.t("structure_gap_col_impact"): g.impact,
                    i18n.t("structure_gap_col_recommended_action"): g.recommended_action,
                    i18n.t("structure_gap_col_section"): g.mapped_section or "-",
                } for g in st.session_state.gap_items],
                use_container_width=True,
            )


# ---------------------------------------------------------------------------
# Tab 5: Page Allocation
# ---------------------------------------------------------------------------

with tabs[4]:
    st.subheader(i18n.t("pageaalloc_subheader"))
    st.caption(i18n.t("pageaalloc_caption"))
    if _is_letter():
        st.info(i18n.t("pageaalloc_small_scope_info"))

    allocations = st.session_state.allocations
    if not allocations:
        st.info(i18n.t("pageaalloc_generate_structure_first"))
    else:
        st.dataframe(
            [{
                i18n.t("pageaalloc_col_section"): a.section_name, i18n.t("pageaalloc_col_weighting"): f"{a.weighting:.0f}%",
                i18n.t("pageaalloc_col_source"): a.page_limit_source, i18n.t("pageaalloc_col_allocated_pages"): a.allocated_pages,
                i18n.t("pageaalloc_col_reason"): a.reason,
            } for a in allocations],
            use_container_width=True,
        )
        with st.expander(i18n.t("pageaalloc_override_pages_expander")):
            section_names = [a.section_name for a in allocations]
            target = st.selectbox(i18n.t("pageaalloc_section_label"), section_names, key="page_override_target")
            new_pages = st.number_input(i18n.t("pageaalloc_new_pages_label"), 1, 50, value=2, step=1, key="page_override_value")
            if st.button(i18n.t("pageaalloc_apply_pages_button"), type="primary"):
                updated = page_allocation.apply_manual_page_override(allocations, {target: int(new_pages)})
                st.session_state.allocations = updated
                new_sections = proposal_structure.build_proposal_structure(
                    st.session_state.analysis, st.session_state.weighted_criteria, updated,
                    proposal_format=st.session_state.proposal_format,
                )
                st.session_state.sections = new_sections
                st.session_state.guidance_notes = guidance_generator.generate_all_guidance_notes(new_sections)
                st.success(i18n.t("pageaalloc_pages_applied_success", target=target, pages=new_pages))
                st.rerun()


