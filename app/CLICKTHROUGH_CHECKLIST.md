# Manual click-through checklist -- after any change to app.py / modules/pages/

Run against the deployed app (or `streamlit run app.py` locally). The smoke
test (`python smoke_test.py`) must already pass before starting this list.

## Login & account (SaaS mode only)
- [ ] Login screen renders; wrong password shows an error; 5 wrong passwords in a row locks the form with a clear "paused for ~15 minutes" message
- [ ] Correct login works; refresh keeps you signed in; Log out returns to a clean login screen
- [ ] Signup creates an account (terms checkbox required) and lands in the app
- [ ] Sidebar shows the right plan line (trial / subscription / pay-as-you-go / unlimited)
- [ ] Admin account only: "AI cost (admin)" expander shows a total and per-project table

## Project Setup & Upload
- [ ] Enter project/client/tender names -- they persist across tab switches and reruns
- [ ] Upload a text PDF brief: success line shows characters/pages/headings
- [ ] Upload a scanned PDF: either OCR runs with the "OCR-derived -- verify carefully" warning, or the plain-language "this brief looks scanned" message appears -- never an empty success
- [ ] Upload a tender-package ZIP: breakdown table shows each file filed as brief/addendum/schedule/drawing/other with reasons; schedules noted as kept for Export Pack
- [ ] Upload company material (profile, CVs) -- per-file merge works, re-upload replaces just that file

## Analysis → Structure → Drafts
- [ ] Run Tender Analysis: progress bar, then scope/objectives/criteria render; trial counter decrements exactly once for the same project+brief
- [ ] Generate Proposal Structure: sections table renders; format switch (formal/letter) warns about stale structure
- [ ] Page Allocation renders and edits persist
- [ ] Generate drafts: no invented facts; placeholders appear for unknowns; user edits to a draft survive a rerun and are NOT overwritten by regeneration without confirmation
- [ ] Red-team pitch review only comments on entered text

## Graphics, Team, Fees
- [ ] Divider/cover generation works; theme change re-themes
- [ ] Team & Resourcing: assign people from CVs, custom titles stick
- [ ] Fee Estimate (both formats): editing hours/rates updates totals in place (fragment -- no full-page rerun); benchmark split renders; delivery program grid edits persist

## Export Pack
- [ ] Generate DOCX (both formats): downloads open in Word; OCR notice appears at the front ONLY when the brief was OCR-derived
- [ ] Tender Summary + Org Chart / Methodology / Program PPTX downloads all work
- [ ] Archive to Library: entry appears in Proposal Library for this account only
- [ ] Returnable schedules: schedules from the ZIP are listed; "Fill schedules" produces a filled copy with real data where known and [TO BE COMPLETED: ...] elsewhere; original formatting intact; fill report matches the document
- [ ] Save/Load project round-trips (including returnable schedules and OCR flag)

## Cross-cutting
- [ ] Autosave: make a change, wait, reload -- "My projects" has the update
- [ ] No stack trace anywhere above: every failure path shows a human message
