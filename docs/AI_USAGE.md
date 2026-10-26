# AI Usage Statement

PRISM Studio is developed with the help of AI coding assistants. This page
says what they did and what they did not do.

## Who decides

The ideas, the design and the review are human work. Karl Koschutnig
(project lead) conceived PRISM and PRISM Studio, decides what the software
does and how it is built (architecture, data model, specification, user
interface, scope), and reviews every change before it is merged into `main`.
Contributions from other people go through the same review.

## What the AI tools did

GPT-5.3 (OpenAI), Claude Sonnet 5 and Opus 4.6 (Anthropic), and GitHub
Copilot were used to write and refactor code, write tests, draft
documentation, and help draft the manuscript. They worked on tasks set by
the project lead, who checked, corrected or rejected their output.

## Safeguards

- Every change is reviewed by a person before it is merged.
- New features and bug fixes are written test-first; the test suite and the
  validator checks run in continuous integration.
- The authors accept full responsibility for the software, the
  documentation and the paper.

## About `CLAUDE.md`

The [`CLAUDE.md`](https://github.com/MRI-Lab-Graz/prism-studio/blob/main/CLAUDE.md)
file in the repository holds the project's rules for the AI assistant: which
architecture to follow, that tests come first, and which past mistakes not
to repeat. These rules were written from the project lead's decisions; the
file instructs the tool, it does not record work done by it.
