import { describe, expect, it, vi } from 'vitest';

import { finishImport, offerShare, refreshTemplateList, validateCurrent } from './source-workflow.js';

const REQUIRED = [{ path: 'Study', message: "'TaskName' is a required property" }];
const REAL_ERROR = [...REQUIRED, { path: 'Study.Authors', message: "1 is not of type 'string'" }];

async function alertFor(errors, options) {
    const alerts = [];
    const el = { disabled: false, classList: { toggle() {}, add() {} } };
    const context = {
        modalityEl: { value: 'survey' }, schemaEl: { value: 'stable' },
        getCurrentProjectPath: () => '/p', projectContextRequestToken: 1,
        getExportWordButton: () => null, currentTemplate: {}, hasExplicitTemplate: true,
        apiPost: async () => ({ ok: false, errors }),
        isProjectContextCurrent: () => true,
        btnDownload: el, btnSave: el, alertAreaEl: { querySelectorAll: () => [] },
        deriveFocusPath: (p) => p, escapeHtml: (s) => s, renderMissingSummary() {},
        showAlert: (type, html) => alerts.push({ type, html }),
    };
    await validateCurrent(context, options);
    return alerts[0];
}

describe('validateCurrent right after loading a template', () => {
    it('shows missing required fields as a hint, not an error', async () => {
        const alert = await alertFor(REQUIRED, { initial: true });
        expect(alert.type).toBe('warning');
        expect(alert.html).not.toContain('Validation failed');
        expect(alert.html).toContain('TaskName');
    });

    it('still fails loudly on an explicit Validate', async () => {
        expect((await alertFor(REQUIRED)).type).toBe('danger');
    });

    it('stays red when there is a real error too', async () => {
        expect((await alertFor(REAL_ERROR, { initial: true })).type).toBe('danger');
    });
});

const LIMESURVEY_IMPORT_ERRORS = [
    { path: 'Study', message: "'Citation' is a required property" },
    { path: 'Study', message: "'Category' is a required property" },
    { path: 'Technical', message: "'SoftwareVersion' is a required property" },
    { path: 'Technical/SoftwareVersion', message: "SoftwareVersion is required when SoftwarePlatform is 'LimeSurvey'" },
];

describe('validateCurrent right after an import', () => {
    it('says the fields were not found in the file, instead of reporting a failure', async () => {
        const alert = await alertFor(LIMESURVEY_IMPORT_ERRORS, { initial: true, imported: true });
        expect(alert.type).toBe('warning');
        expect(alert.html).toContain('Not found in your file');
        expect(alert.html).not.toContain('Validation failed');
        expect(alert.html).toContain('Citation');
        expect(alert.html).toContain('SoftwareVersion is required when');
    });

    it('treats "is required when ..." as a missing field, not an error, after a load too', async () => {
        const alert = await alertFor(LIMESURVEY_IMPORT_ERRORS, { initial: true });
        expect(alert.type).toBe('warning');
    });

    it('stays red when the import also has a real error', async () => {
        const alert = await alertFor([...LIMESURVEY_IMPORT_ERRORS, ...REAL_ERROR.slice(1)], { initial: true, imported: true });
        expect(alert.type).toBe('danger');
        expect(alert.html).toContain('Validation failed');
    });

    it('still fails loudly when the user clicks Validate', async () => {
        expect((await alertFor(LIMESURVEY_IMPORT_ERRORS)).type).toBe('danger');
    });
});

describe('finishImport', () => {
    it('validates as an import, so missing details are a hint and not a failure', async () => {
        const alerts = [];
        const el = { disabled: false, classList: { toggle() {}, add() {} } };
        const context = {
            modalityEl: { value: 'survey' }, schemaEl: { value: 'stable' },
            getCurrentProjectPath: () => '/p', projectContextRequestToken: 1,
            getExportWordButton: () => null, currentTemplate: {}, hasExplicitTemplate: true,
            apiPost: async () => ({ ok: false, errors: LIMESURVEY_IMPORT_ERRORS }),
            isProjectContextCurrent: () => true,
            btnDownload: el, btnSave: el, alertAreaEl: { querySelectorAll: () => [] },
            deriveFocusPath: (p) => p, escapeHtml: (s) => s, renderMissingSummary() {},
            showAlert: (type, html) => alerts.push({ type, html }),
        };
        await finishImport(context, 'Imported x');
        expect(alerts.at(-1).type).toBe('warning');
        expect(alerts.at(-1).html).toContain('Not found in your file');
    });
});

describe('refreshTemplateList', () => {
    async function selectedAfterRefresh(loadedFromProjectLibrary, currentTemplateFilename) {
        globalThis.document = { createElement: () => ({ dataset: {} }) };
        // like a real <select>: rebuilding the options clears the selection
        const select = () => {
            const s = { value: '', options: [], appendChild(o) { this.options.push(o); } };
            Object.defineProperty(s, 'innerHTML', { set() { this.options = []; this.value = ''; } });
            return s;
        };
        const templates = [{ filename: 'survey-aq10.json', source: 'project', path: '/p/aq10' }];
        const context = {
            modalityEl: { value: 'survey' }, schemaEl: { value: 'stable' },
            getCurrentProjectPath: () => '/p', projectContextRequestToken: 1,
            withProjectPathQuery: (u) => u, apiGet: async () => ({ templates }),
            isProjectContextCurrent: () => true,
            templateStatusPrefix: () => '[FILE OK]', templateStatusTitle: () => '',
            templateMetadata: {}, projectTemplateSelectEl: select(), globalTemplateSelectEl: select(),
            updateProjectLibraryStatus() {}, updateLoadButtonState() {},
            loadedFromProjectLibrary, currentTemplateFilename,
        };
        await refreshTemplateList(context, { silent: true });
        return context.projectTemplateSelectEl.value;
    }

    it('selects the open project template again', async () => {
        expect(await selectedAfterRefresh(true, 'survey-aq10.json')).toBe('survey-aq10.json');
    });

    it('selects nothing when the open template is not a project file', async () => {
        expect(await selectedAfterRefresh(false, 'survey-aq10.json')).toBe('');
    });

    it('selects nothing when the open file is gone from the project', async () => {
        expect(await selectedAfterRefresh(true, 'survey-deleted.json')).toBe('');
    });
});


describe('offerShare', () => {
    const ask = (answer) => { globalThis.confirm = vi.fn(() => answer); return globalThis.confirm; };

    it('asks nothing for a template that was not an unmatched import', async () => {
        const confirm = ask(true);
        await offerShare({ shareCandidate: null, apiPost: vi.fn() }, 'survey-x.json');
        expect(confirm).not.toHaveBeenCalled();
    });

    it('asks nothing when a different template was saved', async () => {
        const confirm = ask(true);
        await offerShare({ shareCandidate: 'survey-x.json', apiPost: vi.fn() }, 'survey-y.json');
        expect(confirm).not.toHaveBeenCalled();
    });

    it('asks once; No sends nothing and is not asked again', async () => {
        const confirm = ask(false);
        const context = { shareCandidate: 'survey-x.json', apiPost: vi.fn() };
        await offerShare(context, 'survey-x.json');
        await offerShare(context, 'survey-x.json');
        expect(confirm).toHaveBeenCalledTimes(1);
        expect(confirm.mock.calls[0][0]).toContain('mri-lab@uni-graz.at');
        expect(context.apiPost).not.toHaveBeenCalled();
        expect(context.shareCandidate).toBeNull();
    });
});
