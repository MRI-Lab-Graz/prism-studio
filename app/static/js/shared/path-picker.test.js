import { describe, expect, it } from 'vitest';


describe('isProjectJsonPath', () => {
  it.each([
    ['C:\\Users\\me\\study\\project.json', true],
    ['/home/me/study/project.json', true],
    ['C:\\Users\\me\\study\\other.json', false],
    ['/home/me/project.json.bak', false],
    ['', false],
  ])('%s -> %s', async (path, expected) => {
    const { isProjectJsonPath } = await import('./path-picker.js');
    expect(isProjectJsonPath(path)).toBe(expected);
  });
});
