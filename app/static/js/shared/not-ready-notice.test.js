import { describe, expect, it } from 'vitest';

import { isNotReadyResponse, showNotReadyNotice } from './not-ready-notice.js';

describe('isNotReadyResponse', () => {
    it('matches only 409 project_not_ready', () => {
        expect(isNotReadyResponse(409, { code: 'project_not_ready' })).toBe(true);
        expect(isNotReadyResponse(409, { code: 'other' })).toBe(false);
        expect(isNotReadyResponse(500, { code: 'project_not_ready' })).toBe(false);
        expect(isNotReadyResponse(409, null)).toBe(false);
    });
});

// Small DOM fakes: the notice only needs createElement/getElementById/body.appendChild.
const fakeDocument = () => {
    const appended = [];
    const make = (tag) => ({
        tag, id: '', className: '', style: {}, children: [], href: '', textContent: '',
        append(...nodes) { this.children.push(...nodes); },
    });
    return {
        appended,
        createElement: make,
        getElementById: (id) => appended.find((el) => el.id === id) || null,
        body: { appendChild: (el) => appended.push(el) },
    };
};
const response = (status, body) => ({ status, clone: () => ({ json: async () => body }) });
const NOT_READY = { code: 'project_not_ready', error: 'Tools are blocked until these required fields are set: Authors.' };

describe('showNotReadyNotice', () => {
    it('ignores everything that is not a 409 project_not_ready', async () => {
        const doc = fakeDocument();
        expect(await showNotReadyNotice(response(200, NOT_READY), { document: doc, pathname: '/converter' })).toBe(false);
        expect(await showNotReadyNotice(response(409, { code: 'other' }), { document: doc, pathname: '/converter' })).toBe(false);
        expect(doc.appended).toHaveLength(0);
    });

    it('shows the backend text with a link back to the Projects page', async () => {
        const doc = fakeDocument();
        expect(await showNotReadyNotice(response(409, NOT_READY), { document: doc, pathname: '/converter' })).toBe(true);
        const [box] = doc.appended;
        expect(box.children[0]).toContain('required fields');
        expect(box.children[1].href).toBe('/projects');
    });

    it('shows one notice however many requests were blocked', async () => {
        const doc = fakeDocument();
        await showNotReadyNotice(response(409, NOT_READY), { document: doc, pathname: '/recipes' });
        await showNotReadyNotice(response(409, NOT_READY), { document: doc, pathname: '/recipes' });
        expect(doc.appended).toHaveLength(1);
    });

    it('stays out of the way on the Projects page itself', async () => {
        const doc = fakeDocument();
        expect(await showNotReadyNotice(response(409, NOT_READY), { document: doc, pathname: '/projects' })).toBe(false);
        expect(doc.appended).toHaveLength(0);
    });
});
