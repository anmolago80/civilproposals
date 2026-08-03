"""
resourcing.py

Turns the disciplines the brief calls for into (a) a resourcing plan -- who
staffs each discipline and each mandatory management role -- and (b) the row
set for the discipline fee build-up. Both are deliberately built from the
brief plus a couple of hard rules, never from a "typical team" template:

- The required disciplines are exactly what tender_analyser extracted from
  THIS brief (analysis.disciplines_involved), plus Project Management, which
  is ALWAYS included whether or not the brief names it -- every job the firm
  prices carries PM effort, so leaving it out of the fee build-up would
  understate the bid every time.
- Every org chart, regardless of project, carries the four management roles a
  design commission always has: the client's Project Manager at the top (their
  side of the table), then the firm's Project Director, Project Manager, and
  Design Manager. These are separate from the discipline leads and are never
  dropped, even if the brief doesn't spell them out.

Nothing here calls the AI. Name assignment is done by the user in the app
(picking from CV-derived names or typing someone in who has no CV uploaded);
this module just defines the shape of the plan and the rules around it.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from modules.ai_interface import call_ai_json

# The management roles every design-commission org chart must show. The client's
# PM sits on the client side of the chart (top); the other three are the firm's
# leadership for the job. Order matters -- it's the top-down order in the chart.
CLIENT_ROLE = "Client Project Manager"
FIRM_MANAGEMENT_ROLES = ["Project Director", "Project Manager", "Design Manager"]
MANDATORY_ORG_ROLES = [CLIENT_ROLE] + FIRM_MANAGEMENT_ROLES

# Fixed note shown next to the firm's three leadership roles' "include in proposal"
# tick -- these three are never judged against scope (see suggest_proposal_inclusion),
# they're just tickable "in case" per the user's own instruction.
FIRM_LEADERSHIP_REASON = "Project leadership -- recommended to include."

# Project Management is always part of the discipline fee build-up.
ALWAYS_INCLUDED_DISCIPLINE = "Project Management"

# Light canonicalisation so "geotech", "Geotechnical Engineering", and
# "geotechnical" don't show up as three separate fee rows. This is intentionally
# small and conservative -- it only merges obvious synonyms, and anything it
# doesn't recognise is kept verbatim (title-cased) rather than dropped.
_CANONICAL = {
    "geotech": "Geotechnical",
    "geotechnical": "Geotechnical",
    "geotechnical engineering": "Geotechnical",
    "structural": "Structural",
    "structures": "Structural",
    "structural engineering": "Structural",
    "bridge": "Bridges",
    "bridges": "Bridges",
    "hydraulics": "Hydraulics & Hydrology",
    "hydrology": "Hydraulics & Hydrology",
    "hydraulics and hydrology": "Hydraulics & Hydrology",
    "hydraulics & hydrology": "Hydraulics & Hydrology",
    "drainage": "Hydraulics & Hydrology",
    "road": "Road & Civil",
    "civil": "Road & Civil",
    "road and civil": "Road & Civil",
    "road & civil": "Road & Civil",
    "roads": "Road & Civil",
    "environmental": "Environmental",
    "environment": "Environmental",
    "environmental and cultural heritage": "Environmental",
    "traffic": "Traffic Engineering",
    "traffic engineering": "Traffic Engineering",
    "pavement": "Pavement",
    "survey": "Survey",
    "surveying": "Survey",
    "cost": "Cost Estimating",
    "cost estimating": "Cost Estimating",
    "quantity surveying": "Cost Estimating",
    "project management": ALWAYS_INCLUDED_DISCIPLINE,
    "pm": ALWAYS_INCLUDED_DISCIPLINE,
}


class ResourceAssignment(BaseModel):
    """One row of the resourcing plan: a role or discipline, who's staffed to
    it, and whether that person came from an uploaded CV or was typed in by
    hand (someone the firm has but hasn't uploaded a CV for).

    The four fields below (rpeq_status/years_experience/value_to_project/
    local_experience) feed the Key Personnel profile block in export_docx.py
    (see build_personnel_profiles/_build_personnel_profiles). They're always
    optional, user-entered text -- never AI-invented -- and left blank means
    the exported profile shows an explicit bracketed placeholder rather than
    a guess, same no-invention discipline as the rest of the tool."""
    slot: str                       # e.g. "Project Director" or "Geotechnical"
    slot_kind: str                  # "management" | "discipline"
    person_name: str = ""           # blank until the user assigns someone
    from_cv: bool = False           # True if picked from a CV-derived name
    is_lead: bool = True            # discipline lead vs support (management always lead)
    # A discipline can carry more than one person: exactly one lead
    # (is_lead=True) plus any number of support rows (is_lead=False) sharing
    # the same `slot`, added under that lead in the Team & Resourcing tab
    # (e.g. "Ryan Swagemakers" added under the "Structural" lead). custom_title
    # is ONLY used for a support row -- the user's own free-text label for
    # that person's position on the job (e.g. "Bridge Engineer"), since a
    # support member's title is rarely just the discipline name. A lead's
    # displayed title is always its `slot` (unchanged). Never guessed --
    # blank means "not yet given a title" and renders as a placeholder.
    custom_title: str = ""
    qualification: str = ""         # e.g. "BEng (Civil) (Hons), UQ, 2003" -- user-entered, never guessed
    rpeq_status: str = ""           # e.g. "RPEQ 12345" -- user-entered, never guessed
    years_experience: str = ""      # e.g. "18 years" -- free text, user-entered
    value_to_project: str = ""      # "On this project, [name] will..." -- user-entered
    relevant_projects: list[str] = Field(default_factory=list)  # bullet list of past projects, user-entered
    local_experience: list[str] = Field(default_factory=list)  # bullet list, user-entered
    # Whether this person's/slot's Key Personnel profile (photo + write-up) makes it
    # into the exported pack. Defaults True (nobody is dropped unless the user or the
    # AI recommendation says otherwise) -- see suggest_proposal_inclusion() below and
    # export_docx._build_personnel_profiles, which filters on this flag. Ticking is a
    # SPACE decision, not a staffing one: an unticked person is still on the job and
    # still shows in the fee build-up/org chart, they just don't get a full pen-pic
    # profile in a page-limited section.
    include_in_proposal: bool = True


# Keyword rules for canonicalisation, checked in order (first match wins). Each
# entry is (word-stems, canonical label): a discipline name matches if ANY of its
# words STARTS WITH one of the stems. Matching on word-start (not raw substring)
# is deliberate -- it means "Structural Design" and "Structural (Bridge)
# Engineering" both collapse to "Structural", while "Infrastructure" (whose only
# word doesn't start with "structur") is left alone. Order matters where a name
# could match two rules (e.g. "quantity surveying" hits cost before survey).
_KEYWORD_RULES = [
    (("constructab",), "Constructability"),
    (("geotech",), "Geotechnical"),
    (("hydraul", "hydrolog", "drainage", "stormwater", "flood"), "Hydraulics & Hydrology"),
    (("pavement",), "Pavement"),
    (("structur",), "Structural"),           # structural / structure(s)
    (("bridge",), "Bridges"),
    (("environ", "ecolog"), "Environmental"),
    (("heritage", "cultural"), "Cultural Heritage"),
    (("traffic",), "Traffic Engineering"),
    (("rail",), "Rail"),
    (("cost", "estimat", "quantity"), "Cost Estimating"),
    (("survey",), "Survey"),
    (("landscap",), "Landscaping"),
    (("stakeholder", "engagement", "communicat"), "Stakeholder Engagement"),
    (("sustainab",), "Sustainability"),
    (("utilit", "service"), "Utilities & Services"),
    (("road", "civil", "highway"), "Road & Civil"),
    (("electric",), "Electrical"),
    (("mechanic",), "Mechanical"),
]


def canonical_discipline(name: str) -> str:
    """
    Map a raw discipline string to a canonical label so variant phrasings merge
    ("Structural Design" and "Structural (Bridge) Engineering" -> "Structural";
    "Hydraulics / Hydrology" and "Hydraulic/Hydrology Engineering" ->
    "Hydraulics & Hydrology"). Falls back to a tidied title-case of the original
    if nothing matches. Never returns an empty string for non-empty input.
    """
    raw = (name or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered in _CANONICAL:
        return _CANONICAL[lowered]

    words = re.findall(r"[a-z]+", lowered)
    if "project" in words and "management" in words:
        return ALWAYS_INCLUDED_DISCIPLINE
    if words == ["pm"]:
        return ALWAYS_INCLUDED_DISCIPLINE
    for stems, label in _KEYWORD_RULES:
        if any(w.startswith(stem) for w in words for stem in stems):
            return label

    singular = lowered.rstrip("s")
    if singular in _CANONICAL:
        return _CANONICAL[singular]
    return raw if raw.isupper() else raw.title()


def normalize_plan_disciplines(plan: list) -> list:
    """
    Canonicalise the discipline slots in an existing resourcing plan and merge
    any LEAD rows that collapse to the same label (e.g. two 'Structural ...'
    lead rows become one 'Structural'). Management roles are left untouched.
    When merging leads, an assigned person is preferred over an unassigned
    duplicate, so cleaning up duplicates never silently drops someone the user
    already staffed.

    Support rows (is_lead=False -- team members added under a discipline lead,
    see ResourceAssignment.custom_title) are NEVER merged/dropped here: each is
    a distinct person, not a duplicate to collapse, even if two of them share a
    discipline. Their `slot` is still canonicalised (so they track a re-labelled
    discipline the same way their lead does), and each lead's own support rows
    are kept immediately after it so grouping by slot stays contiguous and
    stable for callers (org chart, Small Scope Project Team section, etc.) --
    see discipline_groups() below.

    Returns a new list; original order preserved by first appearance.
    """
    management = [a for a in plan if getattr(a, "slot_kind", "discipline") == "management"]
    disciplines = [a for a in plan if getattr(a, "slot_kind", "discipline") != "management"]
    leads = [a for a in disciplines if getattr(a, "is_lead", True)]
    supports = [a for a in disciplines if not getattr(a, "is_lead", True)]

    by_label: dict[str, ResourceAssignment] = {}
    order: list[str] = []
    for a in leads:
        label = canonical_discipline(a.slot)
        if label not in by_label:
            a.slot = label
            by_label[label] = a
            order.append(label)
        else:
            existing = by_label[label]
            # Keep whichever has a person assigned; prefer the existing one otherwise.
            if not (existing.person_name or "").strip() and (a.person_name or "").strip():
                a.slot = label
                by_label[label] = a

    normalized_supports: list[ResourceAssignment] = []
    seen_supports = set()
    for a in supports:
        a.slot = canonical_discipline(a.slot)
        dedupe_key = (a.slot, normalize_name_key(a.person_name), (a.custom_title or "").strip().lower())
        if dedupe_key in seen_supports:
            continue
        seen_supports.add(dedupe_key)
        normalized_supports.append(a)

    result: list[ResourceAssignment] = []
    for label in order:
        result.append(by_label[label])
        result += [s for s in normalized_supports if s.slot == label]
    # A support row whose lead no longer exists (shouldn't normally happen --
    # e.g. the lead was deleted without also removing its support rows) is
    # still kept, just no longer grouped under anything, rather than dropped.
    result += [s for s in normalized_supports if s.slot not in by_label]
    return management + result


def discipline_groups(plan: list) -> list[dict]:
    """
    Group the discipline rows of a (normalized) resourcing plan into one entry
    per discipline: {"lead": ResourceAssignment | None, "supports": [ResourceAssignment, ...]}.
    Order follows first appearance of each slot in `plan`. A discipline with
    support rows but somehow no lead row (shouldn't normally happen) still gets
    a group with lead=None, so its support members are never silently dropped
    by a caller that only looks at "lead". Management rows are ignored --
    callers that need those read the plan directly (see personnel_profile_order).
    """
    groups: dict[str, dict] = {}
    order: list[str] = []
    for a in plan or []:
        if getattr(a, "slot_kind", "discipline") != "discipline":
            continue
        slot = a.slot
        if slot not in groups:
            groups[slot] = {"lead": None, "supports": []}
            order.append(slot)
        if getattr(a, "is_lead", True) and groups[slot]["lead"] is None:
            groups[slot]["lead"] = a
        elif not getattr(a, "is_lead", True):
            groups[slot]["supports"].append(a)
        elif groups[slot]["lead"] is not None:
            # A second is_lead=True row for the same slot (shouldn't happen
            # once normalize_plan_disciplines has run) -- treat it as a
            # support rather than silently dropping the person.
            groups[slot]["supports"].append(a)
    return [groups[slot] for slot in order]


def required_disciplines(disciplines_involved: list[str] | None) -> list[str]:
    """
    The disciplines the fee build-up must cover: every discipline the brief
    named (canonicalised and de-duplicated), plus Project Management, which is
    ALWAYS present even if the brief never mentions it.

    Project Management is ordered first (it spans the whole job); the rest keep
    the order the brief introduced them in, which tends to track importance.

    Used by the fee build-up (seed_discipline_fee_lines / ensure_project_management_present).
    For the Team & Resourcing tab's discipline-lead list, use
    resourcing_disciplines() instead -- Project Management is staffed by the
    Project Manager management role there, not a separate discipline lead.
    """
    ordered: list[str] = [ALWAYS_INCLUDED_DISCIPLINE]
    seen = {ALWAYS_INCLUDED_DISCIPLINE.lower()}
    for raw in (disciplines_involved or []):
        canon = canonical_discipline(raw)
        if not canon:
            continue
        if canon.lower() in seen:
            continue
        seen.add(canon.lower())
        ordered.append(canon)
    return ordered


def resourcing_disciplines(disciplines_involved: list[str] | None) -> list[str]:
    """
    The disciplines the Team & Resourcing tab should list as discipline-lead
    rows: everything required_disciplines() returns, MINUS Project Management.

    Project Management effort is staffed by the Project Manager management
    role (see FIRM_MANAGEMENT_ROLES / MANDATORY_ORG_ROLES), which already sits
    at the top of the org chart -- listing it again as a discipline lead would
    just be the same person/role duplicated under a second heading. It still
    gets its own line in the fee build-up (required_disciplines /
    seed_discipline_fee_lines) since that's a cost category, not a staffing
    slot.
    """
    return [d for d in required_disciplines(disciplines_involved) if d != ALWAYS_INCLUDED_DISCIPLINE]


def role_label(a) -> str:
    """
    The title to DISPLAY for one assignment: a lead (or any management role)
    shows its slot as-is (e.g. "Structural", "Project Director"). A support
    row shows its own custom_title if the user gave it one (e.g. "Bridge
    Engineer"), falling back to the slot only when no custom title has been
    entered yet -- never inventing one."""
    if not getattr(a, "is_lead", True) and (getattr(a, "custom_title", "") or "").strip():
        return a.custom_title.strip()
    return a.slot


def personnel_profile_order(plan: list) -> list:
    """
    The order Key Personnel profiles are written up in the exported pack:
    Project Director, then Project Manager, then Design Manager (the firm's
    own leadership, in that fixed order), then discipline leads in whatever
    order they appear in the plan. The client's own Project Manager
    (CLIENT_ROLE) is deliberately excluded -- that's the client's staff, not
    ours, so it doesn't get a "value to project" / RPEQ / photo profile.

    Single source of truth for this ordering, used by both export_docx.py
    (rendering the profiles) and app.py (so the Team & Resourcing tab lists
    people in the same order the exported document will).
    """
    by_slot = {a.slot: a for a in (plan or []) if a.slot_kind == "management"}
    ordered = [by_slot[role] for role in FIRM_MANAGEMENT_ROLES if role in by_slot]
    ordered += [a for a in (plan or []) if a.slot_kind != "management"]
    return ordered


def personnel_profiles_deduped(plan: list) -> list:
    """
    One profile entry per unique assigned PERSON, in personnel_profile_order,
    with the roles a person holds across multiple slots merged into a single
    entry. Without this, someone assigned to two disciplines (e.g. a senior
    engineer leading both Structural and Bridges) would get two duplicate
    Key Personnel profiles -- same name, same RPEQ, same everything -- and a
    duplicate column in the personnel x experience matrix. Deduping by person
    gives one profile that lists all their roles.

    Unassigned slots (no person_name yet) are kept as their own separate
    entries -- there's nothing to dedupe on, and they still need to surface as
    fill-me placeholders in both the editor and the export.

    Each entry is a dict:
      {"assignment": <primary ResourceAssignment -- the person's first slot in
                      order; the editor reads/writes profile fields on this one>,
       "name": str,                    # person_name ("" for an unassigned slot)
       "roles": [slot, ...],           # every slot this person holds, in order
       "qualification" / "rpeq_status" / "years_experience" / "value_to_project":
                      first non-empty value found across the person's slots,
       "relevant_projects" / "local_experience": first non-empty list across
                      the person's slots}

    First-non-empty merging means that if the user happened to fill a field on
    any one of a person's slots, it still shows up on their single merged
    profile -- nothing entered is silently dropped.
    """
    ordered = personnel_profile_order(plan)
    entries: list = []
    index: dict = {}
    for a in ordered:
        name = (getattr(a, "person_name", "") or "").strip()
        if not name:
            entries.append({
                "assignment": a, "name": "", "roles": [role_label(a)],
                "qualification": "", "rpeq_status": "", "years_experience": "",
                "value_to_project": "", "relevant_projects": [], "local_experience": [],
            })
            continue
        key = normalize_name_key(name)
        if key not in index:
            entry = {
                "assignment": a, "name": name, "roles": [role_label(a)],
                "qualification": (getattr(a, "qualification", "") or "").strip(),
                "rpeq_status": (getattr(a, "rpeq_status", "") or "").strip(),
                "years_experience": (getattr(a, "years_experience", "") or "").strip(),
                "value_to_project": (getattr(a, "value_to_project", "") or "").strip(),
                "relevant_projects": list(getattr(a, "relevant_projects", None) or []),
                "local_experience": list(getattr(a, "local_experience", None) or []),
            }
            index[key] = entry
            entries.append(entry)
        else:
            entry = index[key]
            entry["roles"].append(role_label(a))
            if not entry["qualification"]:
                entry["qualification"] = (getattr(a, "qualification", "") or "").strip()
            if not entry["rpeq_status"]:
                entry["rpeq_status"] = (getattr(a, "rpeq_status", "") or "").strip()
            if not entry["years_experience"]:
                entry["years_experience"] = (getattr(a, "years_experience", "") or "").strip()
            if not entry["value_to_project"]:
                entry["value_to_project"] = (getattr(a, "value_to_project", "") or "").strip()
            if not entry["relevant_projects"]:
                entry["relevant_projects"] = list(getattr(a, "relevant_projects", None) or [])
            if not entry["local_experience"]:
                entry["local_experience"] = list(getattr(a, "local_experience", None) or [])
    return entries


def letter_team_entries(plan: list) -> list[dict]:
    """
    The people to show in the Small Scope pack's Project Team section: the
    same people and the same "include in proposal" filter as Large Scope's
    Key Personnel profiles (firm leadership, then discipline leads --
    personnel_profile_order), but with each discipline's support members
    (ResourceAssignment.custom_title -- e.g. "Ryan Swagemakers" added under
    the "Structural" lead, "Mat Williams") listed directly under their own
    lead ("indent": True) instead of flattened into one list. This is what
    makes the nesting show up as indented entries in the Small Scope pack's
    plain-text team list, without the pack needing an org chart image of its
    own (see org_chart.py for the in-app/PPTX chart, which both pack formats
    already share via the Team & Resourcing tab).

    Deliberately NOT deduped by person the way personnel_profiles_deduped()
    is -- someone leading two disciplines shows up once per role here, same
    as the flat list this replaces. Merging that with the lead/support
    nesting below would only complicate a case that barely occurs in
    practice; Large Scope's numbered Key Personnel profiles (which DO need
    the dedupe, to avoid two identical pen-pics) are unaffected either way.

    Each entry: {"assignment", "name", "role_label", "indent", "qualification",
    "rpeq_status", "years_experience", "value_to_project", "relevant_projects"}.
    """
    def _entry(a, indent: bool) -> dict:
        return {
            "assignment": a,
            "name": (a.person_name or "").strip(),
            "role_label": role_label(a),
            "indent": indent,
            "qualification": (a.qualification or "").strip(),
            "rpeq_status": (a.rpeq_status or "").strip(),
            "years_experience": (a.years_experience or "").strip(),
            "value_to_project": (a.value_to_project or "").strip(),
            "relevant_projects": list(a.relevant_projects or []),
        }

    entries: list[dict] = []
    management = [a for a in (plan or []) if a.slot_kind == "management" and a.slot in FIRM_MANAGEMENT_ROLES]
    for a in management:
        if a.include_in_proposal:
            entries.append(_entry(a, indent=False))
    for group in discipline_groups(plan):
        lead = group["lead"]
        if lead is not None and lead.include_in_proposal:
            entries.append(_entry(lead, indent=False))
        for s in group["supports"]:
            if s.include_in_proposal:
                entries.append(_entry(s, indent=True))
    return entries


def excluded_personnel_names(plan: list) -> set[str]:
    """Names of people staffed on the resourcing plan whose primary assignment
    has include_in_proposal=False -- i.e. deliberately left out of the exported
    proposal (e.g. their CV wasn't provided, or they're not essential to this
    bid). Used to keep their name out of everything else that feeds the
    proposal too: drafted section prose, the raw company-material grounding
    text handed to the AI, and so on -- not just the personnel-profile pages
    the tick was originally built for."""
    excluded: set[str] = set()
    for entry in personnel_profiles_deduped(plan):
        a = entry["assignment"]
        if not getattr(a, "include_in_proposal", True):
            name = (entry.get("name") or "").strip()
            if name:
                excluded.add(name)
    return excluded


def build_resource_plan(disciplines_involved: list[str] | None) -> list[ResourceAssignment]:
    """
    Build the starting resourcing plan: the four mandatory management roles
    first (unassigned), then one lead slot per required discipline --
    excluding Project Management, which the Project Manager management role
    already covers (see resourcing_disciplines). The user fills in the names
    in the app.
    """
    plan: list[ResourceAssignment] = []
    for role in MANDATORY_ORG_ROLES:
        plan.append(ResourceAssignment(slot=role, slot_kind="management", is_lead=True))
    for disc in resourcing_disciplines(disciplines_involved):
        plan.append(ResourceAssignment(slot=disc, slot_kind="discipline", is_lead=True))
    return plan


def ensure_project_management_present(disciplines: list[str]) -> list[str]:
    """
    Guard used by the fee table: whatever disciplines the user has ended up with
    (after adding/removing rows), Project Management must still be there. If the
    user removed it, put it back. Returns a new list; existing order preserved,
    PM appended if it was missing.
    """
    if any(canonical_discipline(d) == ALWAYS_INCLUDED_DISCIPLINE or d.strip().lower() == ALWAYS_INCLUDED_DISCIPLINE.lower()
           for d in disciplines):
        return list(disciplines)
    return list(disciplines) + [ALWAYS_INCLUDED_DISCIPLINE]


class DisciplineFeeLine(BaseModel):
    """A single row of the first-pass discipline fee build-up. total_hours and
    rate_per_hour are both manual, user-entered figures -- there is
    deliberately no auto-estimated number for either of them (that lives in
    fee_estimation_engine's indicative split); this table is the user's own
    first-pass build-up per discipline. fee_amount is never entered directly --
    it's always derived (hours x rate) so it can't drift out of sync with the
    two inputs it's built from."""
    discipline: str
    total_hours: float = 0.0
    rate_per_hour: float = 0.0
    note: str = ""

    @property
    def fee_amount(self) -> float:
        """Derived total ($) -- total_hours x rate_per_hour, never entered directly."""
        return self.total_hours * self.rate_per_hour


def seed_discipline_fee_lines(disciplines_involved: list[str] | None) -> list[DisciplineFeeLine]:
    """Seed the manual discipline fee table: one row per required discipline
    (brief disciplines + always Project Management), hours and rate both
    starting at 0 for the user to fill in."""
    return [DisciplineFeeLine(discipline=d) for d in required_disciplines(disciplines_involved)]


def discipline_fee_lines_to_excel(lines: list[DisciplineFeeLine], theme_name: str | None = None) -> bytes | None:
    """
    Build a downloadable .xlsx of the hours x rate discipline fee build-up
    (the Fee Estimate tab's first table). Adds a "Total" summary row and an
    "Average rate across project ($/hr)" row -- total fee divided by total
    hours across every discipline -- since that blended rate is the key
    sanity-check figure for whether the priced hours/rates make sense in
    aggregate, not just discipline by discipline. Returns None if openpyxl
    isn't installed (caller should show an install hint rather than crash).
    """
    from modules.excel_export import build_fee_workbook

    rows = [[l.discipline, l.total_hours, l.rate_per_hour, l.fee_amount, l.note] for l in lines]
    total_hours = sum(l.total_hours for l in lines)
    total_fee = sum(l.fee_amount for l in lines)
    avg_rate = (total_fee / total_hours) if total_hours else None

    summary_rows = [
        ["Total", total_hours or None, None, total_fee or None, ""],
        ["Average rate across project ($/hr)", None, avg_rate, None, ""],
    ]
    return build_fee_workbook(
        sheet_title="Discipline fee build-up",
        headers=["Discipline", "Total hours", "Rate per hour ($)", "Total ($)", "Note"],
        rows=rows,
        column_formats={2: "#,##0.0", 3: "$#,##0.00", 4: "$#,##0"},
        summary_rows=summary_rows,
        theme_name=theme_name,
    )


_FILENAME_NOISE = {
    "cv", "cvs", "resume", "resumes", "curriculum", "vitae", "bio", "bios",
    "profile", "profiles", "final", "draft", "updated", "copy", "new", "latest",
    "v1", "v2", "v3", "the", "and",
}


def _smart_case(word: str) -> str:
    """Capitalise a word UNLESS it's already got internal mixed case (e.g.
    "McAuley", "MacDonald") -- str.title() mangles those into "Mcauley" /
    "Macdonald", which is wrong when the filename already spelled the name
    correctly. Trust mixed-case input; only fix all-caps/all-lower words."""
    if word.isupper() or word.islower():
        return word.capitalize()
    return word


def names_from_filenames(filenames: list[str] | None) -> list[str]:
    """
    Derive candidate person names from uploaded CV filenames -- an instant,
    no-AI way to populate the resourcing dropdowns, since CV files are almost
    always named after the person (e.g. "Andres Moreno - Bridge CV.docx").

    Many firms' CV filenames carry more than just the name -- a project name,
    a date, a version tag -- usually separated from "Firstname_Lastname" by a
    further underscore (e.g. "David_Law_North Johnston River Bridge CV.docx").
    When the filename stem has 2+ underscore-separated segments, only the
    first two are used as the name and everything from the third segment
    onward is discarded -- otherwise a filename like that produces the name
    "David Law North Johnston" instead of "David Law". Filenames with no
    underscore (e.g. "Andres Moreno - Bridge CV.docx") fall back to the
    previous word-based cleanup (strip noise words, cap at 4 words).

    Strips common noise words ("CV", "Resume", "Final", ...) and applies
    smart capitalisation (see _smart_case) rather than str.title(), which
    mangles names like "McAuley" into "Mcauley". These are only candidates --
    the user can ignore, edit, or replace any of them, and the AI extraction
    (which reads the CV text itself) gives more reliable names.
    """
    names: list[str] = []
    seen = set()
    for raw in (filenames or []):
        stem = (raw or "").rsplit(".", 1)[0].strip()
        underscore_parts = [p for p in stem.split("_") if p.strip()]
        if len(underscore_parts) >= 2:
            # "Firstname_Lastname[_anything else]" -- keep only the name segments,
            # discard a third-and-later segment entirely (almost never part of the name).
            candidate = " ".join(underscore_parts[:2])
        else:
            candidate = stem.replace("_", " ").replace("-", " ")
        candidate = re.sub(r"[^A-Za-z ]+", " ", candidate)  # drop digits/punctuation
        words = [w for w in candidate.split() if w.lower() not in _FILENAME_NOISE and len(w) > 1]
        if not words:
            continue
        name = " ".join(_smart_case(w) for w in words[:4]).strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names


# Words that essentially never appear in a real person's name but commonly show
# up in reference/project titles -- a safety net for when a non-CV document
# (e.g. a reference project write-up) ends up mixed into the CV library upload,
# so its filename or an AI mis-read of its heading doesn't get suggested as a
# person's name (e.g. "Coomera To Helensvale Duplication" from a stray
# "Coomera to Helensvale Duplication.docx" reference document in the CV
# library). Deliberately short and conservative: small connector words are a
# near-certain signal, and the infrastructure nouns are ones a person's name
# essentially never contains.
_NOT_A_NAME_WORDS = {
    "to", "and", "of", "the", "for", "at", "on", "in",
    "duplication", "upgrade", "widening", "realignment", "interchange",
    "overpass", "underpass", "roundabout", "reconstruction",
    "rehabilitation", "renewal", "extension", "corridor", "bypass",
    "intersection", "stormwater", "pipeline",
    "creek", "river", "railway", "highway", "junction", "crossing",
    "catchment", "precinct", "package",
}


def _looks_like_person_name(name: str) -> bool:
    """
    A light sanity check to keep obviously-not-a-person strings out of the
    auto-suggested name pool (dedupe_names/cv_derived_names). Rejects a
    candidate if any of its words is one from _NOT_A_NAME_WORDS. This only
    screens what gets auto-suggested in dropdowns -- the user can still type
    any name directly via the "type a name" option, so a false rejection here
    is never a hard block, just a missing suggestion.
    """
    words = [w.lower() for w in (name or "").split()]
    return bool(words) and not any(w in _NOT_A_NAME_WORDS for w in words)


def normalize_name_key(name: str) -> str:
    """
    A comparison key for "is this the same person" that's tolerant of the
    trivial spelling variants that show up between different name SOURCES in
    this app -- a filename-derived name (mechanically built from
    underscore-separated segments) vs. an AI-read name (reproducing however
    the CV itself writes it) frequently differ only in a hyphen vs. a space
    (e.g. "Andres Moreno Lara" vs. "Andres Moreno-Lara") or in extra
    whitespace. Without normalising before comparing, those come out as two
    different "people" -- duplicated in every name dropdown, and (worse)
    silently splitting one real person's profile data across two identities
    depending on which spelling happens to be assigned where.

    Lower-cases, then treats hyphens/underscores as word separators the same
    as spaces, then collapses repeated whitespace. Used everywhere two names
    are compared for "same person" -- dedupe_names, personnel_profiles_deduped,
    and team_bios._match_name_to_cv_file -- so all three agree on identity.
    """
    import re as _re

    key = (name or "").strip().lower()
    key = _re.sub(r"[-_]+", " ", key)
    key = _re.sub(r"\s+", " ", key)
    return key.strip()


def dedupe_names(names: list[str]) -> list[str]:
    """
    Clean a merged pool of candidate names: de-duplication that's tolerant of
    hyphen/space/case variants of the same name (see normalize_name_key --
    "Andres Moreno Lara" and "Andres Moreno-Lara" collapse to one entry, not
    two), then collapse a bare first-name into its fuller form when there's
    exactly one match (e.g. drop "David" when "David Smith" is also present,
    but keep a bare "David" if two "David ..." people exist, since it's then
    ambiguous). Also drops any candidate that doesn't look like a person's
    name at all (see _looks_like_person_name) -- e.g. a reference-project
    title that ended up in the CV filename list. Order is preserved (first
    occurrence, and its exact spelling, wins).
    """
    ordered: list[str] = []
    seen = set()
    for n in names or []:
        clean = (n or "").strip()
        key = normalize_name_key(clean)
        if clean and key not in seen and _looks_like_person_name(clean):
            seen.add(key)
            ordered.append(clean)

    result: list[str] = []
    for n in ordered:
        if len(n.split()) == 1:
            first = normalize_name_key(n)
            fuller = [m for m in ordered if m != n and normalize_name_key(m).split()[:1] == [first]]
            if len(fuller) == 1:
                continue  # the single fuller name covers this bare first name
        result.append(n)
    return result


def cv_derived_names(team_members: list | None, extra_names: list[str] | None = None) -> list[str]:
    """
    The pick-list of people the user can assign to slots. Drawn from team-member
    bios already drafted from the CV library (each has a .name), plus any names
    the user has typed elsewhere. De-duplicated, blanks removed, order preserved.
    Someone without a CV is handled in the app by letting the user type a name
    that isn't on this list -- this function only builds the known-names list.
    """
    names = [(getattr(m, "name", "") or "") for m in (team_members or [])]
    names += list(extra_names or [])
    return dedupe_names(names)


# ---------------------------------------------------------------------------
# AI-assisted "include in proposal" recommendation -- see include_in_proposal
# on ResourceAssignment and export_docx._build_personnel_profiles, which
# filters on it. This never decides FOR the user; it only pre-ticks/pre-unticks
# the checkbox in the Team & Resourcing tab and leaves a short reason. Nothing
# here changes staffing, the org chart, or the fee build-up -- it only affects
# whether a discipline gets a full pen-pic profile in the page-limited Key
# Personnel section.
# ---------------------------------------------------------------------------

_INCLUSION_SYSTEM_MESSAGE = """You are advising a proposals team at an engineering/\
infrastructure consultancy on which discipline leads should get a full Key Personnel \
profile (a photo plus a detailed write-up, which takes real page space) in a \
page-limited tender response. For EACH discipline role listed, judge whether that \
discipline is central enough to the brief's ACTUAL scope to justify featuring its own \
profile, versus a discipline that is only marginally touched on and can be left out of \
the Key Personnel section without weakening the bid (that person is still on the job and \
still appears in the org chart/fee build-up either way -- this is purely about whether \
they get a dedicated profile). Judge strictly from the scope material given below -- never \
assume a "typical" project team or a discipline's general importance in the industry; a \
role is only recommended if the scope material actually supports it. Keep each reason to \
one short, concrete sentence tied to the scope."""

_INCLUSION_PROMPT_TEMPLATE = """PROJECT SCOPE:
{project_scope}

DISCIPLINES THE BRIEF NAMES:
{disciplines}

SCOPE ITEMS (title: tasks):
{scope_items}

DISCIPLINE LEAD ROLES TO JUDGE (return one verdict for EACH, using the exact text given):
{roles}

Return a JSON object:
{{
  "roles": [
    {{"slot": string (exactly as given above), "recommended": boolean, "reason": string (one short sentence, grounded in the scope above)}}
  ]
}}"""


def suggest_proposal_inclusion(
    plan: list, analysis=None, config: dict | None = None,
) -> dict[str, dict]:
    """
    Recommend which Key Personnel slots should be ticked "include in proposal".

    The three firm leadership roles (FIRM_MANAGEMENT_ROLES) are always recommended
    True with the fixed FIRM_LEADERSHIP_REASON note -- there's nothing for the AI to
    judge there, they're core team regardless of scope. Every discipline slot is then
    judged against THIS project's real scope (analysis.project_scope /
    disciplines_involved / scope_items) by one AI call -- e.g. a bridge-over-creek
    brief should come back recommending Bridges / Hydraulics & Hydrology /
    Geotechnical, but not Cultural Heritage or Lighting unless the brief actually
    touches on them.

    Returns {slot: {"recommended": bool, "reason": str}} covering every slot in
    `plan` (management + discipline). Never mutates `plan` and never raises --
    on any AI failure (no key configured, call error, bad JSON) every discipline
    slot falls back to recommended=True with an explanatory reason, so a broken
    AI call never silently drops someone from the proposal. The caller (app.py)
    applies the result to session state, and the checkbox always stays
    user-overridable regardless of what's recommended here.
    """
    result: dict[str, dict] = {}
    discipline_slots: list[str] = []
    for a in plan or []:
        if a.slot_kind == "management":
            if a.slot in FIRM_MANAGEMENT_ROLES:
                result[a.slot] = {"recommended": True, "reason": FIRM_LEADERSHIP_REASON}
            # else: the client's own PM (CLIENT_ROLE) -- not a firm profile, skip.
            continue
        if a.slot not in discipline_slots:
            discipline_slots.append(a.slot)

    if not discipline_slots:
        return result

    if analysis is None:
        for slot in discipline_slots:
            result[slot] = {
                "recommended": True,
                "reason": "No tender analysis available yet to judge relevance against -- recommended by default.",
            }
        return result

    scope_items = getattr(analysis, "scope_items", None) or []
    scope_items_text = "\n".join(
        f"- {(getattr(si, 'title', '') or '').strip()}: {'; '.join(getattr(si, 'tasks', None) or [])}"
        for si in scope_items
    ) or "(none extracted)"

    prompt = _INCLUSION_PROMPT_TEMPLATE.format(
        project_scope=(getattr(analysis, "project_scope", "") or "").strip() or "(not extracted)",
        disciplines=", ".join(getattr(analysis, "disciplines_involved", None) or []) or "(none extracted)",
        scope_items=scope_items_text,
        roles="\n".join(f"- {s}" for s in discipline_slots),
    )

    try:
        data = call_ai_json(prompt, system_message=_INCLUSION_SYSTEM_MESSAGE, config=config, max_tokens=2000)
    except Exception:
        for slot in discipline_slots:
            result[slot] = {
                "recommended": True,
                "reason": "AI recommendation unavailable -- recommended by default; review and untick anything not needed.",
            }
        return result

    by_slot: dict[str, dict] = {}
    raw_roles = data.get("roles", []) if isinstance(data, dict) else []
    for item in raw_roles:
        if isinstance(item, dict) and (item.get("slot") or "").strip():
            by_slot[item["slot"].strip()] = item

    for slot in discipline_slots:
        item = by_slot.get(slot)
        if item is not None:
            result[slot] = {
                "recommended": bool(item.get("recommended", True)),
                "reason": (item.get("reason") or "").strip() or "No reason given by the AI.",
            }
        else:
            result[slot] = {
                "recommended": True,
                "reason": "Not covered by the AI's response -- recommended by default.",
            }
    return result
