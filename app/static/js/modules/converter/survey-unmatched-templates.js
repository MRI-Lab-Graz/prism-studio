import { fetchWithApiFallback } from '../../shared/api.js';

export function createSurveyUnmatchedTemplatesController({
    conversionSummaryBody,
    conversionSummaryContainer,
    appendLog,
}) {
    let unmatchedGroupsData = [];

    function displayUnmatchedGroupsError(data) {
        let html = `
            <div class="alert alert-warning mb-3">
                <h6 class="mb-1"><i class="fas fa-exclamation-triangle me-1"></i>Templates Required</h6>
                <p class="mb-0">${data.message}</p>
            </div>
            <table class="table table-sm table-bordered">
                <thead><tr>
                    <th>Group</th><th>Task Key</th><th>Items</th><th>Action</th>
                </tr></thead><tbody>`;

        data.unmatched.forEach((g, i) => {
            html += `<tr id="unmatched-row-${i}">
                <td>${g.group_name}</td>
                <td><code>survey-${g.task_key}</code></td>
                <td>${g.item_count}</td>
                <td><button class="btn btn-sm btn-outline-primary" onclick="saveUnmatchedTemplate(${i})">
                    <i class="fas fa-save me-1"></i>Save Template
                </button></td>
            </tr>`;
        });

        html += `</tbody></table>
            <div class="d-flex gap-2 mt-2">
                <button class="btn btn-primary btn-sm" onclick="saveAllUnmatchedTemplates()">
                    <i class="fas fa-save me-1"></i>Save All Templates
                </button>
                <button class="btn btn-success btn-sm" id="rerunConversionBtn" disabled>
                    <i class="fas fa-redo me-1"></i>Re-run Conversion
                </button>
            </div>`;

        unmatchedGroupsData = Array.isArray(data.unmatched) ? data.unmatched : [];
        window._unmatchedGroupsData = unmatchedGroupsData;

        appendLog('Templates required for unmatched groups \u2014 see below', 'error');
        conversionSummaryBody.innerHTML = html;
        conversionSummaryContainer.classList.remove('d-none');
    }

    async function saveUnmatchedTemplate(index) {
        const g = unmatchedGroupsData[index];
        if (!g) {
            return;
        }

        const btn = document.querySelector(`#unmatched-row-${index} button`);
        if (!btn) {
            return;
        }

        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Saving...';

        try {
            const resp = await fetchWithApiFallback('/api/save-unmatched-template', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({task_key: g.task_key, prism_json: g.prism_json}),
            });
            const result = await resp.json();

            if (result.success) {
                btn.innerHTML = '<i class="fas fa-check me-1"></i>Saved';
                btn.classList.replace('btn-outline-primary', 'btn-outline-success');
                g._saved = true;
                appendLog(`Template saved: ${result.filename}`, 'success');
                checkAllGroupsSaved();
            } else {
                btn.innerHTML = '<i class="fas fa-times me-1"></i>Failed';
                btn.classList.replace('bn-outline-primary', 'btn-outline-danger');
                btn.disabled = false;
                appendLog(`Failed to save template for ${g.group_name}: ${result.error}`, 'error');
            }
        } catch (err) {
            btn.innerHTML = '<i class="fas fa-times me-1"></i>Error';
            btn.classList.replace('btn-outline-primary', 'btn-outline-danger');
            btn.disabled = false;
            appendLog(`Error saving template: ${err.message}`, 'error');
        }
    }

    async function saveAllUnmatchedTemplates() {
        for (let i = 0; i < unmatchedGroupsData.length; i++) {
            if (!unmatchedGroupsData[i]._saved) {
                await saveUnmatchedTemplate(i);
            }
        }
    }

    function checkAllGroupsSaved() {
        const allSaved = unmatchedGroupsData.every((g) => g._saved);
        const rerunBtn = document.getElementById('rerunConversionBtn');
        if (rerunBtn) {
            rerunBtn.disabled = !allSaved;
            if (allSaved) {
                rerunBtn.onclick = () => {
                    const previewBtn = document.getElementById('previewBtn');
                    if (previewBtn) previewBtn.click();
                };
            }
        }
    }

    function initialize() {
        window.saveUnmatchedTemplate = saveUnmatchedTemplate;
        window.saveAllUnmatchedTemplates = saveAllUnmatchedTemplates;
    }

    return {
        initialize,
        displayUnmatchedGroupsError,
    };
}
