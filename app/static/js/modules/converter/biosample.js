/**
 * Biosample tab: collects the `prism_tools biosample import` options, posts them, shows the result.
 * The backend decides everything; this only reads the form and lists what came back.
 */
import { mountChipArea } from '../projects/chip-list.js';
import { resolveCurrentProjectPath } from '../../shared/project-state.js';

export function initBiosample() {
    const byId = (id) => document.getElementById(id);
    const select = byId('biosampleSpecimen');
    const button = byId('biosampleImportBtn');
    const result = byId('biosampleResult');
    if (!select || !button || !result) return;

    // Pull-down + green chip, as on the project page: the chosen type leaves the list until its chip is removed.
    const specimen = mountChipArea(byId('biosampleSpecimenChips'), {
        single: true,
        onChange: (values) => {
            for (const option of select.options) option.hidden = Boolean(option.value) && values.includes(option.value);
            select.value = '';
        },
    });
    select.addEventListener('change', () => { if (select.value) specimen.addValue(select.value); });

    const section = (title, items, variant) => {
        if (!items.length) return;
        const box = document.createElement('div');
        box.className = `alert alert-${variant} py-2`;
        const heading = document.createElement('strong');
        heading.textContent = title;
        const list = document.createElement('ul');
        list.className = 'mb-0 small';
        for (const item of items) {
            const li = document.createElement('li');
            li.textContent = item;
            list.appendChild(li);
        }
        box.append(heading, list);
        result.appendChild(box);
    };

    button.addEventListener('click', async () => {
        const file = byId('biosampleFile').files[0];
        const dryRun = byId('biosampleDryRun').checked;
        const form = new FormData();
        if (file) form.append('file', file);
        form.append('project_path', resolveCurrentProjectPath() || '');
        form.append('specimen', specimen.getValues()[0] || '');
        form.append('overwrite', String(byId('biosampleOverwrite').checked));
        form.append('dry_run', String(dryRun));
        result.innerHTML = '';
        button.disabled = true;
        try {
            const response = await fetch('/api/biosample-import', { method: 'POST', body: form });
            const data = await response.json();
            if (data.error) {
                section('Error', [data.error], 'danger');
                return;
            }
            section(dryRun ? 'Would write' : 'Written', data.written, 'success');
            section('Warnings', data.warnings, 'warning');
            section('Errors', data.errors, 'danger');
        } catch (error) {
            section('Error', [String(error)], 'danger');
        } finally {
            button.disabled = false;
        }
    });
}
