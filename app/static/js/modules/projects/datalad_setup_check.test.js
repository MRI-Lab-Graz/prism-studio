import { describe, expect, it } from 'vitest';
import { renderDoctorChecks } from './datalad_setup_check.js';

describe('renderDoctorChecks', () => {
    it('renders nothing for no checks', () => {
        expect(renderDoctorChecks([])).toBe('');
    });
    it('shows a passing check without a fix', () => {
        const html = renderDoctorChecks([{ name: 'git', ok: true, detail: 'git version 2', fix: '' }]);
        expect(html).toContain('git version 2');
        expect(html).toContain('text-success');
        expect(html).not.toContain('text-danger');
    });
    it('shows what to do for a failing check', () => {
        const html = renderDoctorChecks([{ name: 'datalad', ok: false, detail: 'Not found on PATH.', fix: 'Install with: uv tool install datalad' }]);
        expect(html).toContain('text-danger');
        expect(html).toContain('Install with: uv tool install datalad');
    });
    it('escapes server output so it cannot inject markup', () => {
        const html = renderDoctorChecks([{ name: 'server', ok: false, detail: '<img src=x onerror=alert(1)>', fix: '' }]);
        expect(html).not.toContain('<img');
        expect(html).toContain('&lt;img');
    });
});
