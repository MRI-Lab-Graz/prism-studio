# Instrument library: provenance and terms

This directory holds questionnaire templates. **These templates are content,
not code, and the repository's AGPL-3.0 license does not apply to them.**

## The library was reduced

The library shipped with PRISM now contains only templates that may be
redistributed: a demonstration questionnaire (`survey-demo.json`, CC0) and the
DASS templates. Other instruments can still be used: put their templates in
your own library folder (`globalLibraryRoot` or `personalLibraryPath` in the
settings) and PRISM reads them like the shipped ones. Whether you may use an
instrument is for you to check with its authors or publisher.

## What ships

- `survey-demo.json`: written for the PRISM specification as a demonstration,
  released under CC0.
- `survey-dass.json`, `survey-dass21.json`: the DASS templates. Each carries
  its own licensing evidence in the `Study` block (`License`, `LicenseID`,
  `Source`); read it before use.

PRISM does not own these instruments and grants no rights to them beyond what
that evidence states. Nothing in PRISM calls an external service at runtime.

## Your responsibility

You are responsible for confirming that you may use a given instrument in your
study, and for obtaining permission where the rights holder requires it.
