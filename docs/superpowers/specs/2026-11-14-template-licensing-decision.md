# Decision: which instrument templates ship (DASS)

Date: 2026-11-14. Status: **proposed**; the rule below is the user's, the DASS decision is a proposal for the user to
confirm or change. It resolves open point 1 of `2026-11-14-mappings-layer-design.md`.

## The rule (decided by the user, 2026-11-14)

Instrument templates ship only where PRISM is 100% sure it may redistribute them. Everything else is not shipped any
more, in neither prism-specification nor PRISM Studio. Shipped templates demonstrate how templates work; they are not
a library of instruments. The user does not want any licensing problems.

"100% sure" means (the user's checklist): public domain, CC0, CC BY and other open licences, or an explicit permission
from the rights holder to reproduce, distribute or share, with a saved copy of the statement. "Free to use" without a
mention of copying or sharing is **not** enough; neither is "no licence stated" or "all rights reserved".

## What was found (14 November 2026)

The audit of the 103 survey templates (`docs/handouts/template-licence-audit.md`, a working document) found that almost
all licence statements are PsyToolkit's own hedged wording ("it seems that ... can be used for research"), which is
neither a grant by the authors nor about redistribution. Checked against the original sources
(`docs/handouts/template-licence-evidence-2026-11-14.md`: quotes and URLs, fetched by an agent, not yet checked by a
person):

| Template | Result under the rule |
|---|---|
| `dass`, `dass21` | public domain, with limits (below) |
| `cia` | licence not confirmed |
| `phq9`, `gad7` | rights-holder page says "free for download and use as stated within the PHQ Screeners site"; reproduction, distribution and translation are not named |
| all others (about 98) | not verified; none ships |

## DASS: the facts

Source: https://www2.psy.unsw.edu.au/dass/ (the rights holder's site; Psychology Foundation of Australia, Lovibond &
Lovibond).
- "The DASS questionnaire is in the public domain, and may be downloaded from this website."
- "The DASS questionnaire forms may be downloaded and copied without restriction." and "However, the scales may not be
  modified or sold for profit."
- The DASS-21 response form is listed under the same statement.
- Translations are allowed if the translation is itself public domain and is posted on the DASS site.
- Administering the DASS on a website or app "intended for or open to members of the public" is not allowed (defined
  groups such as research participants are fine).

## Proposed decision for DASS

1. `dass` (42 items) and `dass21` stay as the only third-party instrument templates, as **demonstration templates**.
2. They are shipped **with the original English wording unchanged**. The template carries the DASS statement verbatim,
   the source URL, the retrieval date and the three conditions (no modification, no sale for profit, no public-web
   administration), plus a pointer asking users to cite the DASS website.
3. **No translation of ours ships** with them: the DASS rule requires a translation to be public domain and posted on
   the DASS site, which we have not arranged. (If the templates carry German text today, it is removed.)
4. A one-line confirmation is requested from the DASS contact that a JSON template representing the unmodified items
   is acceptable ("not modified" is not defined on the page). Until the answer arrives the proposal stands as the
   working decision; if the answer is no, the DASS templates are removed too.
5. The release notes and `official/library/NOTICE.md` say that the library was reduced and why.

## Consequences for everything that is not shipped (to be planned separately)

- Studio's official library, its instrument registry index and the 104 recipes of the removed instruments go; the
  recipes are kept only for instruments that stay.
- The frozen survey IDs (`term-ids.txt`, 1,478 IDs): the freeze rule says an ID is never deleted. Decision needed:
  keep the list of released IDs (identifiers only, no wording) so existing mappings and data keep resolving, or retire
  the IDs with a recorded reason. Not decided here.
- Studio's tests, converters, docs and screenshots that use library instruments are rewritten around the demo
  templates (a made-up demo questionnaire of our own, plus DASS).
- Users' project copies of templates are not touched.
- The git history and already published releases still contain the removed files; that cannot be undone here.
- Anyone who needs an instrument gets the official source and imports it with the existing Excel and LimeSurvey
  import.

## What a person still has to do

1. Save dated copies of the three DASS pages and the evidence quoted above.
2. Send the DASS confirmation question (point 4).
3. Decide the frozen-ID question and whether PHQ-9 and GAD-7 are worth verifying at the questionnaire PDFs and the
   original papers (the rights-holder page does not settle redistribution).
