import { describe, expect, it } from 'vitest';

import { issueFieldName, issueFieldTarget } from './issue-links.js';

describe('issueFieldName', () => {
    it('reads the field out of the backend schema messages', () => {
        expect(issueFieldName("'Authors' is a required property")).toBe('Authors');
        expect(issueFieldName('Keywords: [] is too short')).toBe('Keywords');
        expect(issueFieldName('Authors: [] should be non-empty')).toBe('Authors');
    });
    it('returns null for text it does not recognise', () => {
        expect(issueFieldName('Could not load dataset_description schema')).toBeNull();
    });
});

describe('issueFieldTarget', () => {
    it('points the fields the user can fill in at their inputs', () => {
        expect(issueFieldTarget("'Name' is a required property")).toBe('#metadataName');
        expect(issueFieldTarget("'Authors' is a required property")).toContain('author-first');
        expect(issueFieldTarget('Keywords: [] is too short')).toBe('#metadataKeywords');
        expect(issueFieldTarget('Funding: [] should be non-empty')).toBe('#metadataFundingYes');
        expect(issueFieldTarget("'EthicsApprovals' is a required property")).toBe('#metadataEthicsYes');
    });
    it('has no target for a field the user cannot edit', () => {
        expect(issueFieldTarget("'DatasetType' is a required property")).toBeNull();
    });
});
