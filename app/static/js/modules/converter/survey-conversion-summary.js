export function createSurveyConversionSummaryController({
    conversionSummaryContainer,
    conversionSummaryBody,
    toggleSummaryBtn,
    convertDatasetName,
    getSurveyPreviewSelectionState,
    setSurveyPreviewSelectedTasks,
    normalizeSurveyTaskName,
    formatSignedOffset,
    escapeHtml,
    openAdvancedOptionsValueOffsetEditor,
    updateConvertBtn,
}) {
    function getSelectionState() {
        if (typeof getSurveyPreviewSelectionState === 'function') {
            return getSurveyPreviewSelectionState() || {};
        }
        return {};
    }

    function updateSurveyTaskSelectionSummaryText() {
        if (!conversionSummaryBody) return;
        const summaryNode = conversionSummaryBody.querySelector('[data-survey-task-selection-count]');
        if (!summaryNode) return;

        const selectionState = getSelectionState();
        const selectedCount = Array.isArray(selectionState.selectedTasks)
            ? selectionState.selectedTasks.length
            : 0;
        const totalCount = Array.isArray(selectionState.availableTasks)
            ? selectionState.availableTasks.length
            : 0;
        summaryNode.textContent = `${selectedCount} of ${totalCount} selected`;
    }

    function renderSurveyTaskReviewSummary(taskSummaries) {
        if (!Array.isArray(taskSummaries) || taskSummaries.length === 0) {
            return '';
        }

        const selectedCount = taskSummaries.filter((entry) => entry && entry.selected !== false).length;
        const reviewCount = taskSummaries.filter((entry) => entry && entry.manual_review_required).length;

        return `
            <div class="mb-3 border rounded p-3">
                <div class="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2 mb-2">
                    <div>
                        <h6 class="mb-1"><i class="fas fa-list-check me-1"></i>Preview Review</h6>
                        <div class="text-muted small">Deselect surveys you do not want to convert. Preview review is now the handoff between setup and conversion.</div>
                    </div>
                    <div class="d-flex flex-wrap align-items-center gap-2">
                        <span class="badge bg-secondary" data-survey-task-selection-count>${selectedCount} of ${taskSummaries.length} selected</span>
                        ${reviewCount > 0 ? `<span class="badge bg-warning text-dark">${reviewCount} need manual review</span>` : '<span class="badge bg-success">All previewed surveys look in range</span>'}
                        ${reviewCount > 0 ? '<button type="button" class="btn btn-sm btn-outline-warning" data-survey-open-advanced><i class="fas fa-sliders-h me-1"></i>Advanced options</button>' : ''}
                        <button type="button" class="btn btn-sm btn-outline-dark" data-survey-task-select-all>Select all</button>
                        <button type="button" class="btn btn-sm btn-outline-dark" data-survey-task-clear-all>Clear all</button>
                    </div>
                </div>
                <div class="list-group list-group-flush border rounded">
                    ${taskSummaries.map((entry, index) => {
                        const task = normalizeSurveyTaskName(entry && entry.task);
                        if (!task) return '';

                        const checkboxId = `survey-task-review-${index}`;
                        const checked = entry && entry.selected !== false ? 'checked' : '';
                        const runCount = Number(entry && entry.run_count);
                        const runBadge = Number.isFinite(runCount) && runCount > 1
                            ? `<span class="badge bg-info text-dark">${runCount} runs</span>`
                            : '';
                        const review = entry && entry.manual_review_required && entry.out_of_range
                            ? entry.out_of_range
                            : null;
                        const suggestedOffsets = Array.isArray(review && review.suggested_offsets)
                            ? review.suggested_offsets
                                .map((value) => formatSignedOffset(value))
                                .filter(Boolean)
                            : [];
                        const expectedLevels = Array.isArray(review && review.expected_levels)
                            ? review.expected_levels.filter((value) => String(value || '').trim())
                            : [];
                        const configuredOffset = Number(review && review.configured_offset);
                        const hasConfiguredOffset = Number.isFinite(configuredOffset);
                        const adjustedValue = review && review.adjusted_value;
                        const hasAdjustedValue = adjustedValue !== undefined && adjustedValue !== null;
                        const rawValueValidWithoutOffset = Boolean(
                            review && review.raw_value_valid_without_offset === true
                        );
                        const offsetEvidence = review && typeof review.offset_evidence === 'object'
                            ? review.offset_evidence
                            : null;
                        const offsetClassification = String(offsetEvidence && offsetEvidence.classification || '').trim().toLowerCase();
                        const structuralOffsetLikely = offsetClassification === 'structural_offset_likely';
                        const sampledValues = Number(offsetEvidence && offsetEvidence.sampled_numeric_values);
                        const invalidWithoutOffset = Number(offsetEvidence && offsetEvidence.invalid_without_offset);
                        const invalidWithoutOffsetPercent = Number(offsetEvidence && offsetEvidence.invalid_without_offset_percent);
                        const hasOutOfRangeRate = Number.isFinite(sampledValues)
                            && sampledValues > 0
                            && Number.isFinite(invalidWithoutOffset)
                            && invalidWithoutOffset >= 0
                            && Number.isFinite(invalidWithoutOffsetPercent);
                        const outOfRangeRateText = hasOutOfRangeRate
                            ? `${invalidWithoutOffsetPercent.toFixed(1)}% (${invalidWithoutOffset}/${sampledValues} sampled values)`
                            : '';

                        return `
                            <div class="list-group-item">
                                <div class="form-check">
                                    <input
                                        class="form-check-input"
                                        type="checkbox"
                                        value="${escapeHtml(task)}"
                                        id="${checkboxId}"
                                        data-survey-task-checkbox
                                        data-survey-task="${escapeHtml(task)}"
                                        ${checked}
                                    >
                                    <label class="form-check-label w-100" for="${checkboxId}">
                                        <div class="d-flex flex-column flex-md-row align-items-md-start justify-content-between gap-2">
                                            <div>
                                                <strong>${escapeHtml(task)}</strong>
                                                ${review ? '<span class="badge bg-warning text-dark ms-2">Out of range</span>' : '<span class="badge bg-success ms-2">Ready</span>'}
                                            </div>
                                            <div class="d-flex flex-wrap gap-2">
                                                ${runBadge}
                                            </div>
                                        </div>
                                        ${review ? `
                                            <div class="small mt-2">
                                                <div class="fw-semibold">Required first: validate and fix source values, then run Preview again.</div>
                                                <div class="text-muted">${escapeHtml(String(review.message || 'Value review required before converting this survey.'))}</div>
                                                ${review.item_id ? `<div class="mt-1">Item: <code>${escapeHtml(String(review.item_id))}</code></div>` : ''}
                                                ${review.raw_value !== undefined && review.raw_value !== null ? `<div>Observed value: <code>${escapeHtml(String(review.raw_value))}</code></div>` : ''}
                                                ${hasConfiguredOffset && hasAdjustedValue ? `<div>Configured offset: <code>${escapeHtml(configuredOffset > 0 ? `+${configuredOffset}` : String(configuredOffset))}</code> -> adjusted value: <code>${escapeHtml(String(adjustedValue))}</code></div>` : ''}
                                                ${rawValueValidWithoutOffset ? '<div class="text-warning">This sampled value is valid before offset. Check offset direction and selected template version.</div>' : ''}
                                                ${expectedLevels.length > 0 ? `<div>Expected levels: <code>${expectedLevels.map((value) => escapeHtml(String(value))).join('</code>, <code>')}</code></div>` : ''}
                                                ${outOfRangeRateText ? `<div>Out-of-range share: <code>${escapeHtml(outOfRangeRateText)}</code></div>` : ''}
                                                <div class="text-muted mt-1">If this survey should not be converted yet, deselect it before converting.</div>
                                                ${suggestedOffsets.length > 0 && structuralOffsetLikely ? `<div class="text-muted mt-1">Advanced-only fallback (expert use): manual task value offset is allowed only when you can independently confirm a full-task scale shift (for example 1-4 in source vs 0-3 in template). Possible offset: <code>${suggestedOffsets.join('</code>, <code>')}</code>. Never use this to ignore incorrect source values.</div>` : '<div class="text-muted mt-1">Advanced-only fallback (expert use): use manual task value offset only when you can independently confirm a full-task shifted scale. Never use this to bypass incorrect source values.</div>'}
                                            </div>
                                        ` : ''}
                                    </label>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }

    function bindSurveyTaskSelectionControls() {
        if (!conversionSummaryBody) return;

        const syncSelectionFromDom = () => {
            const selectedTasks = Array.from(
                conversionSummaryBody.querySelectorAll('[data-survey-task-checkbox]')
            )
                .filter((checkbox) => checkbox.checked)
                .map((checkbox) => normalizeSurveyTaskName(checkbox.getAttribute('data-survey-task')))
                .filter(Boolean);

            if (typeof setSurveyPreviewSelectedTasks === 'function') {
                setSurveyPreviewSelectedTasks(selectedTasks);
            }
            updateSurveyTaskSelectionSummaryText();
            updateConvertBtn();
        };

        conversionSummaryBody.querySelectorAll('[data-survey-task-checkbox]').forEach((checkbox) => {
            checkbox.addEventListener('change', syncSelectionFromDom);
        });

        const selectAllBtn = conversionSummaryBody.querySelector('[data-survey-task-select-all]');
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => {
                conversionSummaryBody.querySelectorAll('[data-survey-task-checkbox]').forEach((checkbox) => {
                    checkbox.checked = true;
                });
                syncSelectionFromDom();
            });
        }

        const clearAllBtn = conversionSummaryBody.querySelector('[data-survey-task-clear-all]');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', () => {
                conversionSummaryBody.querySelectorAll('[data-survey-task-checkbox]').forEach((checkbox) => {
                    checkbox.checked = false;
                });
                syncSelectionFromDom();
            });
        }

        conversionSummaryBody.querySelectorAll('[data-survey-open-advanced]').forEach((button) => {
            button.addEventListener('click', () => {
                openAdvancedOptionsValueOffsetEditor();
            });
        });
    }

    function displayConversionSummary(summary) {
        if (!conversionSummaryContainer || !conversionSummaryBody || !summary) return;

        let html = '';

        const surveyTasks = Array.isArray(summary.survey_tasks) ? summary.survey_tasks : [];
        if (surveyTasks.length > 0) {
            html += renderSurveyTaskReviewSummary(surveyTasks);
        }

        const matches = summary.template_matches;
        if (matches && Object.keys(matches).length > 0) {
            html += `<h6 class="mb-2"><i class="fas fa-puzzle-piece me-1"></i>Matched Templates</h6>`;
            html += `<table class="table table-sm table-bordered mb-3"><thead><tr><th>Survey Group</th><th>Template</th><th>Confidence</th></tr></thead><tbody>`;
            for (const [group, info] of Object.entries(matches)) {
                if (!info) continue;
                const tmpl = info.template_key || info.template || info.matched_template || 'None';
                const conf = info.confidence || info.match_confidence || 'unknown';
                let badgeClass = 'bg-secondary';
                if (conf === 'exact' || conf === 'high') badgeClass = 'bg-success';
                else if (conf === 'medium') badgeClass = 'bg-warning text-dark';
                else if (conf === 'low') badgeClass = 'bg-danger';
                html += `<tr><td>${group}</td><td><code>${tmpl}</code></td><td><span class="badge ${badgeClass}">${conf}</span></td></tr>`;
            }
            html += `</tbody></table>`;
        }

        const toolCols = summary.tool_columns;
        if (toolCols && toolCols.length > 0) {
            html += `<h6 class="mb-2"><i class="fas fa-wrench me-1"></i>Tool-Specific Columns <span class="badge bg-secondary">${toolCols.length}</span></h6>`;
            html += `<div class="mb-3"><details><summary class="text-muted small" style="cursor:pointer;">LimeSurvey system columns (click to expand)</summary>`;
            html += `<div class="mt-1"><code>${toolCols.join('</code>, <code>')}</code></div></details></div>`;
        }

        const nearMatchCandidates = summary.near_match_candidates;
        if (nearMatchCandidates && nearMatchCandidates.length > 0) {
            const applied = Boolean(summary.near_match_applied);
            const stateBadgeClass = applied ? 'bg-success' : 'bg-info text-dark';
            const stateLabel = applied ? 'Applied' : 'Available';
            const previewLimit = 12;
            const previewCandidates = nearMatchCandidates.slice(0, previewLimit);
            const hiddenCount = nearMatchCandidates.length - previewCandidates.length;
            html += `<h6 class="mb-2"><i class="fas fa-arrows-left-right me-1"></i>Near Item Matches <span class="badge ${stateBadgeClass}">${stateLabel}</span> <span class="badge bg-secondary">${nearMatchCandidates.length}</span></h6>`;
            html += `<div class="mb-3"><details><summary class="text-muted small" style="cursor:pointer;">Show near-match mappings</summary><div class="mt-2">`;
            html += previewCandidates
                .map((candidate) => {
                    const source = escapeHtml(String(candidate && candidate.source_column || '').trim());
                    const target = escapeHtml(String(candidate && candidate.target_item || '').trim());
                    const task = escapeHtml(String(candidate && candidate.task || '').trim());
                    const run = (candidate && candidate.run !== undefined && candidate.run !== null)
                        ? `, run ${escapeHtml(String(candidate.run))}`
                        : '';
                    return `<div><code>${source}</code> &rarr; <code>${target}</code> <span class="text-muted small">(task ${task}${run})</span></div>`;
                })
                .join('');
            if (hiddenCount > 0) {
                html += `<div class="text-muted small mt-1">...and ${hiddenCount} more</div>`;
            }
            html += `</div></details><small class="text-muted">Near matches only allow minimal formatting differences and require count-safe mapping.</small></div>`;
        }

        const unknownCols = summary.unknown_columns;
        if (unknownCols && unknownCols.length > 0) {
            const selectedSurveyFilter = (convertDatasetName && convertDatasetName.value)
                ? String(convertDatasetName.value).trim()
                : '';
            html += `<h6 class="mb-2"><i class="fas fa-question-circle me-1 text-warning"></i>Unmatched Columns <span class="badge bg-warning text-dark">${unknownCols.length}</span></h6>`;
            if (selectedSurveyFilter) {
                const previewLimit = 20;
                const previewCols = unknownCols.slice(0, previewLimit);
                const hiddenCount = unknownCols.length - previewCols.length;
                html += `<small class="text-muted d-block mb-1">Task filter active: <code>${escapeHtml(selectedSurveyFilter)}</code>. Most unmatched columns are likely from other tasks and are hidden by default.</small>`;
                html += `<details class="mb-1"><summary class="text-muted small" style="cursor:pointer;">Show unmatched column names</summary>`;
                html += `<div class="mt-2"><code>${previewCols.join('</code>, <code>')}</code></div>`;
                if (hiddenCount > 0) {
                    html += `<div class="text-muted small mt-1">...and ${hiddenCount} more</div>`;
                }
                html += `</details>`;
            } else {
                html += `<div class="mb-1"><code>${unknownCols.join('</code>, <code>')}</code></div>`;
            }
            html += `<small class="text-muted">These columns were not assigned to any template.</small>`;
        }

        if (html) {
            conversionSummaryBody.innerHTML = html;
            conversionSummaryContainer.classList.remove('d-none');
            bindSurveyTaskSelectionControls();

            if (toggleSummaryBtn) {
                toggleSummaryBtn.onclick = function() {
                    const body = conversionSummaryBody;
                    const icon = toggleSummaryBtn.querySelector('i');
                    if (body.style.display === 'none') {
                        body.style.display = '';
                        icon.className = 'fas fa-chevron-down';
                    } else {
                        body.style.display = 'none';
                        icon.className = 'fas fa-chevron-right';
                    }
                };
            }
        }
    }

    return {
        displayConversionSummary,
    };
}
