import { escapeHtml } from '../../shared/dom.js';

export function showPreliminarySaveModal(issues, { doc = document, bootstrapApi = window.bootstrap } = {}) {
    if (!Array.isArray(issues) || issues.length === 0) {
        return Promise.resolve(true);
    }

    if (!bootstrapApi || typeof bootstrapApi.Modal !== 'function') {
        const preview = issues.slice(0, 3).join('\n- ');
        return Promise.resolve(
            confirm(
                'Required fields are still missing. Save as preliminary anyway?\n\n'
                + `- ${preview}`
                + (issues.length > 3 ? `\n- (+${issues.length - 3} more)` : '')
            )
        );
    }

    return new Promise((resolve) => {
        const existingModal = doc.getElementById('_preliminaryMetadataSaveModal');
        if (existingModal) existingModal.remove();

        const listHtml = issues
            .map(item => `<li class="mb-1">${escapeHtml(item)}</li>`)
            .join('');

        const modalEl = doc.createElement('div');
        modalEl.id = '_preliminaryMetadataSaveModal';
        modalEl.className = 'modal fade';
        modalEl.tabIndex = -1;
        modalEl.setAttribute('aria-modal', 'true');
        modalEl.setAttribute('role', 'dialog');
        modalEl.innerHTML = `
            <div class="modal-dialog modal-dialog-centered modal-lg">
                <div class="modal-content border-warning">
                    <div class="modal-header bg-warning bg-opacity-10 border-bottom border-warning">
                        <h5 class="modal-title">
                            <i class="fas fa-save text-warning me-2"></i>
                            Preliminary Save
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <p>The following required fields are still empty or invalid. You can save now as a <strong>preliminary project state</strong> and complete these fields later.</p>
                        <ul class="text-danger mb-0 ps-3">${listHtml}</ul>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal" id="_prelimSaveCancel">
                            <i class="fas fa-arrow-left me-1"></i>Go back
                        </button>
                        <button type="button" class="btn btn-warning" id="_prelimSaveConfirm">
                            <i class="fas fa-save me-1"></i>Save Preliminary State
                        </button>
                    </div>
                </div>
            </div>`;

        doc.body.appendChild(modalEl);

        const bsModal = new bootstrapApi.Modal(modalEl, { backdrop: 'static' });

        doc.getElementById('_prelimSaveConfirm').addEventListener('click', () => {
            bsModal.hide();
            resolve(true);
        });
        doc.getElementById('_prelimSaveCancel').addEventListener('click', () => {
            bsModal.hide();
            resolve(false);
        });
        modalEl.addEventListener('hidden.bs.modal', () => {
            // X button / Escape hide the modal without a click handler; settle
            // the promise (no-op if already resolved) or the submit lock leaks.
            resolve(false);
            modalEl.remove();
        }, { once: true });

        bsModal.show();
    });
}
