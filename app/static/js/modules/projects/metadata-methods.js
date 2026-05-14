export function createMetadataMethodsController({
    escapeHtml,
    fetchWithApiFallback,
    getCurrentProjectPath,
    setButtonLoading,
}) {
    let methodsRequestToken = 0;
    let lastMethodsProjectPath = '';
    let methodsMd = '';
    let methodsHtml = '';
    let methodsFilenameBase = 'methods_section_en';

    function resetMethodsPreviewState() {
        methodsMd = '';
        methodsHtml = '';
        methodsFilenameBase = 'methods_section_en';

        const resultDiv = document.getElementById('methodsResult');
        const errorDiv = document.getElementById('methodsError');
        const preview = document.getElementById('methodsPreview');
        const badgesDiv = document.getElementById('methodsSectionsBadges');

        if (resultDiv) resultDiv.style.display = 'none';
        if (errorDiv) errorDiv.style.display = 'none';
        if (preview) preview.innerHTML = '';
        if (badgesDiv) badgesDiv.innerHTML = '';
    }

    function showMethodsCard() {
        const card = document.getElementById('methodsSectionCard');
        if (!card) return;

        const currentProjectPath = getCurrentProjectPath();
        if (currentProjectPath !== lastMethodsProjectPath) {
            lastMethodsProjectPath = currentProjectPath;
            resetMethodsPreviewState();
        }
        card.style.display = currentProjectPath ? 'block' : 'none';
    }

    async function generateMethodsSection() {
        const btn = document.getElementById('generateMethodsBtn');
        const originalText = setButtonLoading(btn, true, 'Generating...');

        const resultDiv = document.getElementById('methodsResult');
        const errorDiv = document.getElementById('methodsError');
        resultDiv.style.display = 'none';
        errorDiv.style.display = 'none';

        const lang = document.getElementById('methodsLanguage').value;
        const detailLevel = document.getElementById('methodsDetailLevel').value;
        const continuous = true;
        const requestProjectPath = getCurrentProjectPath();
        const requestToken = ++methodsRequestToken;

        if (!requestProjectPath) {
            errorDiv.style.display = 'block';
            errorDiv.innerHTML = `
            <div class="alert alert-warning py-2">
                <i class="fas fa-info-circle me-2"></i>No project selected.
            </div>`;
            setButtonLoading(btn, false, null, originalText);
            return;
        }

        try {
            const response = await fetchWithApiFallback('/api/projects/generate-methods', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: requestProjectPath, language: lang, detail_level: detailLevel, continuous: continuous })
            });
            const data = await response.json();
            if (requestToken !== methodsRequestToken || requestProjectPath !== getCurrentProjectPath()) {
                return;
            }

            if (!data.success) {
                errorDiv.style.display = 'block';
                errorDiv.innerHTML = `
                <div class="alert alert-warning py-2">
                    <i class="fas fa-info-circle me-2"></i>${escapeHtml(data.error || 'Could not generate methods section.')}
                </div>`;
                return;
            }

            methodsMd = data.md;
            methodsHtml = data.html;
            methodsFilenameBase = data.filename_base;

            const badgesDiv = document.getElementById('methodsSectionsBadges');
            badgesDiv.innerHTML = (data.sections_used || []).map(
                s => `<span class="badge bg-success bg-opacity-75 me-1">${s}</span>`
            ).join('');

            const parser = new DOMParser();
            const doc = parser.parseFromString(data.html, 'text/html');
            document.getElementById('methodsPreview').innerHTML = doc.body.innerHTML;
            resultDiv.style.display = 'block';
        } catch (error) {
            if (requestToken !== methodsRequestToken || requestProjectPath !== getCurrentProjectPath()) {
                return;
            }
            errorDiv.style.display = 'block';
            errorDiv.innerHTML = `
            <div class="alert alert-danger py-2">
                <i class="fas fa-exclamation-circle me-2"></i>${escapeHtml(error.message || 'Could not generate methods section.')}
            </div>`;
        } finally {
            setButtonLoading(btn, false, null, originalText);
        }
    }

    function downloadMethods(format) {
        const content = format === 'md' ? methodsMd : methodsHtml;
        const mimeType = format === 'md' ? 'text/markdown' : 'text/html';
        const ext = format === 'md' ? '.md' : '.html';
        const blob = new Blob([content], { type: mimeType + ';charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = methodsFilenameBase + ext;
        document.body.appendChild(anchor);
        anchor.click();
        URL.revokeObjectURL(url);
        document.body.removeChild(anchor);
    }

    function handleProjectChanged() {
        methodsRequestToken += 1;
    }

    function initMethodsControls() {
        const generateMethodsBtn = document.getElementById('generateMethodsBtn');
        if (generateMethodsBtn) {
            generateMethodsBtn.addEventListener('click', () => {
                generateMethodsSection();
            });
        }

        const downloadMethodsMdBtn = document.getElementById('downloadMethodsMdBtn');
        if (downloadMethodsMdBtn) {
            downloadMethodsMdBtn.addEventListener('click', () => {
                downloadMethods('md');
            });
        }

        const downloadMethodsHtmlBtn = document.getElementById('downloadMethodsHtmlBtn');
        if (downloadMethodsHtmlBtn) {
            downloadMethodsHtmlBtn.addEventListener('click', () => {
                downloadMethods('html');
            });
        }
    }

    return {
        showMethodsCard,
        generateMethodsSection,
        downloadMethods,
        handleProjectChanged,
        initMethodsControls,
    };
}