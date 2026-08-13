"""
package_intake.py

Tender-package ZIP intake: real tenders rarely arrive as one tidy PDF --
they arrive as a ZIP holding the main brief, addenda, returnable schedules,
drawings, and assorted other material. This module unpacks such a ZIP,
classifies each file, and hands back a structured result app.py can feed
into the existing flows:

  - brief + addenda      -> extracted and combined into the normal Tender
                            Analysis path (document_processor)
  - returnable schedules -> listed separately, raw bytes kept, for the
                            schedule-filling feature (returnable_schedules.py)
  - drawings             -> skipped, with a note (nothing useful for a text
                            analysis in a DWG/DXF or a plan sheet)
  - other/unreadable     -> listed with a plain-language reason and, for
                            unreadable files, a "send us this file" mailto

Design rules (mirroring the rest of the app):
  - NOTHING in here may raise for a bad input file. A messy real-world ZIP
    must round-trip into a coherent result with human-readable notes, never
    a stack trace. Only a truly unreadable ZIP returns a result whose
    `fatal_error` is set -- and that's a message, not an exception.
  - Classification is heuristic (extension first, filename keywords next,
    content keywords last) and always says WHY it decided what it decided,
    so the user can re-file anything it got wrong.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field

from modules import document_processor

SUPPORT_EMAIL = "hello@civilproposals.com"

# --- Guards ----------------------------------------------------------------
# Compressed ZIPs can lie about their size (zip bombs) -- cap what we're
# willing to unpack, and cap individual files. These are generous for real
# tender packages (the largest real packages seen are tens of MB).
MAX_TOTAL_UNCOMPRESSED_MB = 300
MAX_SINGLE_FILE_MB = 60
MAX_FILES = 200

# Above this many combined pages of brief + addenda, analysis still runs but
# the user gets a clear heads-up first (long analyses are slow and chunked).
COMBINED_PAGE_WARN_THRESHOLD = 200

CATEGORY_LABELS = {
    "brief": "Tender brief",
    "addendum": "Addendum / clarification",
    "schedule": "Returnable schedule / form",
    "drawing": "Drawing",
    "other": "Other document",
    "unreadable": "Couldn't be read",
}

DRAWING_EXTENSIONS = {"dwg", "dxf", "dgn", "shp", "shx", "dbf", "ifc", "rvt", "skp", "12d", "12da"}
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "webp", "heic"}
SPREADSHEET_EXTENSIONS = {"xlsx", "xlsm", "xls", "csv"}
DOCUMENT_EXTENSIONS = {"pdf", "docx", "doc", "txt", "rtf"}
IGNORED_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}

_ADDENDUM_PATTERNS = [
    r"addend", r"clarificat", r"notice\s*to\s*tenderers?", r"\bntt\b", r"q\s*&\s*a",
    r"questions?\s*(and|&)\s*answers?", r"amendment",
]
_SCHEDULE_PATTERNS = [
    r"returnable", r"schedule", r"\bform\b", r"response\s*template", r"pricing",
    r"\bboq\b", r"bill\s*of\s*quantities", r"rates?\b", r"tender\s*form",
    r"declaration", r"statutory", r"\bsch\d", r"attachment\s*[a-z0-9]+\s*[-_ ]\s*(form|schedule)",
]
_BRIEF_PATTERNS = [
    r"request\s*for\s*(tender|quote|quotation|proposal)", r"\brft\b", r"\brfq\b",
    r"\brfp\b", r"\beoi\b", r"invitation\s*to\s*(tender|offer)", r"scope\s*of\s*works?",
    r"\bbrief\b", r"conditions\s*of\s*(tender|contract)", r"specification", r"\bspec\b",
    r"statement\s*of\s*requirements?", r"principal'?s?\s*project\s*requirements",
]
_DRAWING_NAME_PATTERNS = [r"\bdrawings?\b", r"\bplans?\b", r"sketch", r"\bdwg\b", r"\bfigure\b"]


@dataclass
class ClassifiedFile:
    """One file out of the package, with its classification and (for brief/
    addendum files) the extracted text."""
    filename: str                      # path inside the ZIP
    category: str                      # key of CATEGORY_LABELS
    reason: str                        # human-readable "why it was filed here"
    file_bytes: bytes | None = None    # kept for schedules (Batch-5 filling); None elsewhere
    extracted: "document_processor.ExtractedDocument | None" = None
    size_bytes: int = 0


@dataclass
class PackageIntakeResult:
    briefs: list[ClassifiedFile] = field(default_factory=list)
    addenda: list[ClassifiedFile] = field(default_factory=list)
    schedules: list[ClassifiedFile] = field(default_factory=list)
    drawings: list[ClassifiedFile] = field(default_factory=list)
    others: list[ClassifiedFile] = field(default_factory=list)
    unreadable: list[ClassifiedFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fatal_error: str | None = None     # set ONLY when the ZIP itself can't be opened

    def all_files(self) -> list[ClassifiedFile]:
        return self.briefs + self.addenda + self.schedules + self.drawings + self.others + self.unreadable


def support_mailto(filename: str) -> str:
    """A 'send us this file' mailto link for a file we couldn't process."""
    subject = f"CivilProposals -- please help with this tender file: {filename}"
    body = (
        "Hi CivilProposals team,%0D%0A%0D%0AThe attached tender file couldn't be processed "
        "in the app. Could you take a look?%0D%0A%0D%0A(Please attach the file to this "
        "email before sending.)"
    )
    subject = subject.replace(" ", "%20")
    return f"mailto:{SUPPORT_EMAIL}?subject={subject}&body={body}"


