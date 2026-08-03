"""
team_bios.py

Drafts short team-member bios in the three-line format real letter proposals
use (Qualified / Connected / Relevance to project), from CVs the user has
actually uploaded -- never invented. The AI's job here is compression and
formatting of real facts already in the CV text, not generating new claims;
the draft is always shown to the user to review and correct before it's used
(see the SYSTEM_MESSAGE below and app.py's review step).

Headshot photos are handled separately in app.py/session_state (raw bytes,
same pattern as project photos) rather than through this module's pydantic
model, since they're binary assets the user uploads and assigns per person.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from modules.ai_interface import call_ai_json

SYSTEM_MESSAGE = """You are compressing real CVs into short bios for a fee proposal letter, \
in this exact three-line format:
- "Qualified": degrees/qualifications and the year, exactly as stated in the CV.
- "Connected": professional memberships, registrations, chartered status (e.g. RPEQ, \
CPEng, MIEAust) exactly as stated.
- "Relevance to project": 2-4 sentences on their relevant experience, drawing only on \
projects and skills actually described in their CV.
You must not invent a qualification, membership, year, or project that isn't in the source \
text. If a CV doesn't clearly state something (e.g. no membership found), leave that field as \
an empty string rather than guessing. If you cannot confidently identify where one person's \
CV ends and another begins, say so in a warning rather than merging two people into one bio."""

PROMPT_TEMPLATE = """Below is CV / company profile material the user uploaded, which may \
contain one or more people's CVs concatenated together. Identify each distinct person and \
produce a bio for each in the required format.

Return a JSON object:
{{
  "team_members": [
    {{"name": string, "role": string, "qualified": string, "connected": string, "relevance_text": string}}
  ],
  "warnings": [string]
}}

"role" should be their job title/discipline role if stated (e.g. "Structural Engineer", \
"Project Manager") -- leave as an empty string if not clear from the text.

--- CV / PROFILE MATERIAL ---
{material}
--- END MATERIAL ---"""


class TeamMember(BaseModel):
    name: str
    role: str = ""
    qualified: str = ""
    connected: str = ""
    relevance_text: str = ""


def draft_team_bios_from_cv(
    cv_text: str, config: dict | None = None, max_chars: int = 24000
) -> tuple[list[TeamMember], list[str]]:
    """
    Draft candidate bios from uploaded CV/profile text. Returns (members, warnings) --
    always treat the result as a DRAFT: the app must let the user review and edit every
    field before it goes anywhere near an exported document, since CVs are exactly the
    kind of source material where a subtly wrong qualification or year matters.
    """
    material = (cv_text or "").strip()
    if not material:
        return [], ["No CV/company profile text was supplied -- nothing to draft from."]
    if len(material) > max_chars:
        material = material[:max_chars] + "\n\n[...truncated for length...]"

    prompt = PROMPT_TEMPLATE.format(material=material)
    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=3000)

    raw_members = data.get("team_members", [])
    members = [TeamMember.model_validate(m) for m in raw_members]
    warnings = list(data.get("warnings", []))
    if not members:
        warnings.append("No individual team members could be confidently identified in the uploaded material.")
    return members, warnings


NAME_EXTRACTION_SYSTEM = (
    "You identify the distinct real people whose CVs/profiles appear in uploaded text. Return "
    "each person's FULL name -- given name(s) AND family name/surname -- exactly as written at "
    "the top of their CV. Never return a first name on its own if a surname is present, and "
    "never invent, guess, or complete a name. Do not include the client, referees, or people "
    "merely mentioned inside a project description -- only people whose own CV/profile is here. "
    "If you can tell a person's role/discipline from their CV, include it."
)

NAME_EXTRACTION_PROMPT = """Below is CV / company profile material that may contain several \
people's CVs concatenated together. List every distinct person whose own CV/profile appears \
in this text, giving each person's FULL name (given name and surname).

Return a JSON object:
{{
  "people": [
    {{"name": string, "role": string}}
  ]
}}
- "name": the person's COMPLETE name -- given name AND surname -- exactly as written. Never \
return a first name on its own. If the name at the top of a CV looks like only a first name, \
find the surname elsewhere in that same CV (it almost always appears in the page header/footer, \
an email address like firstname.surname@..., or a signature block) and use the full name.
- "role": their job title/discipline if stated, else an empty string.
Only include real people whose own CV/profile is in the text (not clients, referees, or people \
merely mentioned in a project). Include EVERYONE you find -- do not stop early or summarise.

--- CV / PROFILE MATERIAL ---
{material}
--- END MATERIAL ---"""


