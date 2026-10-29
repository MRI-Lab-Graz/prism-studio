import { describe, expect, it } from 'vitest';

import { findDuplicateKey } from './json-duplicates.js';

describe('findDuplicateKey', () => {
  it('returns null for clean JSON', () => {
    expect(findDuplicateKey('{"a": 1, "b": {"a": 2}, "c": [{"a": 1}, {"a": 2}]}')).toBeNull();
  });

  it('finds a duplicate at the top level', () => {
    expect(findDuplicateKey('{"Timepoint": 1, "x": 2, "Timepoint": 3}')).toBe('Timepoint');
  });

  it('finds a duplicate in a nested object', () => {
    expect(findDuplicateKey('{"o": {"k": 1, "k": 2}}')).toBe('k');
  });

  it('ignores keys repeated in different objects and keys inside string values', () => {
    expect(findDuplicateKey('{"a": "\\"a\\": 1, \\"a\\": 2", "b": {"a": 1}}')).toBeNull();
  });

  it('reads escaped keys as the same key', () => {
    expect(findDuplicateKey('{"a": 1, "\\u0061": 2}')).toBe('a');
  });

  it('does not throw on invalid JSON', () => {
    expect(findDuplicateKey('{"a": ')).toBeNull();
  });
});