def process_zip(zip_bytes: bytes, zip_name: str = "package.zip") -> PackageIntakeResult:
    """Unpack + classify a tender-package ZIP. Never raises for bad content;
    see the module docstring."""
    result = PackageIntakeResult()

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except Exception:
        result.fatal_error = (
            f"'{zip_name}' doesn't appear to be a readable ZIP file -- it may be corrupted, "
            f"or renamed from another format. Try re-downloading it from the tender portal, "
            f"or email it to {SUPPORT_EMAIL} and we'll take a look."
        )
        return result

    try:
        infos = [i for i in zf.infolist() if not i.is_dir()]
    except Exception:
        result.fatal_error = (
            f"'{zip_name}' could be opened but its file list couldn't be read -- the archive "
            f"looks damaged. Try re-downloading it, or email it to {SUPPORT_EMAIL}."
        )
        return result

    # --- Guards ---
    if len(infos) > MAX_FILES:
        result.warnings.append(
            f"This package contains {len(infos)} files -- only the first {MAX_FILES} were "
            f"looked at. If something important was missed, upload it individually."
        )
        infos = infos[:MAX_FILES]

    total_uncompressed = sum(i.file_size for i in infos)
    if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_MB * 1024 * 1024:
        result.fatal_error = (
            f"This package unpacks to about {total_uncompressed // (1024*1024)} MB, which is "
            f"over the {MAX_TOTAL_UNCOMPRESSED_MB} MB limit for a single upload. Upload the "
            f"main brief and addenda individually instead (drawings usually aren't needed "
            f"for the analysis), or email the package to {SUPPORT_EMAIL}."
        )
        return result

    for info in infos:
        name = info.filename
        base = name.rsplit("/", 1)[-1]
        if base.lower() in IGNORED_NAMES or base.startswith("~$") or base.startswith("."):
            continue  # OS/temp junk -- silently skipped

        if info.file_size > MAX_SINGLE_FILE_MB * 1024 * 1024:
            result.others.append(ClassifiedFile(
                filename=name, category="other", size_bytes=info.file_size,
                reason=(f"Skipped -- {info.file_size // (1024*1024)} MB is over the "
                        f"{MAX_SINGLE_FILE_MB} MB per-file limit. If this file matters for the "
                        f"analysis, email it to {SUPPORT_EMAIL}."),
            ))
            continue

        try:
            file_bytes = zf.read(info)
        except Exception as exc:
            result.unreadable.append(ClassifiedFile(
                filename=name, category="unreadable", size_bytes=info.file_size,
                reason=(f"This file couldn't be extracted from the ZIP ({_short(exc)}) -- it may "
                        f"be corrupted, or the ZIP may be password-protected."),
            ))
            continue

        classified = _classify_file(name, base, file_bytes)
        getattr(result, _bucket_for(classified.category)).append(classified)

    if not result.all_files():
        result.warnings.append(
            "The ZIP was read fine but contained no usable files -- no brief, addenda, "
            "schedules, or drawings were found inside it."
        )

    # Page-count guard across everything headed for analysis.
    combined_pages = sum(
        (f.extracted.page_count or 0) for f in result.briefs + result.addenda if f.extracted
    )
    if combined_pages > COMBINED_PAGE_WARN_THRESHOLD:
        result.warnings.append(
            f"The brief and addenda in this package total about {combined_pages} pages -- "
            f"that's a big analysis, so expect it to take several minutes. If parts of the "
            f"package aren't actually needed (e.g. standard conditions of contract), removing "
            f"them and re-uploading will be faster and more focused."
        )

    return result


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _bucket_for(category: str) -> str:
    return {
        "brief": "briefs", "addendum": "addenda", "schedule": "schedules",
        "drawing": "drawings", "other": "others", "unreadable": "unreadable",
    }.get(category, "others")