PROFILE_FIELDS_SYSTEM = """You are extracting factual Key Personnel profile details, for specific \
named people, from real CVs. You must not invent a qualification, registration, a number of years, \
or a project claim that isn't stated in the source text. If a fact isn't clearly stated in that \
person's own CV, leave the corresponding field as an empty string (or empty list) rather than \
guessing -- an empty field becomes an explicit placeholder in the document, which is the correct \
outcome when the CV doesn't say. In particular, never calculate "years of experience" from a \
graduation/qualification year -- only report it if the CV itself states a number of years of \
experience in words (e.g. "18 years' experience", "over 20 years in..."). Only produce an entry \
for a person if you can find text that is clearly THEIR OWN CV (matching their name) in the \
material -- skip anyone you can't confidently match, rather than guessing which section belongs \
to them."""

PROFILE_FIELDS_PROMPT = """Below is CV / company profile material, which may contain several \
people's CVs concatenated together. For each of the PEOPLE TO EXTRACT listed below, find their \
own CV in the material (match by name) and extract five fields, using only facts stated in that \
person's own CV text:

- "qualification": their ACADEMIC qualification(s) ONLY -- degrees, e.g. "Bachelor of Engineering \
(Civil) (Hons)" -- NOT professional registrations or memberships (RPEQ, CPEng, MIEAust, NER, \
FIEAust and similar belong in "rpeq_status" instead, never here). CVs often print a short combined \
line like "BEng, RPEQ, CPEng, NER, FIEAust" (e.g. in a name banner/header) -- if so, ONLY the \
degree abbreviation ("BEng") belongs in this field, not the registration letters that follow it. \
If a fuller statement of the SAME degree appears elsewhere in the CV (e.g. in a qualifications \
table: "Bachelor of Engineering (Civil) (Hons), University of Queensland, 2003"), use that fuller, \
more complete version instead of the bare abbreviation -- include institution and year if given \
anywhere in the CV. Empty string if no qualification is stated at all.
- "rpeq_status": their professional registration / chartered status / membership ONLY -- RPEQ, \
CPEng, MIEAust, NER, FIEAust and similar -- NOT academic qualifications/degrees (those belong in \
"qualification" instead, never here). If the CV prints a short combined line like "BEng, RPEQ, \
CPEng, NER, FIEAust", exclude the degree abbreviation ("BEng") and report only the registration/ \
membership part (e.g. "RPEQ, CPEng, NER, FIEAust"). If a REGISTRATION NUMBER for one of these is \
stated anywhere else in the CV (e.g. a qualifications/memberships table showing "RPEQ No. 12929"), \
use that fuller, numbered form instead of a bare abbreviation found elsewhere in the document -- \
scan the whole CV for the most complete statement of registration status, don't stop at the first \
mention. Empty string if the CV states none at all.
- "years_experience": their years of experience, but ONLY if the CV explicitly states a number of \
years in words (e.g. "18 years", "20+ years' experience") -- do not calculate this from a \
graduation year. Empty string if not explicitly stated.
- "value_to_project": the CONTINUATION of the sentence "On this project, [Name] will ..." -- \
i.e. what they will do / the value they bring, WITHOUT repeating the "On this project, [Name] \
will" opening (the document already prints that opening, so start directly with a verb, e.g. \
"lead the structural design, drawing on his role as Bridge Lead on the Bruce Highway Cooroy to \
Curra Section D and the Mackay Northern Access Upgrade, delivering complex integral and box \
girder bridge solutions for TMR..."). Two to three clauses. Must name AT LEAST ONE OR TWO SPECIFIC \
projects from their CV as concrete evidence, not just a general skills/proficiency/standards \
statement -- a claim like "proficient in TMR's Design Criteria" on its own is too generic; anchor \
it to real, named project experience from their CV (e.g. which project(s) they applied that on). \
Grounded only in real skills/background/experience/projects actually stated in their CV -- do not \
invent a specific task, deliverable, or project for THIS project that isn't grounded in their real \
experience.
- "relevant_projects": a list of up to 3 short strings, each naming one real project from their \
CV and (optionally) their role on it (e.g. "Cape River Bridge -- Detailed Design"). Only include \
projects actually named in their CV -- empty list if none can be confidently identified.

PEOPLE TO EXTRACT (only return entries for people in this list; skip anyone not on it, and skip \
anyone on it whose CV you can't confidently find in the material):
{names}

Return a JSON object:
{{
  "profiles": [
    {{"name": string, "qualification": string, "rpeq_status": string, "years_experience": string,
      "value_to_project": string, "relevant_projects": [string]}}
  ],
  "warnings": [string]
}}

--- CV / PROFILE MATERIAL ---
{material}
--- END MATERIAL ---"""

