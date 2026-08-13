"""
project_store.py

Save/load an entire in-progress proposal project to/from a single .zip file.
Everything in app.py's session state otherwise lives only in memory for the
current browser tab (see _init_state()) -- closing the tab, restarting the
app, or the machine sleeping loses it all. This module is what lets someone
pick a project back up later, or hand it to a colleague.

Deliberately, on principle rather than oversight, NEVER saved: anything
under `ai_config` (the API key) or `copilot_*` (client ID, tenant ID, sign-in
token). A saved project file might get emailed around or sit in a shared
drive; a credential riding along with it would be a real problem. AI
provider settings and any Copilot sign-in must be re-entered after loading.

Streamlit-free, like the rest of modules/ -- app.py reads/writes
st.session_state and hands this module plain values, never the other way
around.

Shape of the .zip:
  project.json        Every JSON-safe field, plus every pydantic/dataclass
                       object serialised via .model_dump()/dataclasses.asdict(),
                       plus a "_binary_manifest" telling load_project() which
                       image file in the zip belongs to which field.
  images/...           Every binary field (uploaded photos, generated banners,
                       the weighting chart, team headshots) as real files,
                       not base64-inflated into the JSON.

None vs. empty matters here: several session-state fields are `None` to mean
"this step hasn't been run yet" (e.g. `sections is None` gates the Proposal
Structure tab's buttons) and would be wrongly treated as "done, but empty"
if collapsed to `[]`/`{}` on save. save_project()/load_project() preserve
that distinction field-by-field rather than normalising it away.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict

from modules.tender_analyser import TenderAnalysis
from modules.weighting_engine import WeightedCriterion
from modules.page_allocation import PageAllocation
from modules.proposal_structure import ProposalSection
from modules.guidance_generator import GuidanceNote
from modules.compliance_matrix import ComplianceItem
from modules.gap_analysis import GapItem
from modules.draft_generator import SectionDraft
from modules.graphics_engine import GraphicRecommendation
from modules.fee_estimation_engine import DisciplineFeeEstimate, ScopeItemFee
from modules.team_bios import TeamMember
from modules.resourcing import ResourceAssignment, DisciplineFeeLine
from modules.reference_projects import ReferenceProject
from modules.document_processor import ExtractedDocument
from modules.executive_summary import ExecutiveSummary
from modules.team_intro import TeamIntro
from modules.experience_intro import ExperienceIntro
from modules.pitch_review import PitchReview

PROJECT_FILE_VERSION = 1

# Keys copied verbatim -- already JSON-safe plain data (str/int/float/bool,
# or a list/dict made only of those).
PLAIN_KEYS = [
    "project_name", "client_name", "tender_name", "submission_date_input", "bidder_name",
    "proposal_theme", "project_type", "company_material_text", "company_material_files",
    "company_uploaded_flags",
    "quotes", "section_divider_config", "proposal_format",
    "letter_sender_name", "letter_sender_title", "letter_sender_phone", "letter_sender_email",
    "terms_of_engagement_text", "team_bio_warnings",
    "fee_seed_total", "program_num_weeks", "program_schedule", "program_week_labels",
    "resource_extra_names", "cv_library_filenames", "cv_extracted_names", "dismissed_disciplines",
    "body_font", "reference_project_warnings", "dismissed_fee_disciplines",
    "fee_estimate_manual_total", "project_differentiator", "project_sales_pitch",
    # Bookkeeping app.py uses to detect a stale Proposal Structure (see
    # _structure_format_stale() there) -- MUST travel with "sections" and
    # "proposal_format" or a reopened project falsely looks stale: without
    # this, reloading resets it to None (via _init_state()'s default) while
    # "proposal_format" and "sections" both restore correctly, so the two
    # values never match and the "format changed" warning fires even though
    # nothing was actually changed. Confirmed this exact false positive from
    # a user report before adding this key.
    "_sections_built_format",
]

# key -> model class, for a single optional pydantic instance (None means "not run yet").
MODEL_SINGLE = {
    "analysis": TenderAnalysis,
    "executive_summary": ExecutiveSummary,
    "team_intro": TeamIntro,
    "experience_intro": ExperienceIntro,
    "pitch_review": PitchReview,
}

# key -> model class, for an optional list[Model] (None, not [], means "not run yet").
MODEL_LIST = {
    "weighted_criteria": WeightedCriterion,
    "allocations": PageAllocation,
    "sections": ProposalSection,
    "compliance_items": ComplianceItem,
    "gap_items": GapItem,
    "graphics": GraphicRecommendation,
    "fee_estimates": DisciplineFeeEstimate,
    "team_members": TeamMember,
    "scope_item_fees": ScopeItemFee,
    "resource_plan": ResourceAssignment,
    "discipline_fee_lines": DisciplineFeeLine,
    "reference_projects": ReferenceProject,
}

# key -> model class, for an optional dict[str, Model] (None, not {}, means "not run yet").
MODEL_DICT = {
    "guidance_notes": GuidanceNote,
    "drafts": SectionDraft,
}

# key -> dataclass, single optional instance.
DATACLASS_SINGLE = {"tender_extracted": ExtractedDocument}

# Binary fields, written into the zip as real files rather than JSON.
BINARY_SINGLE = ["cover_hero_png", "weighting_chart_png", "org_chart_png"]  # bytes | None
BINARY_LIST = ["project_photo_bytes", "branding_bytes"]          # list[bytes]
BINARY_DICT = [
    "divider_images", "team_photos", "personnel_photos", "reference_project_photos",
    # Returnable schedules (raw DOCX/XLSX bytes) unpacked from a tender
    # package ZIP -- see modules/package_intake.py; consumed by the
    # schedule filler. Saved with the project so a package uploaded once
    # keeps its schedules across save/load.
    "returnable_schedule_files",
]  # dict[str, bytes]


class ProjectLoadError(Exception):
    """The uploaded file isn't a project this tool saved, or is corrupted."""


