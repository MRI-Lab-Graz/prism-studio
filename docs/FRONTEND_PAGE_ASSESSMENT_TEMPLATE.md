# Frontend Page Assessment Template

Use this template for each frontend page assessment.

## 1. Page Definition

- Page key:
- Route(s):
- Template:
- Primary JS modules:
- Primary backend contracts (endpoints):

## 2. Workflow Logic Map

- Main user workflows (happy path):
- Workflow state machine summary:
- State reset triggers (project change, file change, tab switch, cancel):
- Async operations and polling loops:
- Contract assumptions between frontend and backend:

## 2.1 Backend Command Ownership (Required)

- Rule check: Does this page execute logic only by preparing/submitting backend commands?
- Rule check: Is frontend behavior limited to command setup, validation hints, progress UX, and result rendering?
- Exception check: If this is the Project page, document which logic is intentionally frontend-heavy and why backend-only is not practical.
- Violation list: any business logic or data mutation implemented in frontend that should move to backend.
- Backend command traceability: map each major user action to one backend command/endpoint contract.

## 3. Hostile Usage Assessment

- Abuse scenarios considered:
  - repeated click storms / duplicate submits
  - stale token or job id replay
  - malformed payload / missing required values
  - path parameter misuse
  - large payload / large list abuse
- Observed guardrails:
- Observed gaps:

## 4. Stability Assessment

- Project switch while operation is running:
- Multi-tab behavior:
- Cancel / retry behavior:
- Network failure handling and recovery:
- Stale UI state risk:

## 5. Fast Execution Assessment

- Rendering hotspots:
- Polling and network hotspots:
- Payload size hotspots:
- Expensive loops / repeated rebuilds:

## 6. Findings

Use severity buckets: Critical, High, Medium, Low.

For each finding include:

- Severity:
- Title:
- Affected file(s):
- Repro steps:
- Impact:
- Recommended fix:
- Validation strategy:
- Backend-ownership impact: does this finding break the backend-command ownership rule?

## 7. Remediation Slice Plan

- Slice A (highest risk):
- Slice B:
- Slice C:

Each slice should include:

- planned files
- tests to add or run (`./rtk test ...`)
- acceptance criteria
- backend command ownership checks for touched actions

## 8. Exit Criteria for This Page

- All Critical findings resolved or explicitly accepted with rationale.
- All High findings have either fixes merged or approved defer decision.
- Stability smoke checks pass.
- Focused RTK test suite passes.
- Backend-command ownership holds for all assessed workflows (except documented Project page exceptions).
