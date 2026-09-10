# Instrument library: provenance and terms

This directory holds questionnaire templates. **These templates are content,
not code, and the repository's AGPL-3.0 license does not apply to them.**

## Provenance

Almost all survey templates in `survey/` were derived from the
[PsyToolkit survey library](https://www.psytoolkit.org/survey-library/),
scraped on 2026-01-20. Each template records its upstream page in
`Study.Source`. PsyToolkit is a separate project by Gijsbert Stoet and is not
a dependency of PRISM; nothing in PRISM calls PsyToolkit at runtime.

If you use these templates, cite PsyToolkit:

> Stoet, G. (2010). PsyToolkit: A software package for programming
> psychological experiments using Linux. *Behavior Research Methods*, 42(4),
> 1096-1104.
>
> Stoet, G. (2017). PsyToolkit: A novel web-based method for running online
> questionnaires and reaction-time experiments. *Teaching of Psychology*,
> 44(1), 24-31.

## Terms differ per instrument

PRISM does not own these instruments and grants no rights to them. Each
template's `Study.License` field carries the licensing statement **verbatim
from its upstream source**, and `Study.LicenseID` carries a normalized
identifier where one applies.

Read that field before using an instrument. The statements are not uniform:

- Some instruments are explicitly free for research with attribution.
- Some carry a Creative Commons license, including non-commercial terms
  (`BFI-S` is CC BY-NC), which is **more restrictive than this repository's
  code license**.
- Some upstream pages state no licensing information at all. Those templates
  say `NOT VERIFIED` and must be checked against the original publication
  before use.

A statement like "it seems that X can be used for research" is PsyToolkit's
hedge, meaning no explicit grant was found and no restriction was evident. It
is not a license.

## Removed instruments

Instruments whose upstream terms are unclear or restrictive are removed rather
than shipped. Removed so far:

- **BSRI** (Bem Sex Role Inventory), removed 2026-09-10. PsyToolkit states it
  "is not clear whether it can be freely used for research purposes", and Mind
  Garden licenses the instrument and forbids making it available on the open
  web.

If you find another instrument here whose terms are restrictive, please open
an issue. Do not add an instrument without recording its real upstream
licensing statement.

## Your responsibility

You are responsible for confirming that you may use a given instrument in your
study, and for obtaining permission where the rights holder requires it.
