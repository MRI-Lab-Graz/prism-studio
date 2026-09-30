import { describe, expect, it } from 'vitest';

import { refreshTemplateList, validateCurrent } from './source-workflow.js';

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
