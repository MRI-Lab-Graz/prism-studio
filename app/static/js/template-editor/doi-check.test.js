import { describe, expect, it, vi } from 'vitest';
import { attachDoiCheck, checkDoi, doiMessage } from './doi-check.js';

describe('doiMessage (the wording of the project page)', () => {
  it('shows the short citation for a found DOI', () => {
    expect(doiMessage({ status: 'ok', doi: '10.1/x', citation: 'A, 2020, T' })).toEqual({ cls: 'text-success', text: 'A, 2020, T' });
    expect(doiMessage({ status: 'ok', doi: '10.1/x' }).text).toBe('10.1/x');
  });
  it('says wrong for invalid and not found', () => {
    expect(doiMessage({ status: 'invalid' })).toEqual({ cls: 'text-danger', text: 'Not a valid DOI.' });
    expect(doiMessage({ status: 'not_found' }).cls).toBe('text-danger');
    expect(doiMessage({ status: 'not_found' }).text).toMatch(/not found/i);
  });
  it('says only "could not be checked" when unreachable', () => {
    expect(doiMessage({ status: 'unreachable' })).toEqual({ cls: 'text-muted', text: 'Could not check DOI online (offline?).' });
  });
});

describe('checkDoi', () => {
  it('asks the lookup route once with the encoded DOI', async () => {
    const fetchFn = vi.fn().mockResolvedValue({ json: async () => ({ status: 'ok', doi: '10.1/a b', citation: 'C' }) });
    expect(await checkDoi('10.1/a b', fetchFn)).toEqual({ cls: 'text-success', text: 'C' });
    expect(fetchFn).toHaveBeenCalledWith('/api/projects/lookup-doi?doi=10.1%2Fa%20b');
  });
  it('does not check an empty DOI', async () => {
    const fetchFn = vi.fn();
    expect(await checkDoi('  ', fetchFn)).toBeNull();
    expect(fetchFn).not.toHaveBeenCalled();
  });
  it('a failing request is "could not check", never "wrong"', async () => {
    expect((await checkDoi('10.1/x', vi.fn().mockRejectedValue(new Error('off')))).cls).toBe('text-muted');
  });
});

describe('doiMessage for a registered DOI without metadata', () => {
  it('says it is registered, not wrong', () => {
    expect(doiMessage({ status: 'ok', doi: '10.1/x', empty: true })).toEqual({ cls: 'text-muted', text: 'DOI is registered (no metadata returned).' });
  });
});

describe('attachDoiCheck', () => {
  it('shows only the result of the latest change, whatever order the answers come in', async () => {
    const listeners = {};
    const input = { value: '', addEventListener: (ev, fn) => { listeners[ev] = fn; }, after: vi.fn() };
    globalThis.document = { createElement: () => ({}) };
    const answers = [];
    const fetchFn = vi.fn(() => new Promise((resolve) => answers.push(resolve)));
    const line = attachDoiCheck(input, fetchFn);
    input.value = '10.1/a';
    const first = listeners.change();
    input.value = '10.1/b';
    const second = listeners.change();
    answers[1]({ json: async () => ({ status: 'ok', doi: '10.1/b', citation: 'B' }) });
    await second;
    answers[0]({ json: async () => ({ status: 'not_found' }) });
    await first;
    expect(line.textContent).toBe('B');
    expect(input.after).toHaveBeenCalledWith(line); // the input itself stays the field element, the line follows it
    delete globalThis.document;
  });
});
