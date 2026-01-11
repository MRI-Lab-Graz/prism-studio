# PRISM Hands-on Workshop Strategy (2 Hours)

This document outlines the strategy for a 2-hour hands-on workshop designed to introduce new users to PRISM.

## Workshop Objectives
- Understand the PRISM modular metadata approach (hierarchical JSON).
- Learn how to validate a dataset using the Web Interface and CLI.
- Perform core tasks: missing sidecar generation, error fixing, and library-based conversion.
- Explore advanced features: NeuroBagel export and Methods snippet generation.

## Schedule (Total: 120 Minutes)

| Time | Duration | Activity | Description |
| :--- | :--- | :--- | :--- |
| **00:00** | 15 min | **Introduction** | Theory: BIDS vs. PRISM. Why hierarchical metadata? The Golden Master concept. |
| **00:15** | 15 min | **Setup & Tour** | Activate `.venv`. Launch `python prism-studio.py`. Tour of the Dashboard & Project Management. |
| **00:30** | 35 min | **Hands-on 1: Validation** | Use `demo/workshop/messy_dataset`. Fix filenames, create missing sidecars, and resolve schema errors. |
| **01:05** | 10 min | **Break** | Coffee and informal Q&A. |
| **01:15** | 35 min | **Hands-on 2: Conversion**| Use `demo/workshop/raw_material`. Map raw files to the Survey Library and generate PRISM-compliant datasets. |
| **01:50** | 10 min | **Advanced Features** | Export to NeuroBagel. Generate "Methods" snippets. Brief look at the Plugin API. |

---

## Detailed Hands-on Scenarios

### Scenario 1: The "Messy" Dataset (Validation & Fixing)
**Goal:** Reach 100% compliance ("Green" status) in the validator.
- **Task A (Invalid Naming):** `sub02_ses01_task-wellbeing_beh.tsv` -> Needs proper BIDS labels (`sub-02_ses-01_task-wellbeing_survey.tsv`).
- **Task B (Missing sidecar):** A physiological TSV file exists but has no JSON. Use the "Generate Sidecar" tool.
- **Task C (Schema violation):** `SamplingRate` is provided at the root level. PRISM requires it in `Technical.SamplingRate`.
- **Task D (Modalities):** Adding an Eye-tracking file and selecting the correct schema.

### Scenario 2: The "Conversion" Exercise (Workflow)
**Goal:** Take unorganized raw data and "PRISM-ify" it.
- **Input:** A CSV from LimeSurvey or a custom Excel sheet in `raw_material`.
- **Tool:** Use the "Survey Library" (Golden Master) to auto-populate metadata.
- **Output:** A structured `sub-01/ses-01/survey/...` folder with validated files.

---

## Technical Setup for Instructor
1. Ensure `demo/workshop/` is populated and "reset" before the workshop.
2. Have `prism_tools.py` ready to demonstrate CLI power-user tricks.
3. Pre-load the `library/` folder with standard survey templates (PHQ-9, GAD-7).

## Student Take-away
- Access to [WORKSHOP_HANDOUT.md](WORKSHOP_HANDOUT.md).
- A "Valid" version of the dataset for reference.
- Knowledge on how to contribute new schemas to the PRISM ecosystem.
