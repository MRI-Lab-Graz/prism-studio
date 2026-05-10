export function createSurveyTemplateResultsController({
    escapeHtml,
}) {
    function displayTemplateSingle(data) {
        const container = document.getElementById('templateResultSingle');
        if (!container) return;

        container.classList.remove('d-none');
        document.getElementById('templateQuestionCount').textContent = `${data.question_count} questions`;

        // Show template match info if available
        const matchContainer = document.getElementById('templateSingleMatch');
        if (matchContainer) matchContainer.remove();
        const m = data.template_match;
        if (m) {
            const badgeClass = {exact: 'bg-success', high: 'bg-success', medium: 'bg-warning text-dark', low: 'bg-secondary'}[m.confidence] || 'bg-secondary';
            const icon = {exact: 'fa-check-circle', high: 'fa-check', medium: 'fa-question-circle', low: 'fa-minus-circle'}[m.confidence] || 'fa-circle';
            const actionLabel = {use_library: 'Use library template instead', review: 'Review differences', create_new: 'Create new template'}[m.suggested_action] || '';
            const details = [];
            if (m.overlap_count !== undefined) details.push(`${m.overlap_count}/${m.template_items} items match`);
            if (m.levels_match === true) details.push('levels verified');
            const matchDiv = document.createElement('div');
            matchDiv.id = 'templateSingleMatch';
            matchDiv.className = 'alert alert-info py-2 mt-2 mb-0';
            const srcLabel = m.source === 'project' ? 'project template' : 'library template';
            const srcIcon = m.source === 'project' ? 'fa-folder' : 'fa-globe';
            const leadIcon = document.createElement('i');
            leadIcon.className = `fas ${icon} me-1`;
            matchDiv.appendChild(leadIcon);

            const confidenceBadge = document.createElement('span');
            confidenceBadge.className = `badge ${badgeClass} me-2`;
            confidenceBadge.textContent = m.confidence || 'unknown';
            matchDiv.appendChild(confidenceBadge);

            matchDiv.appendChild(document.createTextNode(`Matches ${srcLabel}: `));
            const strong = document.createElement('strong');
            strong.textContent = m.template_key || '';
            matchDiv.appendChild(strong);
            matchDiv.appendChild(document.createTextNode(' '));

            const sourceBadge = document.createElement('span');
            sourceBadge.className = 'badge bg-light text-dark border ms-1';
            const sourceBadgeIcon = document.createElement('i');
            sourceBadgeIcon.className = `fas ${srcIcon} me-1`;
            sourceBadge.appendChild(sourceBadgeIcon);
            sourceBadge.appendChild(document.createTextNode(m.source === 'project' ? 'project' : 'library'));
            matchDiv.appendChild(sourceBadge);

            const detailText = details.join(', ');
            if (detailText) {
                matchDiv.appendChild(document.createTextNode(` (${detailText})`));
            }
            if (actionLabel) {
                matchDiv.appendChild(document.createTextNode(' - '));
                const em = document.createElement('em');
                em.textContent = actionLabel;
                matchDiv.appendChild(em);
            }
            container.querySelector('.alert')?.after(matchDiv);
        } else if (m === null) {
            const matchDiv = document.createElement('div');
            matchDiv.id = 'templateSingleMatch';
            matchDiv.className = 'alert alert-light py-2 mt-2 mb-0 border';
            const iconEl = document.createElement('i');
            iconEl.className = 'fas fa-plus-circle me-1';
            matchDiv.appendChild(iconEl);
            matchDiv.appendChild(document.createTextNode('No matching library template found - this will be a new template.'));
            container.querySelector('.alert')?.after(matchDiv);
        }

        // Setup preview button
        const previewBtn = document.getElementById('templatePreviewBtn');
        const previewDiv = document.getElementById('templatePreview');
        const previewContent = document.getElementById('templatePreviewContent');

        if (previewBtn && previewDiv && previewContent) {
            previewBtn.onclick = () => {
                previewDiv.classList.toggle('d-none');
                previewContent.textContent = JSON.stringify(data.prism_json, null, 2);
            };
        }

        // Setup download button
        const downloadBtn = document.getElementById('templateDownloadBtn');
        if (downloadBtn) {
            downloadBtn.onclick = () => {
                const blob = new Blob([JSON.stringify(data.prism_json, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = data.suggested_filename || 'survey-template.json';
                a.click();
                URL.revokeObjectURL(url);
            };
        }
    }

    function setupTemplateSaveToProject(data, mode) {
        const saveBtn = mode === 'groups'
            ? document.getElementById('templateSaveToProjectBtn')
            : document.getElementById('templateSaveQuestionsToProjectBtn');

        if (!saveBtn) return;

        saveBtn.onclick = async () => {
            const templates = [];
            const savedKeys = new Set();  // Deduplicate runs of same template

            if (mode === 'groups') {
                for (const [name, info] of Object.entries(data.questionnaires || {})) {
                    const m = info.template_match;

                    // Skip participants templates (handled separately)
                    if (m && m.is_participants) continue;

                    // Deduplicate: if multiple groups matched the same library
                    // template (e.g. run1/run2/run3 of BRS), save only once
                    // using the library filename
                    if (m && m.template_key) {
                        if (savedKeys.has(m.template_key)) continue;
                        savedKeys.add(m.template_key);
                        templates.push({
                            filename: m.template_path || info.suggested_filename || `survey-${name}.json`,
                            content: info.prism_json
                        });
                    } else {
                        templates.push({
                            filename: info.suggested_filename || `survey-${name}.json`,
                            content: info.prism_json
                        });
                    }
                }
            } else {
                for (const [code, qData] of Object.entries(data.questions || {})) {
                    if (qData.prism_json) {
                        templates.push({
                            filename: qData.suggested_filename || `survey-${code}.json`,
                            content: qData.prism_json
                        });
                    }
                }
            }

            if (templates.length === 0) {
                alert('No templates to save (all matched library templates or participants).');
                return;
            }

            try {
                const response = await fetch('/api/limesurvey-save-to-project', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ templates })
                });
                const result = await response.json();

                const successDiv = document.getElementById('templateSaveSuccess');
                const msgSpan = document.getElementById('templateSaveSuccessMessage');
                if (result.success) {
                    successDiv?.classList.remove('d-none');
                    const skipped = Object.keys(data.questionnaires || {}).length - templates.length;
                    let msg = `Saved ${result.saved_files?.length || templates.length} template(s) to ${result.library_path}`;
                    if (skipped > 0) msg += ` (${skipped} duplicate run(s) skipped)`;
                    msgSpan.textContent = msg;
                } else {
                    alert('Error: ' + (result.error || 'Unknown error'));
                }
            } catch (e) {
                alert('Error saving: ' + e.message);
            }
        };
    }

    function displayTemplateGroups(data) {
        const container = document.getElementById('templateResultGroups');
        if (!container) return;

        container.classList.remove('d-none');
        document.getElementById('templateGroupCount').textContent = `${data.questionnaire_count} groups`;
        document.getElementById('templateTotalQuestions').textContent = `${data.total_questions} questions`;

        const listEl = document.getElementById('templateGroupList');
        if (listEl) {
            listEl.innerHTML = '';
            for (const [name, info] of Object.entries(data.questionnaires || {})) {
                const card = document.createElement('div');
                card.className = 'col-md-4';

                // Build template match badge if available
                let matchHtml = '';
                const m = info.template_match;
                if (m) {
                    const badgeClass = {
                        exact: 'bg-success',
                        high: 'bg-success',
                        medium: 'bg-warning text-dark',
                        low: 'bg-secondary'
                    }[m.confidence] || 'bg-secondary';
                    const icon = {
                        exact: 'fa-check-circle',
                        high: 'fa-check',
                        medium: 'fa-question-circle',
                        low: 'fa-minus-circle'
                    }[m.confidence] || 'fa-circle';
                    const details = [];
                    if (m.overlap_count !== undefined) details.push(`${m.overlap_count}/${m.template_items} items`);
                    if (m.levels_match === true) details.push('levels verified');
                    if (m.runs_detected > 1) details.push(`${m.runs_detected} runs`);
                    const detailStr = details.length ? details.join(', ') : '';
                    const diffParts = [];
                    if (m.only_in_import && m.only_in_import.length) diffParts.push(`+${m.only_in_import.length} extra`);
                    if (m.only_in_library && m.only_in_library.length) diffParts.push(`${m.only_in_library.length} missing`);
                    const diffHtml = diffParts.length
                        ? `<small class="d-block text-muted" style="font-size:0.7rem">${diffParts.join(', ')}</small>`
                        : '';
                    // Show "Use Library" button for exact/high matches (but not for participants matches)
                    const sourceLabel = m.source === 'project' ? 'project' : 'library';
                    const sourceIcon = m.source === 'project' ? 'fa-folder' : 'fa-globe';
                    const safeName = escapeHtml(name || '');
                    const safeTemplateKey = escapeHtml(m.template_key || '');
                    const safeDetailStr = escapeHtml(detailStr);
                    const safeSourceLabel = escapeHtml(sourceLabel);
                    const safeConfidence = escapeHtml(m.confidence || 'unknown');
                    // Don't show "Use library version" for participants matches - there's no participants template in the library
                    const useLibBtn = (m.suggested_action === 'use_library' && !m.is_participants)
                        ? `<button class="btn btn-sm btn-outline-primary use-library-btn mt-1" data-name="${safeName}" data-template-key="${safeTemplateKey}" data-is-participants="${m.is_participants || false}"><i class="fas fa-book me-1"></i>Use ${safeSourceLabel} version</button>`
                        : '';
                    matchHtml = `
                        <div class="mt-1 pt-1 border-top">
                            <span class="badge ${badgeClass}" title="${safeDetailStr}">
                                <i class="fas ${icon} me-1"></i>${safeConfidence} match: ${safeTemplateKey}
                            </span>
                            <span class="badge bg-light text-dark border ms-1" title="Matched from ${safeSourceLabel}">
                                <i class="fas ${sourceIcon} me-1"></i>${safeSourceLabel}
                            </span>
                            ${diffHtml}
                            ${useLibBtn}
                        </div>
                    `;
                } else if (m === null) {
                    matchHtml = `
                        <div class="mt-1 pt-1 border-top">
                            <span class="badge bg-light text-dark border">
                                <i class="fas fa-plus-circle me-1"></i>No library match
                            </span>
                        </div>
                    `;
                }

                const safeName = escapeHtml(name || '');
                const safeQuestionCount = escapeHtml(String(info.question_count ?? ''));
                card.innerHTML = `
                    <div class="card h-100">
                        <div class="card-body py-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${safeName}</strong>
                                    <small class="d-block text-muted">${safeQuestionCount} questions</small>
                                </div>
                                <button class="btn btn-sm btn-outline-success download-template-btn" data-name="${safeName}">
                                    <i class="fas fa-download"></i>
                                </button>
                            </div>
                            ${matchHtml}
                        </div>
                    </div>
                `;
                listEl.appendChild(card);
            }

            // "Use Library" button handlers - swap generated template with library version
            listEl.querySelectorAll('.use-library-btn').forEach(btn => {
                btn.onclick = async () => {
                    const groupName = btn.dataset.name;
                    const templateKey = btn.dataset.templateKey;
                    btn.disabled = true;
                    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Loading...';
                    try {
                        const resp = await fetch(`/api/library-template/${encodeURIComponent(templateKey)}`);
                        const result = await resp.json();
                        if (result.success && result.prism_json) {
                            // Swap the template in the data object
                            data.questionnaires[groupName].prism_json = result.prism_json;
                            data.questionnaires[groupName].suggested_filename = result.filename;
                            // Update the card visually
                            const matchDiv = btn.closest('.border-top');
                            if (matchDiv) {
                                matchDiv.replaceChildren();
                                const badge = document.createElement('span');
                                badge.className = 'badge bg-success';
                                const badgeIcon = document.createElement('i');
                                badgeIcon.className = 'fas fa-check-circle me-1';
                                badge.appendChild(badgeIcon);
                                badge.appendChild(document.createTextNode(`Using library: ${templateKey || ''}`));
                                matchDiv.appendChild(badge);

                                const filenameEl = document.createElement('small');
                                filenameEl.className = 'd-block text-muted mt-1';
                                filenameEl.textContent = result.filename || '';
                                matchDiv.appendChild(filenameEl);
                            }
                        } else {
                            btn.disabled = false;
                            btn.innerHTML = '<i class="fas fa-book me-1"></i>Use library version';
                            alert('Error: ' + (result.error || 'Failed to load library template'));
                        }
                    } catch (e) {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="fas fa-book me-1"></i>Use library version';
                        alert('Error loading template: ' + e.message);
                    }
                };
            });

            // Add download handlers
            listEl.querySelectorAll('.download-template-btn').forEach(btn => {
                btn.onclick = () => {
                    const name = btn.dataset.name;
                    const info = data.questionnaires[name];
                    if (info) {
                        const blob = new Blob([JSON.stringify(info.prism_json, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = info.suggested_filename || `survey-${name}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                    }
                };
            });
        }

        // Download all as ZIP (deduplicate runs of the same template)
        const downloadAllBtn = document.getElementById('templateDownloadAllBtn');
        if (downloadAllBtn) {
            downloadAllBtn.onclick = async () => {
                const JSZip = window.JSZip;
                if (!JSZip) {
                    alert('JSZip not loaded');
                    return;
                }
                const zip = new JSZip();
                const addedKeys = new Set();
                for (const [name, info] of Object.entries(data.questionnaires || {})) {
                    const m = info.template_match;
                    // Skip participants templates
                    if (m && m.is_participants) continue;
                    // Deduplicate runs: use library filename, skip if already added
                    const filename = (m && m.template_path) ? m.template_path : (info.suggested_filename || `survey-${name}.json`);
                    const dedupeKey = (m && m.template_key) ? m.template_key : filename;
                    if (addedKeys.has(dedupeKey)) continue;
                    addedKeys.add(dedupeKey);
                    zip.file(filename, JSON.stringify(info.prism_json, null, 2));
                }
                const blob = await zip.generateAsync({ type: 'blob' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'survey-templates.zip';
                a.click();
                URL.revokeObjectURL(url);
            };
        }

        // Save to project button
        setupTemplateSaveToProject(data, 'groups');
    }

    function displayTemplateQuestions(data) {
        const container = document.getElementById('templateResultQuestions');
        if (!container) return;

        container.classList.remove('d-none');
        document.getElementById('templateIndividualCount').textContent = `${data.question_count} templates`;

        const listEl = document.getElementById('templateQuestionsList');
        if (listEl) {
            listEl.innerHTML = '';
            for (const [groupName, groupInfo] of Object.entries(data.by_group || {})) {
                const groupDiv = document.createElement('div');
                groupDiv.className = 'col-12 mb-2';
                const heading = document.createElement('h6');
                heading.className = 'text-muted';
                heading.textContent = groupName;
                groupDiv.appendChild(heading);
                listEl.appendChild(groupDiv);

                for (const q of groupInfo.questions || []) {
                    const qData = data.questions[q.code];
                    if (!qData) continue;

                    const card = document.createElement('div');
                    card.className = 'col-md-3';

                    const cardInner = document.createElement('div');
                    cardInner.className = 'card h-100';
                    const cardBody = document.createElement('div');
                    cardBody.className = 'card-body py-2';
                    const row = document.createElement('div');
                    row.className = 'd-flex justify-content-between align-items-center';

                    const textWrap = document.createElement('div');
                    const strong = document.createElement('strong');
                    strong.textContent = q.code || '';
                    textWrap.appendChild(strong);
                    const small = document.createElement('small');
                    small.className = 'd-block text-muted';
                    small.textContent = `${q.type || ''} (${String(q.item_count ?? '')} items)`;
                    textWrap.appendChild(small);

                    const button = document.createElement('button');
                    button.className = 'btn btn-sm btn-outline-success download-q-btn';
                    button.dataset.code = q.code || '';
                    const buttonIcon = document.createElement('i');
                    buttonIcon.className = 'fas fa-download';
                    button.appendChild(buttonIcon);

                    row.appendChild(textWrap);
                    row.appendChild(button);
                    cardBody.appendChild(row);
                    cardInner.appendChild(cardBody);
                    card.appendChild(cardInner);
                    listEl.appendChild(card);
                }
            }

            // Add download handlers
            listEl.querySelectorAll('.download-q-btn').forEach(btn => {
                btn.onclick = () => {
                    const code = btn.dataset.code;
                    const qData = data.questions[code];
                    if (qData && qData.prism_json) {
                        const blob = new Blob([JSON.stringify(qData.prism_json, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = qData.suggested_filename || `survey-${code}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                    }
                };
            });
        }

        // Download all as ZIP
        const downloadBtn = document.getElementById('templateDownloadQuestionsBtn');
        if (downloadBtn) {
            downloadBtn.onclick = async () => {
                const JSZip = window.JSZip;
                if (!JSZip) {
                    alert('JSZip not loaded');
                    return;
                }
                const zip = new JSZip();
                for (const [code, qData] of Object.entries(data.questions || {})) {
                    if (qData.prism_json) {
                        zip.file(qData.suggested_filename || `survey-${code}.json`, JSON.stringify(qData.prism_json, null, 2));
                    }
                }
                const blob = await zip.generateAsync({ type: 'blob' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'survey-question-templates.zip';
                a.click();
                URL.revokeObjectURL(url);
            };
        }

        // Save to project button
        setupTemplateSaveToProject(data, 'questions');
    }

    return {
        displayTemplateSingle,
        displayTemplateGroups,
        displayTemplateQuestions,
    };
}
