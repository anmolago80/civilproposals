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
    st.subheader("Proposal Structure")
    st.caption("If the brief names its own selection criteria, the structure mirrors those exactly. Otherwise it falls back to the standard skeleton, ordered by weighting.")

    ready = st.session_state.analysis is not None
    if not ready:
        st.info("Run Tender Analysis first.")

    if st.button("Generate Proposal Structure", type="primary", disabled=not ready):
        _rebuild_structure()
        st.success(f"Generated {len(st.session_state.sections)} section(s).")

    if _structure_format_stale():
        st.warning(
            "You changed the Proposal format (Project Setup) after these sections were generated, so "
            "the list below is still built for the *previous* format and won't match what "
            "drafting/export expect (e.g. no 'Project Understanding' section for a Small Scope "
            "pack). Click **Generate Proposal Structure** above again to refresh it."
        )

    sections = st.session_state.sections
    if sections:
        st.dataframe(
            [{
                "#": s.section_number, "Title": s.title, "Fixed": "Yes" if s.is_fixed else "No",
                "Weighting": f"{s.weighting:.0f}%" if s.weighting else "-",
                "Weighting source": s.weighting_source, "Pages": s.allocated_pages,
                "Page source": s.page_limit_source,
            } for s in sections],
            use_container_width=True,
        )

        with st.expander("Manually override a section's weighting"):
            criteria = st.session_state.weighted_criteria
            names = [c.criterion_name for c in criteria if not c.is_mandatory_gate]
            if names:
                target = st.selectbox("Section", names, key="weight_override_target")
                new_weight = st.number_input("New weighting (%)", 0.0, 100.0, step=1.0, key="weight_override_value")
                if st.button("Apply weighting override", type="primary"):
                    updated = weighting_engine.apply_manual_override(criteria, {target: new_weight})
                    st.session_state.weighted_criteria = updated
                    allocations = page_allocation.allocate_pages(updated, st.session_state.analysis)
                    new_sections = proposal_structure.build_proposal_structure(
                        st.session_state.analysis, updated, allocations, proposal_format=st.session_state.proposal_format,
                    )
                    st.session_state.allocations = allocations
                    st.session_state.sections = new_sections
                    st.session_state.guidance_notes = guidance_generator.generate_all_guidance_notes(new_sections)
                    st.success(f"Weighting for '{target}' set to {new_weight:.0f}%. Structure recalculated.")
                    st.rerun()

        st.divider()
        st.markdown("#### Compliance matrix")
        if st.button("Generate Compliance Matrix", type="primary"):
            st.session_state.compliance_items = compliance_matrix.build_compliance_matrix(
                st.session_state.analysis, sections, _company_materials_flags(),
            )
        if st.session_state.compliance_items:
            st.dataframe(
                [{
                    "ID": i.requirement_id, "Description": i.description, "Type": i.requirement_type,
                    "Mapped section": i.mapped_section or "-", "Priority": i.priority, "Status": i.status,
                } for i in st.session_state.compliance_items],
                use_container_width=True,
            )

        st.markdown("#### Gap analysis")
        if st.button("Generate Gap Analysis", disabled=st.session_state.compliance_items is None, type="primary"):
            st.session_state.gap_items = gap_analysis.analyse_gaps(
                st.session_state.analysis, st.session_state.compliance_items,
                st.session_state.weighted_criteria, _company_materials_flags(),
            )
        if st.session_state.gap_items:
            st.dataframe(
                [{
                    "Risk": g.risk_level, "Issue": g.issue, "Impact": g.impact,
                    "Recommended action": g.recommended_action, "Section": g.mapped_section or "-",
                } for g in st.session_state.gap_items],
                use_container_width=True,
            )


# ---------------------------------------------------------------------------
# Tab 5: Page Allocation
# ---------------------------------------------------------------------------

with tabs[4]:
    st.subheader("Page Allocation")
    st.caption("Priority order: brief's exact section limit > weighted share of a stated total > default template.")
    if _is_letter():
        st.info(
            "The Small Scope pack doesn't carry a stated page limit to mirror, so this step is "
            "indicative only -- its actual section lengths come from the Sections table (tab "
            "4), not from page allocation."
        )

    allocations = st.session_state.allocations
    if not allocations:
        st.info("Generate the Proposal Structure first.")
    else:
        st.dataframe(
            [{
                "Section": a.section_name, "Weighting": f"{a.weighting:.0f}%",
                "Source": a.page_limit_source, "Allocated pages": a.allocated_pages, "Reason": a.reason,
            } for a in allocations],
            use_container_width=True,
        )
        with st.expander("Manually override a section's page count"):
            section_names = [a.section_name for a in allocations]
            target = st.selectbox("Section", section_names, key="page_override_target")
            new_pages = st.number_input("New page count", 1, 50, value=2, step=1, key="page_override_value")
            if st.button("Apply page override", type="primary"):
                updated = page_allocation.apply_manual_page_override(allocations, {target: int(new_pages)})
                st.session_state.allocations = updated
                new_sections = proposal_structure.build_proposal_structure(
                    st.session_state.analysis, st.session_state.weighted_criteria, updated,
                    proposal_format=st.session_state.proposal_format,
                )
                st.session_state.sections = new_sections
                st.session_state.guidance_notes = guidance_generator.generate_all_guidance_notes(new_sections)
                st.success(f"'{target}' set to {new_pages} page(s). Structure updated.")
                st.rerun()


