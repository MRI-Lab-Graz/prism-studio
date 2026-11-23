# Instrument library: provenance and terms

This directory holds questionnaire templates. **These templates are content,
not code, and the repository's AGPL-3.0 license does not apply to them.**
Each template stays under its own terms, set by the rights holder of the
instrument and stated in the template's `Study` block (`License`, `LicenseID`,
`Source`, `LicenseLanguages`). That block is authoritative; read it before use.

## What ships (23 templates)

- `survey-demo.json`: written for the PRISM specification as a demonstration,
  released under CC0 1.0. It measures nothing and is not a real instrument.
- `survey-dass.json`, `survey-dass21.json`: the DASS templates. The authors'
  statement (kept in each template) allows free use without further permission.
- 20 templates of the Open Test Archive (testarchiv.eu, published through
  PsychArchives), each under **CC BY-SA 4.0** with the DOI of its record in
  `Study.Source`. Attribution and share-alike apply to the template; the
  languages named in `Study.LicenseLanguages` are the ones the licence covers.

The list of what ships is `survey/index.json`. A template is added only when
its redistribution is verified (a statement of the rights holder or an open
licence, kept with its source). PRISM does not own these instruments and grants
no rights to them beyond what each template states. Nothing in PRISM calls an
external service at runtime.

## Other instruments

Put your own templates in your own library folder (`globalLibraryRoot` or
`personalLibraryPath` in the settings) and PRISM reads them like the shipped
ones. Whether you may use an instrument is for you to check with its authors or
publisher.

## Your responsibility

You are responsible for confirming that you may use a given instrument in your
study, and for obtaining permission where the rights holder requires it.
