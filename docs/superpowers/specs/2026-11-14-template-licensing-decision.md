# Decision: which instrument templates ship (DASS)

Date: 2026-11-14. Status: **decided in principle by the user** ("we ship only 2 templates to the specifications, and
prepare this for later usage"); the details of the DASS proposal below are the working decision until the DASS contact
answers. It resolves open point 1 of `2026-11-14-mappings-layer-design.md`.

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


## What the user decided (2026-11-14, after the crawler and PsyToolkit review)

- **The move goes ahead with only the two templates that are 100% sure: `dass` and `dass21`** (plus their recipes, plus
  our own demo templates). Nothing else is moved into prism-specification.
- **The other templates are not moved and not copied again, and they are dropped from Studio** (decided later the same
  day: "the templates should be dropped from Studio, move them to a local folder which is not tracked"). A verified copy
  is kept in `/Volumes/Evo/work/prism-local-library/` (outside every repository) and Studio reads it through its
  `globalLibraryRoot` setting. Until the removal is merged (a plan of its own, Task 8 of
  `2026-11-14-mappings-layer-and-two-templates.md`) the files stay tracked.
- **The rest is prepared in the background** (section "Background preparation" below), so that templates can move to
  the specification one by one when their licence is verified.
- Why the earlier plan changed: the crawler (`harvest_psytoolkit.py`, January 2026) copied item wording from
  PsyToolkit; PsyToolkit's own terms say the copyright of the scales "typically belongs to the authors" and grant use in
  its tool, with nothing about republishing. A notice (acknowledgement, citation) is right and will be built, but it
  does not answer who may publish the wording. See `docs/handouts/template-licence-audit.md`.

- **Recipes and mappings for all instruments ship** (the user's observation: they carry no wording), with the identifier
  list `ids/survey-ids.txt`; four hand-written recipes (PSQI, WHO-5, TIPI and a duplicate) are held until their
  cut-offs and notes are verified or removed. See the plan, Global Constraints.

## Facts found in the two templates (to be handled when they move)

- Both carry **German text** next to the English (items and instructions). The DASS terms say a translation must itself
  be public domain and posted on the DASS site; the origin of our German wording is not recorded. **The German text does
  not move**; the moved templates are English only.
- Their `Study.License` is PsyToolkit's paraphrase (`dass`: "The DASS website states that the DASS is public domain ...";
  `dass21`: "This scale can be used as long as the website, the authors, and the papers are acknowledged."). On the move,
  the rights holder's own statements (quoted in `template-licence-evidence-2026-11-14.md`) replace them, with the
  source URL and the retrieval date, and the three DASS conditions are written into the template.
- Both templates still carry `Study.ItemCount` and the item flag `Reversed`, which the slim-survey schema 2.1.1 no
  longer defines; they are cleaned as part of the move.
- `prism:dass.*` has 67 released IDs in `term-ids.txt` (and `dass21` its own); they move unchanged.

## Background preparation (no template moves; none of it needs the answers)

1. **Acknowledgement and citation notice in Studio:** before a user applies a template, show its source, licence
   statement and acknowledgement requirement; after use, write the citation and the acknowledgement into the generated
   methods text and the project's citation file; a template without verified evidence says so in plain words.
2. **Licence evidence pipeline:** every template that ships from the specification must carry its evidence (rights
   holder, URL, retrieval date, quoted sentence) and a check refuses a template without it, so any instrument cleared
   later can be added without a new decision.
3. **Rights-holder contact policy** in the repositories and the documentation: how to ask for removal of an instrument.
4. **Letters (drafts for the user to send):** to PsyToolkit (Stoet), to the DASS contact (is a JSON template with the
   unmodified items "not modified"?), to Pfizer/PHQ screeners, and a template for authors ("may we share the items?").
5. **Wording-free skeletons** (identifiers, answer scale, recipes, mappings; no item text) as a design for later, for the
   instruments that cannot be shipped with wording; needs a legal view before anything ships.

## Consequences if templates were ever withdrawn from Studio (NOT decided; kept for reference)

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
