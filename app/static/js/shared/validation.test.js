import { describe, expect, it } from 'vitest';

import {
  isValidEmail,
  isValidPath,
  isValidProjectName,
  isValidUrl
} from './validation.js';

describe('shared validation helpers', () => {
  it('validates project names with safe characters only', () => {
    expect(isValidProjectName('study_01-alpha')).toBe(true);
    expect(isValidProjectName('study name')).toBe(false);
    expect(isValidProjectName('')).toBe(false);
  });

  it('validates email addresses', () => {
    expect(isValidEmail('user@example.org')).toBe(true);
    expect(isValidEmail('invalid-email')).toBe(false);
  });

  it('validates urls via the URL constructor', () => {
    expect(isValidUrl('https://example.org/path')).toBe(true);
    expect(isValidUrl('not a url')).toBe(false);
  });

  it('rejects blank paths', () => {
    expect(isValidPath('/tmp/project')).toBe(true);
    expect(isValidPath('   ')).toBe(false);
  });
});