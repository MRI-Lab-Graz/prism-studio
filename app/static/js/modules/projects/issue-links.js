/** Which input a "Dataset description issue" belongs to (pure, unit tested), so the
 *  message can link to it. Fields the user cannot edit here (DatasetType, ...) have none. */

const TARGETS = {
    Name: '#metadataName',
    Authors: '#metadataAuthorsList .author-first',
    Keywords: '#metadataKeywords',
    Funding: '#metadataFundingYes',
    EthicsApprovals: '#metadataEthicsYes',
};

/** The field a backend schema message talks about: "'Authors' is a required property",
 *  "Keywords: [] is too short". */
export function issueFieldName(message) {
    const text = String(message || '');
    const match = /^'([A-Za-z]+)' is a required property/.exec(text) || /^([A-Za-z]+):/.exec(text);
    return match ? match[1] : null;
}

export const issueFieldTarget = (message) => TARGETS[issueFieldName(message)] || null;