def save_project(state) -> bytes:
    """
    `state`: anything with a `.get(key, default=None)` method -- in practice
    st.session_state itself, passed straight through from app.py. Returns
    the raw bytes of a .zip file, ready to hand to st.download_button().
    """
    payload = {"version": PROJECT_FILE_VERSION}

    for key in PLAIN_KEYS:
        payload[key] = state.get(key)

    for key, _cls in MODEL_SINGLE.items():
        obj = state.get(key)
        payload[key] = obj.model_dump() if obj is not None else None

    for key, _cls in MODEL_LIST.items():
        items = state.get(key)
        payload[key] = None if items is None else [item.model_dump() for item in items]

    for key, _cls in MODEL_DICT.items():
        items = state.get(key)
        payload[key] = None if items is None else {k: v.model_dump() for k, v in items.items()}

    for key, _cls in DATACLASS_SINGLE.items():
        obj = state.get(key)
        payload[key] = asdict(obj) if obj is not None else None

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        binary_manifest: dict = {}

        for key in BINARY_SINGLE:
            blob = state.get(key)
            if blob:
                filename = f"images/{key}.bin"
                zf.writestr(filename, blob)
                binary_manifest[key] = filename

        for key in BINARY_LIST:
            blobs = state.get(key) or []
            filenames = []
            for i, blob in enumerate(blobs):
                filename = f"images/{key}/{i}.bin"
                zf.writestr(filename, blob)
                filenames.append(filename)
            binary_manifest[key] = filenames

        for key in BINARY_DICT:
            blobs = state.get(key) or {}
            entries = []
            for i, (orig_key, blob) in enumerate(blobs.items()):
                filename = f"images/{key}/{i}.bin"
                zf.writestr(filename, blob)
                entries.append({"key": orig_key, "file": filename})
            binary_manifest[key] = entries

        payload["_binary_manifest"] = binary_manifest
        zf.writestr("project.json", json.dumps(payload, indent=2))

    return zip_buffer.getvalue()


def load_project(zip_bytes: bytes) -> dict:
    """
    Returns a plain dict of {session_state_key: value}, ready for app.py to
    assign back onto st.session_state. Every key this module manages is
    always present in the result (with None/[]/{} where the original project
    hadn't reached that step), so loading fully replaces prior project state
    for these keys rather than merging with whatever was there before.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            payload = json.loads(zf.read("project.json"))
    except zipfile.BadZipFile as exc:
        raise ProjectLoadError("This doesn't look like a project file (not a zip archive).") from exc
    except KeyError as exc:
        raise ProjectLoadError(f"This doesn't look like a project file (missing {exc}).") from exc
    except json.JSONDecodeError as exc:
        raise ProjectLoadError(f"This doesn't look like a project file (corrupt project.json: {exc}).") from exc

    result: dict = {}
    for key in PLAIN_KEYS:
        if key in payload:
            result[key] = payload[key]

    for key, cls in MODEL_SINGLE.items():
        data = payload.get(key)
        result[key] = cls.model_validate(data) if data else None

    for key, cls in MODEL_LIST.items():
        raw = payload.get(key)
        result[key] = None if raw is None else [cls.model_validate(item) for item in raw]

    for key, cls in MODEL_DICT.items():
        raw = payload.get(key)
        result[key] = None if raw is None else {k: cls.model_validate(v) for k, v in raw.items()}

    for key, cls in DATACLASS_SINGLE.items():
        data = payload.get(key)
        result[key] = cls(**data) if data else None

    manifest = payload.get("_binary_manifest", {})
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for key in BINARY_SINGLE:
                filename = manifest.get(key)
                result[key] = zf.read(filename) if filename else None

            for key in BINARY_LIST:
                result[key] = [zf.read(f) for f in manifest.get(key, [])]

            for key in BINARY_DICT:
                result[key] = {entry["key"]: zf.read(entry["file"]) for entry in manifest.get(key, [])}
    except KeyError as exc:
        raise ProjectLoadError(f"Project file is missing an image it references ({exc}).") from exc

    return result
