/**
 * Projects Module - "Check this computer" for DataLad server setup.
 *
 * Thin adapter over `prism_tools.py datalad doctor`: the checks (Git, git-annex,
 * DataLad, SSH key, server login) run in the backend; this only renders them.
 */

import { getById, setHtml, escapeHtml } from '../../shared/dom.js';
import { fetchWithApiFallback } from '../../shared/api.js';
import { setButtonLoading } from './helpers.js';

export function renderDoctorChecks(checks) {
    if (!checks || !checks.length) return '';
    const rows = checks.map((c) => {
        const icon = c.ok
            ? '<i class="fas fa-check-circle text-success me-2"></i>'
            : '<i class="fas fa-times-circle text-danger me-2"></i>';
        const fix = !c.ok && c.fix
            ? `<div class="small text-danger ms-4" style="white-space: pre-wrap;">${escapeHtml(c.fix)}</div>`
            : '';
        return `<li class="list-group-item">${icon}<strong>${escapeHtml(c.name)}</strong>`
            + ` <span class="text-muted small">${escapeHtml(c.detail)}</span>${fix}</li>`;
    });
    return `<ul class="list-group mb-3">${rows.join('')}</ul>`;
}

async function onCheckClick() {
    const btn = getById('dataladServerCheckBtn');
    const originalText = btn ? btn.innerHTML : '';
    const url = (getById('dataladServerUrl')?.value || '').trim();
    setButtonLoading(btn, true, 'Checking...', originalText);
    try {
        const query = url ? `?url=${encodeURIComponent(url)}` : '';
        const resp = await fetchWithApiFallback(`/api/projects/datalad/doctor${query}`);
        if (!resp.ok) throw new Error('Could not run the setup check');
        const body = await resp.json();
        setHtml('dataladServerCheckResult', renderDoctorChecks(body.checks));
    } catch (error) {
        setHtml('dataladServerCheckResult', `<div class="alert alert-danger">${escapeHtml(error.message)}</div>`);
    } finally {
        setButtonLoading(btn, false, null, originalText);
    }
}

export function initDataladSetupCheck() {
    const btn = getById('dataladServerCheckBtn');
    if (btn) btn.addEventListener('click', onCheckClick);
}