def _matches_any(text: str, patterns: list[str]) -> str | None:
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return pat
    return None


def _short(exc: Exception) -> str:
    return str(exc).strip().splitlines()[0][:120] if str(exc).strip() else type(exc).__name__


class _BytesUpload:
    """Minimal Streamlit-UploadedFile-alike for document_processor."""
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def _pdf_is_encrypted(file_bytes: bytes) -> bool:
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        needs = bool(doc.needs_pass)
        doc.close()
        return needs
    except Exception:
        return False  # not encrypted -- just unreadable; caller handles that


def _classify_file(name: str, base: str, file_bytes: bytes) -> ClassifiedFile:
    """Extension first, filename keywords next, extracted-content keywords
    last. Never raises."""
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    lower_name = name.lower()
    size = len(file_bytes)

    # --- Pure-extension categories ---
    if ext in DRAWING_EXTENSIONS:
        return ClassifiedFile(
            filename=name, category="drawing", size_bytes=size,
            reason=f"CAD/model file (.{ext}) -- drawings aren't used in the text analysis, so this was set aside.",
        )
    if ext in IMAGE_EXTENSIONS:
        return ClassifiedFile(
            filename=name, category="drawing", size_bytes=size,
            reason=(f"Image file (.{ext}) -- treated as a drawing/figure and set aside. If this is "
                    f"actually a scanned page of the brief, upload it as a PDF so OCR can read it."),
        )
    if ext == "zip":
        return ClassifiedFile(
            filename=name, category="other", size_bytes=size,
            reason="A ZIP inside the ZIP -- nested archives aren't unpacked automatically. Extract it and upload its contents if they matter.",
        )
    if ext in SPREADSHEET_EXTENSIONS:
        matched = _matches_any(lower_name, _SCHEDULE_PATTERNS)
        return ClassifiedFile(
            filename=name, category="schedule", file_bytes=file_bytes, size_bytes=size,
            reason=("Spreadsheet" + (f" whose name matches '{matched}'" if matched else "")
                    + " -- filed as a returnable schedule (pricing/rates/response forms usually are)."),
        )
    if ext not in DOCUMENT_EXTENSIONS:
        return ClassifiedFile(
            filename=name, category="other", size_bytes=size,
            reason=f"Unrecognised file type (.{ext or 'no extension'}) -- set aside.",
        )

    # Legacy Office formats: can't be parsed by the extractors used here.
    if ext in ("doc", "rtf"):
        return ClassifiedFile(
            filename=name, category="other", size_bytes=size,
            reason=(f"Legacy Word format (.{ext}) -- please re-save it as .docx (File > Save As in "
                    f"Word) and upload it individually, or email it to {SUPPORT_EMAIL}."),
        )

    # Password-protected PDF: a specific, human answer, not a generic failure.
    if ext == "pdf" and _pdf_is_encrypted(file_bytes):
        return ClassifiedFile(
            filename=name, category="unreadable", size_bytes=size,
            reason=("This PDF is password-protected, so its text can't be read. If you have the "
                    "password, open it in a PDF viewer, save an unlocked copy (usually Print > "
                    f"Save as PDF), and upload that -- or email the file to {SUPPORT_EMAIL}."),
        )

    # --- Filename keywords ---
    if _matches_any(lower_name, _ADDENDUM_PATTERNS):
        category_by_name = "addendum"
    elif _matches_any(lower_name, _SCHEDULE_PATTERNS):
        category_by_name = "schedule"
    elif _matches_any(lower_name, _DRAWING_NAME_PATTERNS):
        return ClassifiedFile(
            filename=name, category="drawing", size_bytes=size,
            reason="Filename looks like a drawing/plan set -- set aside (not used in the text analysis).",
        )
    elif _matches_any(lower_name, _BRIEF_PATTERNS):
        category_by_name = "brief"
    else:
        category_by_name = None

    # Returnable schedules keep their BYTES (needed to fill them later) and
    # skip text extraction -- their content isn't part of the brief analysis.
    if category_by_name == "schedule":
        return ClassifiedFile(
            filename=name, category="schedule", file_bytes=file_bytes, size_bytes=size,
            reason="Filename matches a returnable schedule/form -- kept aside for schedule filling, not mixed into the brief analysis.",
        )

    # --- Extract text (also validates readability) ---
    try:
        extracted = document_processor.extract_text_from_file(_BytesUpload(base, file_bytes))
    except Exception as exc:  # extract_text_from_file shouldn't raise, but never trust that here
        return ClassifiedFile(
            filename=name, category="unreadable", size_bytes=size,
            reason=(f"This file couldn't be read ({_short(exc)}). It may be corrupted -- try "
                    f"re-downloading it, or email it to {SUPPORT_EMAIL}."),
        )
    if extracted.warning and not extracted.text:
        reason = extracted.warning
        if reason.startswith("Could not read"):
            # document_processor's generic failure line -- add the human
            # "what now" that every other unreadable path here carries.
            reason = (
                f"This file couldn't be read -- it looks corrupted or incomplete. Try "
                f"re-downloading it from the tender portal, or email it to {SUPPORT_EMAIL} "
                f"and we'll process it for you. (Technical detail: {reason})"
            )
        return ClassifiedFile(
            filename=name, category="unreadable", size_bytes=size,
            reason=reason,
        )

    # --- Content keywords (first couple of pages) ---
    head = (extracted.text or "")[:6000].lower()
    if category_by_name is None:
        if _matches_any(head, _ADDENDUM_PATTERNS):
            category_by_name = "addendum"
        elif _matches_any(head, _BRIEF_PATTERNS):
            category_by_name = "brief"
        elif _matches_any(head, _SCHEDULE_PATTERNS) and _looks_like_form(extracted):
            return ClassifiedFile(
                filename=name, category="schedule", file_bytes=file_bytes, size_bytes=size,
                reason="Content reads like a response form/schedule (schedule wording plus mostly-empty tables).",
            )
        else:
            category_by_name = "other"

    reason = {
        "brief": "Filed as (part of) the tender brief -- included in the analysis.",
        "addendum": "Reads as an addendum/clarification -- included in the analysis alongside the brief.",
        "other": "Couldn't be confidently matched to brief/addendum/schedule/drawing -- set aside. Upload it with the brief if it should be analysed.",
    }[category_by_name]

    return ClassifiedFile(
        filename=name, category=category_by_name, size_bytes=size,
        extracted=extracted if category_by_name in ("brief", "addendum") else None,
        file_bytes=None,
        reason=reason,
    )


def _looks_like_form(extracted) -> bool:
    """True when a document's tables are mostly empty cells -- the signature
    of a fill-me-in response form rather than an information document."""
    total_cells = 0
    empty_cells = 0
    for table in extracted.tables or []:
        for row in table.get("rows", []):
            for cell in row:
                total_cells += 1
                if not (cell or "").strip():
                    empty_cells += 1
    return total_cells >= 8 and empty_cells / max(total_cells, 1) >= 0.4
