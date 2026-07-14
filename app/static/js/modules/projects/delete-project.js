// Delete-project confirmation flow. The trigger button
// (#projectBoxDeleteBtn) is re-rendered dynamically inside the
// "Project Loaded" panel, so binding happens via delegation on a stable
// ancestor rather than on the button itself.
export function initDeleteProjectController({ fetchWithApiFallback, escapeHtml }) {
    let pendingPath = '';
    let pendingName = '';

    function getModalElements() {
        return {
            modalEl: document.getElementById('deleteProjectModal'),
            pathEl: document.getElementById('deleteProjectModalPath'),
            nameEl: document.getElementById('deleteProjectModalName'),
            input: document.getElementById('deleteProjectConfirmInput'),
            errorEl: document.getElementById('deleteProjectModalError'),
            confirmBtn: document.getElementById('deleteProjectConfirmBtn'),
        };
    }

    function showModalError(errorEl, message) {
        if (!errorEl) return;
        const text = String(message || '').trim();
        errorEl.textContent = text;
        errorEl.style.display = text ? 'block' : 'none';
    }

    function openDeleteModal(path, name) {
        pendingPath = String(path || '').trim();
        pendingName = String(name || '').trim() || pendingPath.split(/[\\/]/).pop();
        if (!pendingPath) return;

        const { modalEl, pathEl, nameEl, input, errorEl, confirmBtn } = getModalElements();
        if (!modalEl || !window.bootstrap || !window.bootstrap.Modal) return;

        if (pathEl) pathEl.textContent = pendingPath;
        if (nameEl) nameEl.textContent = pendingName;
        if (input) input.value = '';
        if (confirmBtn) confirmBtn.disabled = true;
        showModalError(errorEl, '');

        const modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
        window.setTimeout(() => input && input.focus(), 200);
    }

    document.addEventListener('click', function(event) {
        const trigger = event.target.closest ? event.target.closest('#projectBoxDeleteBtn') : null;
        if (!trigger) return;
        openDeleteModal(trigger.dataset.projectPath, trigger.dataset.projectName);
    });

    document.addEventListener('input', function(event) {
        if (event.target.id !== 'deleteProjectConfirmInput') return;
        const { confirmBtn, errorEl } = getModalElements();
        if (confirmBtn) {
            confirmBtn.disabled = event.target.value.trim() !== pendingName;
        }
        showModalError(errorEl, '');
    });

    document.addEventListener('click', async function(event) {
        const btn = event.target.closest ? event.target.closest('#deleteProjectConfirmBtn') : null;
        if (!btn) return;

        const { modalEl, input, errorEl, confirmBtn } = getModalElements();
        const typedName = input ? input.value.trim() : '';
        if (typedName !== pendingName) {
            showModalError(errorEl, 'Name does not match.');
            return;
        }

        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Deleting...';
        showModalError(errorEl, '');

        try {
            const response = await fetchWithApiFallback('/api/projects/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: pendingPath, confirm_name: typedName }),
            });
            const data = await response.json().catch(() => ({ success: false, error: 'Invalid server response.' }));
            if (!response.ok || !data.success) {
                throw new Error(data.error || `Delete failed (${response.status})`);
            }

            if (window.bootstrap && window.bootstrap.Modal && modalEl) {
                window.bootstrap.Modal.getOrCreateInstance(modalEl).hide();
            }

            // Full reload so recent projects, the current-project banner, and
            // every other panel that depends on session state re-sync from
            // the server rather than trying to hand-patch a dozen bits of UI.
            window.location.href = '/projects?clear_current=1&deleted=1';
        } catch (error) {
            showModalError(errorEl, error.message || 'Could not delete the project.');
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
        }
    });

    return { openDeleteModal };
}