# Single-person variant used when the caller can hand over one person's own CV file in
# isolation (see extract_personnel_profile_fields' per-file path below). Asking about only
# one person, from only their own file, removes the failure mode where the AI attributes
# one person's background to a different name when several CVs are concatenated together
# in the same chunk -- there's no other person's text in the material for it to confuse
# this with.
SINGLE_PROFILE_SYSTEM = """You are extracting factual Key Personnel profile details for ONE named \
person from their own CV. You must not invent a qualification, registration, a number of years, or \
a project claim that isn't stated in the source text. If a fact isn't clearly stated, leave the \
corresponding field as an empty string (or empty list) rather than guessing. Never calculate \
"years of experience" from a graduation/qualification year -- only report it if the CV itself \
states a number of years of experience in words (e.g. "18 years' experience"). Everything you \
return must describe THIS person, {name} -- never attribute another person's background to them, \
even if other names appear in the material."""

SINGLE_PROFILE_PROMPT = """Below is {name}'s own CV. Extract five fields, using only facts \
stated in this text:

- "qualification": their ACADEMIC qualification(s) ONLY -- degrees, e.g. "Bachelor of Engineering \
(Civil) (Hons)" -- NOT professional registrations or memberships (RPEQ, CPEng, MIEAust, NER, \
FIEAust and similar belong in "rpeq_status" instead, never here). CVs often print a short combined \
line like "BEng, RPEQ, CPEng, NER, FIEAust" (e.g. in a name banner/header) -- if so, ONLY the \
degree abbreviation ("BEng") belongs in this field, not the registration letters that follow it. \
If a fuller statement of the SAME degree appears elsewhere in the CV (e.g. in a qualifications \
table: "Bachelor of Engineering (Civil) (Hons), University of Queensland, 2003"), use that fuller, \
more complete version instead of the bare abbreviation -- include institution and year if given \
anywhere in the CV. Empty string if no qualification is stated at all.
- "rpeq_status": their professional registration / chartered status / membership ONLY -- RPEQ, \
CPEng, MIEAust, NER, FIEAust and similar -- NOT academic qualifications/degrees (those belong in \
"qualification" instead, never here). If the CV prints a short combined line like "BEng, RPEQ, \
CPEng, NER, FIEAust", exclude the degree abbreviation ("BEng") and report only the registration/ \
membership part (e.g. "RPEQ, CPEng, NER, FIEAust"). If a REGISTRATION NUMBER for one of these is \
stated anywhere else in the CV (e.g. a qualifications/memberships table showing "RPEQ No. 12929"), \
use that fuller, numbered form instead of a bare abbreviation found elsewhere in the document -- \
scan the whole CV for the most complete statement of registration status, don't stop at the first \
mention. Empty string if the CV states none at all.
- "years_experience": ONLY if explicitly stated as a number of years in words (e.g. "18 years"). \
Empty string otherwise -- do not calculate it from a graduation year.
- "value_to_project": the CONTINUATION of the sentence "On this project, {name} will ..." -- \
what they will do / the value they bring, WITHOUT repeating the "On this project, {name} will" \
opening (the document already prints that opening, so start directly with a verb, e.g. "lead the \
structural design, drawing on his role as Bridge Lead on the Bruce Highway Cooroy to Curra Section \
D and the Mackay Northern Access Upgrade, delivering complex integral and box girder bridge \
solutions for TMR..."). Two to three clauses. Must name AT LEAST ONE OR TWO SPECIFIC projects from \
this CV as concrete evidence, not just a general skills/proficiency/standards statement -- a claim \
like "proficient in TMR's Design Criteria" on its own is too generic; anchor it to real, named \
project experience from this CV. Grounded only in real skills/background/experience/projects \
actually stated in this CV.
- "relevant_projects": a list of up to 3 short strings, each naming one real project from this CV \
and (optionally) their role on it (e.g. "Cape River Bridge -- Detailed Design"). Only include \
projects actually named in this CV -- empty list if none can be confidently identified.

Return a JSON object: {{"qualification": string, "rpeq_status": string, "years_experience": string,
"value_to_project": string, "relevant_projects": [string]}}

--- {name}'S CV ---
{material}
--- END CV ---"""


