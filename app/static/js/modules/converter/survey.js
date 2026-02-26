/**
 * Converter Survey Module
 * Handles LimeSurvey quick import actions.
 */

export function initLimeSurveyQuickImport() {
    const lssFile = document.getElementById('lssFile');
    const lssTaskName = document.getElementById('lssTaskName');
    const lssConvertBtn = document.getElementById('lssConvertBtn');
    const lssError = document.getElementById('lssError');

    if (!lssFile || !lssConvertBtn || !lssError) {
        return;
    }

    const lssResultSingle = document.getElementById('lssResultSingle');
    const lssQuestionCount = document.getElementById('lssQuestionCount');
    const lssPreviewBtn = document.getElementById('lssPreviewBtn');
    const lssDownloadBtn = document.getElementById('lssDownloadBtn');
    const lssPreview = document.getElementById('lssPreview');
    const lssPreviewContent = document.getElementById('lssPreviewContent');

    const lssResultMultiple = document.getElementById('lssResultMultiple');
    const lssGroupCount = document.getElementById('lssGroupCount');
    const lssTotalQuestions = document.getElementById('lssTotalQuestions');
    const lssDownloadAllBtn = document.getElementById('lssDownloadAllBtn');
    const lssQuestionnaireList = document.getElementById('lssQuestionnaireList');

    const lssResultQuestions = document.getElementById('lssResultQuestions');
    const lssIndividualCount = document.getElementById('lssIndividualCount');
    const lssDownloadAllQuestionsBtn = document.getElementById('lssDownloadAllQuestionsBtn');
    const lssQuestionsList = document.getElementById('lssQuestionsList');

    const lssSaveGroupsToProjectBtn = document.getElementById('lssSaveGroupsToProjectBtn');
    const lssSaveQuestionsToProjectBtn = document.getElementById('lssSaveQuestionsToProjectBtn');
    const lssSaveSuccess = document.getElementById('lssSaveSuccess');
    const lssSaveSuccessMessage = document.getElementById('lssSaveSuccessMessage');

    let lssConvertedData = null;
    let lssSuggestedFilename = 'survey.json';
    let lssQuestionnaires = null;
    let lssIndividualQuestions = null;

    function getSelectedLssMode() {
        const checked = document.querySelector('input[name="lssMode"]:checked');
        return checked ? checked.value : 'groups';
    }

    lssFile.addEventListener('change', function() {
        lssConvertBtn.disabled = !lssFile.files.length;
        lssResultSingle?.classList.add('d-none');
        lssResultMultiple?.classList.add('d-none');
        lssResultQuestions?.classList.add('d-none');
        lssError.classList.add('d-none');
        lssPreview?.classList.add('d-none');
    });

    lssConvertBtn.addEventListener('click', async function() {
        if (!lssFile.files.length) return;

        const originalText = lssConvertBtn.innerHTML;
        lssConvertBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Converting...';
        lssConvertBtn.disabled = true;
        lssError.classList.add('d-none');
        lssResultSingle?.classList.add('d-none');
        lssResultMultiple?.classList.add('d-none');
        lssResultQuestions?.classList.add('d-none');

        const formData = new FormData();
        formData.append('file', lssFile.files[0]);
        formData.append('task_name', lssTaskName?.value || '');
        formData.append('mode', getSelectedLssMode());

        try {
            const response = await fetch('/api/limesurvey-to-prism', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.success) {
                if (data.mode === 'questions') {
                    lssIndividualQuestions = data.questions;
                    if (lssIndividualCount) {
                        lssIndividualCount.textContent = `${data.question_count} question templates`;
                    }

                    if (lssQuestionsList) {
                        lssQuestionsList.innerHTML = '';

                        const grouped = {};
                        for (const [code, qData] of Object.entries(data.questions)) {
                            const groupName = qData.group_name || 'Ungrouped';
                            if (!grouped[groupName]) grouped[groupName] = [];
                            grouped[groupName].push({code, ...qData});
                        }

                        const sortedGroups = Object.entries(grouped).sort((a, b) => {
                            const orderA = a[1][0]?.group_order || 0;
                            const orderB = b[1][0]?.group_order || 0;
                            return orderA - orderB;
                        });

                        for (const [groupName, questions] of sortedGroups) {
                            const groupHeader = document.createElement('div');
                            groupHeader.className = 'col-12 mt-2';
                            groupHeader.innerHTML = `<h6 class="text-muted border-bottom pb-1"><i class="fas fa-folder me-1"></i>${groupName}</h6>`;
                            lssQuestionsList.appendChild(groupHeader);

                            questions.sort((a, b) => (a.question_order || 0) - (b.question_order || 0));

                            for (const q of questions) {
                                const card = document.createElement('div');
                                card.className = 'col-md-3';
                                const questionType = q.question_type || '';
                                const itemCount = q.item_count || 1;
                                const itemBadge = itemCount > 1 ? `<span class="badge bg-secondary ms-1">${itemCount} items</span>` : '';
                                const questionText = q.prism_json?.Study?.Description || '';
                                card.innerHTML = `
                                    <div class="card h-100 card-hover">
                                        <div class="card-body py-2">
                                            <div class="d-flex justify-content-between align-items-start">
                                                <div class="small fw-bold text-truncate" title="${q.code}">${q.code}</div>
                                                <span class="badge bg-info small">${questionType}</span>
                                            </div>
                                            <div class="text-muted x-small text-truncate" title="${questionText}">${questionText}</div>
                                            ${itemBadge}
                                            <div class="mt-1">
                                                <div class="btn-group btn-group-sm">
                                                    <button class="btn btn-outline-secondary btn-sm lss-preview-question" data-code="${q.code}" title="Preview">
                                                        <i class="fas fa-eye"></i>
                                                    </button>
                                                    <button class="btn btn-outline-success btn-sm lss-download-question" data-code="${q.code}" data-filename="${q.suggested_filename}" title="Download">
                                                        <i class="fas fa-download"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                `;
                                lssQuestionsList.appendChild(card);
                            }
                        }
                    }

                    lssResultQuestions?.classList.remove('d-none');
                } else if (data.mode === 'groups') {
                    lssQuestionnaires = data.questionnaires;
                    if (lssGroupCount) {
                        lssGroupCount.textContent = `${data.questionnaire_count} questionnaires`;
                    }
                    if (lssTotalQuestions) {
                        lssTotalQuestions.textContent = `${data.total_questions} total questions`;
                    }

                    if (lssQuestionnaireList) {
                        lssQuestionnaireList.innerHTML = '';
                        for (const [name, qData] of Object.entries(data.questionnaires)) {
                            const card = document.createElement('div');
                            card.className = 'col-md-4';
                            card.innerHTML = `
                                <div class="card h-100">
                                    <div class="card-body">
                                        <h6 class="card-title"><i class="fas fa-file-alt me-1 text-success"></i>${name}</h6>
                                        <p class="card-text small text-muted">${qData.question_count} questions</p>
                                        <div class="btn-group btn-group-sm">
                                            <button class="btn btn-outline-secondary lss-preview-single" data-name="${name}">
                                                <i class="fas fa-eye"></i>
                                            </button>
                                            <button class="btn btn-outline-success lss-download-single" data-name="${name}" data-filename="${qData.suggested_filename}">
                                                <i class="fas fa-download"></i>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            `;
                            lssQuestionnaireList.appendChild(card);
                        }
                    }

                    lssResultMultiple?.classList.remove('d-none');
                } else {
                    lssConvertedData = data.prism_json;
                    lssSuggestedFilename = data.suggested_filename;
                    if (lssQuestionCount) {
                        lssQuestionCount.textContent = `${data.question_count} questions`;
                    }
                    if (lssPreviewContent) {
                        lssPreviewContent.textContent = JSON.stringify(lssConvertedData, null, 2);
                    }
                    lssResultSingle?.classList.remove('d-none');
                }
            } else {
                lssError.textContent = data.error || 'Conversion failed';
                lssError.classList.remove('d-none');
            }
        } catch (err) {
            lssError.textContent = 'Error: ' + err.message;
            lssError.classList.remove('d-none');
        } finally {
            lssConvertBtn.innerHTML = originalText;
            lssConvertBtn.disabled = false;
        }
    });

    if (lssQuestionnaireList) {
        lssQuestionnaireList.addEventListener('click', function(e) {
            const previewBtn = e.target.closest('.lss-preview-single');
            const downloadBtn = e.target.closest('.lss-download-single');

            if (previewBtn) {
                const name = previewBtn.dataset.name;
                if (lssQuestionnaires && lssQuestionnaires[name]) {
                    alert(JSON.stringify(lssQuestionnaires[name].prism_json, null, 2).substring(0, 2000) + '...');
                }
            }

            if (downloadBtn) {
                const name = downloadBtn.dataset.name;
                const filename = downloadBtn.dataset.filename;
                if (lssQuestionnaires && lssQuestionnaires[name]) {
                    downloadJson(lssQuestionnaires[name].prism_json, filename);
                }
            }
        });
    }

    if (lssPreviewBtn) {
        lssPreviewBtn.addEventListener('click', function() {
            lssPreview?.classList.toggle('d-none');
            const icon = lssPreviewBtn.querySelector('i');
            if (icon && lssPreview) {
                icon.className = lssPreview.classList.contains('d-none')
                    ? 'fas fa-eye me-1'
                    : 'fas fa-eye-slash me-1';
            }
        });
    }

    if (lssDownloadBtn) {
        lssDownloadBtn.addEventListener('click', function() {
            if (lssConvertedData) downloadJson(lssConvertedData, lssSuggestedFilename);
        });
    }

    if (lssDownloadAllBtn) {
        lssDownloadAllBtn.addEventListener('click', function() {
            if (!lssQuestionnaires) return;
            downloadAllAsZip(lssQuestionnaires);
        });
    }

    if (lssQuestionsList) {
        lssQuestionsList.addEventListener('click', function(e) {
            const previewBtn = e.target.closest('.lss-preview-question');
            const downloadBtn = e.target.closest('.lss-download-question');

            if (previewBtn) {
                const code = previewBtn.dataset.code;
                if (lssIndividualQuestions && lssIndividualQuestions[code]) {
                    const json = JSON.stringify(lssIndividualQuestions[code].prism_json, null, 2);
                    alert(json.substring(0, 3000) + (json.length > 3000 ? '\n...(truncated)' : ''));
                }
            }

            if (downloadBtn) {
                const code = downloadBtn.dataset.code;
                const filename = downloadBtn.dataset.filename;
                if (lssIndividualQuestions && lssIndividualQuestions[code]) {
                    downloadJson(lssIndividualQuestions[code].prism_json, filename);
                }
            }
        });
    }

    if (lssDownloadAllQuestionsBtn) {
        lssDownloadAllQuestionsBtn.addEventListener('click', function() {
            if (!lssIndividualQuestions) return;
            downloadAllQuestionsAsZip(lssIndividualQuestions);
        });
    }

    async function saveTemplatesToProject(templates) {
        try {
            const response = await fetch('/api/limesurvey-save-to-project', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ templates })
            });
            const data = await response.json();

            if (data.success) {
                if (lssSaveSuccessMessage) {
                    lssSaveSuccessMessage.textContent = `Saved ${data.saved_count} template(s) to ${data.library_path}`;
                }
                lssSaveSuccess?.classList.remove('d-none');
                return true;
            }

            alert('Error: ' + (data.error || 'Failed to save templates'));
            return false;
        } catch (err) {
            alert('Error saving to project: ' + err.message);
            return false;
        }
    }

    if (lssSaveGroupsToProjectBtn) {
        lssSaveGroupsToProjectBtn.addEventListener('click', async function() {
            if (!lssQuestionnaires) return;

            const templates = Object.entries(lssQuestionnaires).map(([name, qData]) => ({
                filename: qData.suggested_filename,
                content: qData.prism_json
            }));

            lssSaveGroupsToProjectBtn.disabled = true;
            lssSaveGroupsToProjectBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';

            await saveTemplatesToProject(templates);

            lssSaveGroupsToProjectBtn.disabled = false;
            lssSaveGroupsToProjectBtn.innerHTML = '<i class="fas fa-folder-plus me-1"></i>Save to Project';
        });
    }

    if (lssSaveQuestionsToProjectBtn) {
        lssSaveQuestionsToProjectBtn.addEventListener('click', async function() {
            if (!lssIndividualQuestions) return;

            const templates = Object.entries(lssIndividualQuestions).map(([code, qData]) => ({
                filename: qData.suggested_filename,
                content: qData.prism_json
            }));

            lssSaveQuestionsToProjectBtn.disabled = true;
            lssSaveQuestionsToProjectBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';

            await saveTemplatesToProject(templates);

            lssSaveQuestionsToProjectBtn.disabled = false;
            lssSaveQuestionsToProjectBtn.innerHTML = '<i class="fas fa-folder-plus me-1"></i>Save to Project';
        });
    }

    function downloadJson(data, filename) {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    async function downloadAllAsZip(questionnaires) {
        if (typeof JSZip !== 'undefined') {
            const zip = new JSZip();
            for (const [, qData] of Object.entries(questionnaires)) {
                zip.file(qData.suggested_filename, JSON.stringify(qData.prism_json, null, 2));
            }
            const blob = await zip.generateAsync({type: 'blob'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'limesurvey_questionnaires.zip';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } else {
            for (const [, qData] of Object.entries(questionnaires)) {
                downloadJson(qData.prism_json, qData.suggested_filename);
                await new Promise(r => setTimeout(r, 300));
            }
        }
    }

    async function downloadAllQuestionsAsZip(questions) {
        if (typeof JSZip !== 'undefined') {
            const zip = new JSZip();
            for (const [, qData] of Object.entries(questions)) {
                zip.file(qData.suggested_filename, JSON.stringify(qData.prism_json, null, 2));
            }
            const blob = await zip.generateAsync({type: 'blob'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'limesurvey_question_templates.zip';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } else {
            for (const [, qData] of Object.entries(questions)) {
                downloadJson(qData.prism_json, qData.suggested_filename);
                await new Promise(r => setTimeout(r, 300));
            }
        }
    }
}
