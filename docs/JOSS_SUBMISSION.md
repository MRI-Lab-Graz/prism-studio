# JOSS submission checklist (PRISM)

This is a practical checklist for submitting PRISM to the Journal of Open Source Software (JOSS).

## 1) Prerequisites

- An OSI-approved open source license in `LICENSE`.
- A tagged release (e.g., `v1.2.3`).
- An archived copy of the release with a DOI (commonly via Zenodo).
- A `paper/` directory containing `paper.md` and `paper.bib`.

## 2) Fill in the placeholders

Update these files:

- `paper/paper.md`: authors, affiliations, ORCIDs, and the manuscript text.
- `paper/paper.bib`: add the correct BIDS citation and any related work.
- `CITATION.cff`: version, license, repository URL, and authors.
- `codemeta.json`: license and repository URL.

## 3) Recommended repository hygiene

- Add a "How to cite" section to README linking to `CITATION.cff` and the DOI.
- Ensure installation instructions work from a clean environment.
- Ensure a minimal example dataset validates end-to-end.

## 4) Submit to JOSS

- Start a submission at: https://joss.theoj.org/
- Provide:
  - Software repository URL
  - Archive DOI
  - `paper/paper.md` and `paper/paper.bib`

## 5) During review

- Address reviewer comments in GitHub issues/PRs.
- Cut a new tagged release if needed, and update the archive DOI reference.