def _strip_value_prefix(value: str, name: str) -> str:
    """Strip a leading "On this project, <name> will[ ,:]" opening from a
    value_to_project string. The export prints that opening itself ("On this
    project, <name> will: ..."), so if the AI includes it too the exported
    line doubles up ("On this project, X will: On this project, X will ...").
    Defensive belt-and-braces alongside the prompt now asking for the
    continuation only. Also lower-cases the first surviving letter when the
    strip leaves a mid-sentence fragment, so it reads naturally after "will:".
    """
    import re as _re

    v = (value or "").strip()
    if not v:
        return v
    # "On this project, <any name> will[ ,:]" -- name-agnostic on purpose: the export
    # always prints the correct assigned name, so whatever name the AI put in the opening
    # (including a wrong one left over from old cross-attributed data) should be stripped.
    # The non-greedy .{0,40}? captures the name without swallowing the rest of the sentence.
    pattern = r"^on this project,?\s+.{0,40}?\bwill\b\s*[:,]?\s*"
    stripped = _re.sub(pattern, "", v, count=1, flags=_re.IGNORECASE)
    if stripped and stripped != v:
        stripped = stripped[0].lower() + stripped[1:] if len(stripped) > 1 else stripped.lower()
        return stripped.strip()
    return v


def _match_name_to_cv_file(name: str, cv_files: dict) -> str | None:
    """
    Find which file in a {filename: text} CV library store is this person's
    own CV. Returns None (never guesses) if it can't be resolved to exactly
    one file.

    Two passes, both safe against cross-attribution because each resolves to a
    single file (the AI is then only ever shown that one person's own CV).
    Both passes compare names via resourcing.normalize_name_key rather than a
    plain .lower() -- a filename-derived name ("Andres Moreno Lara", built
    mechanically from underscore-separated segments) and an AI-read name
    (reproducing however the CV itself spells it, e.g. "Andres Moreno-Lara")
    are the same real person but differ in a hyphen vs. a space; without
    normalising, that mismatch makes this function report "no match" for a
    person who very much does have a CV on file:

    1. Filename derivation -- the same filename -> candidate-name logic that
       populates the name-suggestion dropdowns (resourcing.names_from_filenames).
       A name that was itself suggested from a filename matches back to that
       exact file. This is the normal path.
    2. Full-name-in-text fallback -- for a name that doesn't derive from any
       filename (e.g. typed by hand, or taken from AI text extraction rather
       than a filename), find files whose text actually contains that full
       name. Used ONLY when it hits exactly one file; if the name appears in
       zero files (nobody) or two-plus files (ambiguous), returns None rather
       than risk attributing the wrong CV.
    """
    from modules.resourcing import names_from_filenames, normalize_name_key

    target = normalize_name_key(name)
    if not target:
        return None

    for filename in cv_files or {}:
        candidates = names_from_filenames([filename])
        if candidates and normalize_name_key(candidates[0]) == target:
            return filename

    # Fallback: exact full-name appears in the body of exactly one CV file --
    # normalizing the CV text the same way so a hyphen/space difference between
    # the assigned name and however the CV itself is written doesn't break the
    # match (see the docstring above).
    matches = [
        fn for fn, text in (cv_files or {}).items()
        if target in normalize_name_key(text or "")
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def cv_filenames_for_names(names, cv_files: dict) -> set:
    """Public batch wrapper around _match_name_to_cv_file -- resolves each name
    in `names` to its own CV file (if any) and returns the set of matched
    filenames. Used to strip a specific person's CV out of the material fed to
    downstream drafting once they've been excluded from the proposal, so their
    name/expertise can't leak into AI-drafted prose via the raw CV text even
    after they've been dropped from the nominated-team context."""
    matched = set()
    for name in names or []:
        filename = _match_name_to_cv_file(name, cv_files)
        if filename:
            matched.add(filename)
    return matched


def extract_personnel_profile_fields(
    cv_text: str, names: list[str], config: dict | None = None,
    chunk_chars: int = 12000, max_chunks: int = 24, cv_files: dict | None = None,
    max_chars_per_file: int = 32000,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """
    For each name in `names`, find (qualification, rpeq_status,
    years_experience, value_to_project, relevant_projects) -- the free-text
    fields the Key Personnel profile
    block in the export needs (see ResourceAssignment in resourcing.py).
    Returns (profiles, warnings), keyed by name.lower() so callers can match
    back to resource_plan rows.

    Two modes, depending on whether `cv_files` (the CV library's per-file
    {filename: text} store -- see app.py's Upload Documents tab) is supplied:

    - Per-file (preferred): each name is matched to its own CV file via
      _match_name_to_cv_file, and the AI is asked about ONLY that person,
      from ONLY their own file. This is deliberate: with several CVs
      concatenated into one blob, an AI call covering multiple people at
      once has, in practice, attributed one person's background to a
      different assigned name (e.g. describing person B's "will lead bridge
      design" experience under person A's name) -- there's no ambiguity for
      the model to get wrong when it only ever sees one person's file. A
      name with no matching file is skipped (recorded in warnings), not
      guessed at from the combined text.
    - Combined-text fallback (cv_files not supplied, e.g. an older project
      whose CV library was never split per-file): falls back to the previous
      chunked-search-of-the-whole-blob approach, which is less precise but
      still functional until the library is re-uploaded.

    Never invents a value: a field left blank stays blank, which the export
    then renders as an explicit bracketed placeholder rather than a guess.
    """
    clean_names = [n.strip() for n in (names or []) if (n or "").strip()]
    if not clean_names:
        return {}, ["No named people were supplied -- nothing to extract."]

    if cv_files:
        return _extract_profile_fields_per_file(clean_names, cv_files, config, max_chars_per_file)
    return _extract_profile_fields_from_combined_text(clean_names, cv_text, config, chunk_chars, max_chunks)


def _call_single_profile_with_retry(
    name: str, text: str, config: dict | None, max_attempts: int = 3,
) -> dict:
    """
    Call the single-person profile-fields prompt with a short retry/backoff
    loop, so a transient failure (an AI provider rate limit is the common
    case once you're processing 20-40 CVs back-to-back with no delay between
    calls) doesn't silently drop this one person for the whole batch -- which
    previously showed up as an unexplained empty pen pic with no way to tell
    whether the CV was bad or the call just got throttled.

    Raises the last exception if every attempt fails, so the caller can still
    record a real failure (as opposed to masking it forever).
    """
    import time

    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return call_ai_json(
                SINGLE_PROFILE_PROMPT.format(name=name, material=text),
                system_message=SINGLE_PROFILE_SYSTEM.format(name=name), config=config, max_tokens=900,
            )
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                time.sleep(1.5 * (attempt + 1))  # 1.5s, then 3s -- brief backoff, not a long stall
    raise last_exc


def _extract_profile_fields_per_file(
    names: list[str], cv_files: dict, config: dict | None, max_chars_per_file: int,
    delay_between_people: float = 0.4,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    import time

    profiles: dict[str, dict[str, str]] = {}
    warnings: list[str] = []
    unmatched: list[str] = []
    failed_people: list[str] = []

    for i, name in enumerate(names):
        matched_file = _match_name_to_cv_file(name, cv_files)
        if not matched_file:
            unmatched.append(name)
            continue
        text = (cv_files.get(matched_file) or "").strip()
        if not text:
            unmatched.append(name)
            continue
        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file] + "\n\n[...truncated for length...]"
        # A small pause between successive calls -- cheap insurance against
        # tripping a per-minute rate limit when a batch runs across 20-40
        # people, at negligible cost to total run time.
        if i > 0 and delay_between_people:
            time.sleep(delay_between_people)
        try:
            data = _call_single_profile_with_retry(name, text, config)
        except Exception as exc:
            failed_people.append(f"{name} ({exc})")
            continue
        if not isinstance(data, dict):
            failed_people.append(f"{name} (AI did not return a usable response)")
            continue
        profiles[name.lower()] = {
            "name": name,
            "qualification": (data.get("qualification") or "").strip(),
            "rpeq_status": (data.get("rpeq_status") or "").strip(),
            "years_experience": (data.get("years_experience") or "").strip(),
            "value_to_project": _strip_value_prefix((data.get("value_to_project") or "").strip(), name),
            "relevant_projects": [str(p).strip() for p in (data.get("relevant_projects") or []) if str(p).strip()],
        }

    if unmatched:
        warnings.append(
            "No CV file could be matched to: " + ", ".join(unmatched) +
            " -- their filename doesn't derive to this exact name, or they have no CV uploaded."
        )
    if failed_people:
        warnings.append(
            f"{len(failed_people)} person(s)' CVs couldn't be read after retrying -- "
            + "; ".join(failed_people) +
            ". Use the 'Refresh from CV' button for just that person once the underlying "
            "issue (e.g. rate limiting) has cleared, rather than re-running everyone."
        )
    if not profiles:
        warnings.append("No profile details could be confidently matched to the named people.")
    return profiles, warnings


def _extract_profile_fields_from_combined_text(
    names: list[str], cv_text: str, config: dict | None, chunk_chars: int, max_chunks: int,
) -> tuple[dict[str, dict[str, str]], list[str]]:
    from modules.document_processor import split_text_into_chunks

    material = (cv_text or "").strip()
    if not material:
        return {}, ["No CV text was supplied -- nothing to extract."]

    chunks = split_text_into_chunks(material, chunk_size=chunk_chars, overlap=500)
    truncated = len(chunks) > max_chunks
    chunks = chunks[:max_chunks]

    profiles: dict[str, dict[str, str]] = {}
    warnings: list[str] = []
    failed_chunks = 0
    names_block = "\n".join(f"- {n}" for n in names)

    for chunk in chunks:
        try:
            data = call_ai_json(
                PROFILE_FIELDS_PROMPT.format(names=names_block, material=chunk),
                system_message=PROFILE_FIELDS_SYSTEM, config=config, max_tokens=2000,
            )
        except Exception:
            failed_chunks += 1
            continue
        entries = data.get("profiles", []) if isinstance(data, dict) else []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = (entry.get("name", "") or "").strip()
            if not name:
                continue
            key = name.lower()
            existing = profiles.setdefault(key, {
                "name": name, "qualification": "", "rpeq_status": "", "years_experience": "",
                "value_to_project": "", "relevant_projects": [],
            })
            for field in ("qualification", "rpeq_status", "years_experience", "value_to_project"):
                value = (entry.get(field, "") or "").strip()
                if field == "value_to_project":
                    value = _strip_value_prefix(value, name)
                if value and not existing.get(field):
                    existing[field] = value
            if not existing.get("relevant_projects"):
                projects = [str(p).strip() for p in (entry.get("relevant_projects") or []) if str(p).strip()]
                if projects:
                    existing["relevant_projects"] = projects
        warns = data.get("warnings", []) if isinstance(data, dict) else []
        warnings.extend(w for w in warns if w)

    if failed_chunks:
        warnings.append(f"{failed_chunks} section(s) of the CV library couldn't be read; the rest were processed.")
    if truncated:
        warnings.append("The CV library is very large; only the first portion was scanned for profile details.")
    if not profiles:
        warnings.append("No profile details could be confidently matched to the named people.")
    return profiles, warnings


def extract_person_names(cv_text: str, config: dict | None = None,
                         chunk_chars: int = 8000, max_chunks: int = 24) -> tuple[list[str], list[str]]:
    """
    Extract the full names of everyone whose CV appears in the CV library, for
    populating the resourcing dropdowns. Returns (names, warnings).

    The CV library is often long (many CVs concatenated -- tens of thousands of
    characters), so this reads it in CHUNKS and merges the names, rather than
    truncating to the first slice and silently missing most of the team. Names
    are de-duplicated case-insensitively across chunks. Never invents names.
    """
    from modules.document_processor import split_text_into_chunks

    material = (cv_text or "").strip()
    if not material:
        return [], ["No CV/company profile text was supplied -- nothing to extract names from."]

    chunks = split_text_into_chunks(material, chunk_size=chunk_chars, overlap=500)
    truncated = len(chunks) > max_chunks
    chunks = chunks[:max_chunks]

    names: list[str] = []
    seen = set()
    warnings: list[str] = []
    failed_chunks = 0
    for chunk in chunks:
        try:
            data = call_ai_json(
                NAME_EXTRACTION_PROMPT.format(material=chunk),
                system_message=NAME_EXTRACTION_SYSTEM, config=config, max_tokens=1500,
            )
        except Exception:
            failed_chunks += 1
            continue
        people = data.get("people", []) if isinstance(data, dict) else []
        for p in people:
            name = (p.get("name", "") if isinstance(p, dict) else "").strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                names.append(name)

    if failed_chunks:
        warnings.append(f"{failed_chunks} section(s) of the CV library couldn't be read for names; the rest were processed.")
    if truncated:
        warnings.append("The CV library is very large; scanned the first portion for names. Add any missing people manually.")
    if not names:
        warnings.append("No individual people could be confidently identified in the CV library.")
    return names, warnings
