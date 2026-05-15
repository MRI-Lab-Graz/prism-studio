# Frontend Structural Assessment Roadmap (2026-05)

## Mission

Assess every frontend page one at a time with focus on:

- workflow logic correctness
- hostile usage resilience
- stability under edge conditions
- fast execution

## Non-Negotiable Architecture Rule

Frontend must prepare and submit backend commands.
Frontend should not own business logic execution.

Exception:

- Project page may keep limited frontend-heavy orchestration where backend-only operation is not practical.

This rule is part of every page assessment and every remediation slice acceptance check.

## Assessment Order

### Phase 1 - Core Workflow Pages

1. Converter page group ([app/templates/converter.html](app/templates/converter.html))
2. Projects page ([app/templates/projects.html](app/templates/projects.html))
3. Validation page ([app/templates/index.html](app/templates/index.html))
4. Results page ([app/templates/results.html](app/templates/results.html))

### Phase 2 - Authoring and Data Ops Pages

5. Template Editor ([app/templates/template_editor.html](app/templates/template_editor.html))
6. Recipe Builder ([app/templates/recipe_builder.html](app/templates/recipe_builder.html))
7. Survey Customizer ([app/templates/survey_customizer.html](app/templates/survey_customizer.html))
8. Survey Generator ([app/templates/survey_generator.html](app/templates/survey_generator.html))
9. File Management ([app/templates/file_management.html](app/templates/file_management.html))

### Phase 3 - Secondary Pages and Platform Glue

10. JSON Editor ([app/templates/json_editor.html](app/templates/json_editor.html))
11. Specifications ([app/templates/specifications.html](app/templates/specifications.html))
12. Library and Library Editor ([app/templates/library.html](app/templates/library.html), [app/templates/library_editor.html](app/templates/library_editor.html))
13. PRISM App Runner ([app/templates/prism_app_runner.html](app/templates/prism_app_runner.html))
14. Home page ([app/templates/home.html](app/templates/home.html))

Cross-cutting shared modules:

- [app/static/js/shared/project-state.js](app/static/js/shared/project-state.js)
- [app/static/js/shared/api.js](app/static/js/shared/api.js)
- [app/static/js/shared/job-polling.js](app/static/js/shared/job-polling.js)

## Deliverable Per Page

For each page we deliver:

1. Workflow map and state transition summary
2. Backend command ownership map (action -> backend command/endpoint)
3. Hostile usage scenarios and current guardrails
4. Stability scenarios (project switch, multi-tab, cancellation, retries)
5. Execution speed bottlenecks
6. Severity-ranked findings (Critical/High/Medium/Low)
7. 1-3 remediation slices with RTK test plan

## Validation Standard

RTK-first only:

- `./rtk test <focused tests>` for each page slice
- `./rtk coverage` at phase boundaries

## Current Start Point (Phase 1.1 Converter)

Initial concerns to verify and convert into actionable findings:

- project-context drift during long-running converter operations
- polling/cancellation reliability
- stale state after project changes
- frontend-backend contract mismatches on command payloads
- command ownership violations where frontend performs business logic that should run in backend

Primary implementation surface:

- [app/static/js/converter-bootstrap.js](app/static/js/converter-bootstrap.js)
- [app/static/js/modules/converter/](app/static/js/modules/converter/)
- [app/src/web/blueprints/conversion.py](app/src/web/blueprints/conversion.py)
- [app/src/web/blueprints/conversion_survey_handlers.py](app/src/web/blueprints/conversion_survey_handlers.py)
- [app/src/web/blueprints/conversion_participants_blueprint.py](app/src/web/blueprints/conversion_participants_blueprint.py)

## Current Checkpoint (2026-05-15)

- Phase 1.1 Converter checkpoint completed and captured in [docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md](docs/FRONTEND_ASSESSMENT_CONVERTER_2026-05.md).
- Phase 1.2 Projects checkpoint started in [docs/FRONTEND_ASSESSMENT_PROJECTS_2026-05.md](docs/FRONTEND_ASSESSMENT_PROJECTS_2026-05.md).
- Phase 1.3 Validator checkpoint started in [docs/FRONTEND_ASSESSMENT_VALIDATOR_2026-05.md](docs/FRONTEND_ASSESSMENT_VALIDATOR_2026-05.md).
- Phase 1.4 Results checkpoint started in [docs/FRONTEND_ASSESSMENT_RESULTS_2026-05.md](docs/FRONTEND_ASSESSMENT_RESULTS_2026-05.md).
- Phase 2.1 Template Editor checkpoint started in [docs/FRONTEND_ASSESSMENT_TEMPLATE_EDITOR_2026-05.md](docs/FRONTEND_ASSESSMENT_TEMPLATE_EDITOR_2026-05.md).
- Phase 2.2 Recipe Builder checkpoint started in [docs/FRONTEND_ASSESSMENT_RECIPE_BUILDER_2026-05.md](docs/FRONTEND_ASSESSMENT_RECIPE_BUILDER_2026-05.md).
- Phase 2.3 Survey Customizer checkpoint started in [docs/FRONTEND_ASSESSMENT_SURVEY_CUSTOMIZER_2026-05.md](docs/FRONTEND_ASSESSMENT_SURVEY_CUSTOMIZER_2026-05.md).
- Phase 2.4 Survey Generator checkpoint started in [docs/FRONTEND_ASSESSMENT_SURVEY_GENERATOR_2026-05.md](docs/FRONTEND_ASSESSMENT_SURVEY_GENERATOR_2026-05.md).
- Phase 2.5 File Management checkpoint started in [docs/FRONTEND_ASSESSMENT_FILE_MANAGEMENT_2026-05.md](docs/FRONTEND_ASSESSMENT_FILE_MANAGEMENT_2026-05.md).
- Phase 3.1 JSON Editor checkpoint started in [docs/FRONTEND_ASSESSMENT_JSON_EDITOR_2026-05.md](docs/FRONTEND_ASSESSMENT_JSON_EDITOR_2026-05.md).
- UI harmonization gating remains green and now serves as baseline safety net while page-by-page structural assessment continues.
