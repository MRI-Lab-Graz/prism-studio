/**
 * Import a Pavlovia survey.json response (MRI-Lab Graz Study Application)
 * to prefill the Create Project form.
 */

function splitPersonName(fullName) {
    const cleaned = String(fullName || '').trim();
    if (!cleaned) return { first: '', last: '' };
    if (cleaned.includes(',')) {
        const [last, first] = cleaned.split(',').map(s => s.trim());
        return { first: first || '', last: last || '' };
    }
    const tokens = cleaned.split(/\s+/).filter(Boolean);
    if (tokens.length <= 1) return { first: tokens[0] || '', last: '' };
    return { first: tokens[0], last: tokens.slice(1).join(' ') };
}

function sanitizeProjectName(title) {
    return String(title || '')
        .trim()
        .replace(/[^a-zA-Z0-9_-]+/g, '_')
        .replace(/^_+|_+$/g, '');
}

/**
 * Pure mapping from a survey.json response object to a normalized,
 * form-agnostic shape. No DOM access here.
 */
export function mapSurveyResponseToFormFields(response) {
    const r = response && typeof response === 'object' ? response : {};

    const pi = splitPersonName(r.PI_Name);
    const authors = [];
    if (pi.first || pi.last) {
        authors.push({
            'given-names': pi.first,
            'family-names': pi.last,
            email: r.PI_email || '',
            orcid: r.PI_orcid || '',
            corresponding: true,
        });
    }
    if (Array.isArray(r.additional_authors)) {
        r.additional_authors.forEach(entry => {
            if (!entry || typeof entry !== 'object') return;
            const name = splitPersonName(entry.author_name);
            if (!name.first && !name.last) return;
            authors.push({
                'given-names': name.first,
                'family-names': name.last,
                email: entry.author_email || '',
                orcid: entry.author_orcid || '',
                affiliation: entry.author_affiliation || '',
            });
        });
    }

    const keywords = Array.isArray(r.keywords)
        ? r.keywords.filter(Boolean)
        : [];

    let ethics = null;
    if (r.Ethics === true) {
        const committee = String(r.ethics_committee || '').trim();
        const votum = String(r.code_ethic || '').trim();
        const date = String(r.date_ethic || '').trim();
        const votumWithDate = date ? [votum, `(${date})`].filter(Boolean).join(' ') : votum;
        ethics = { committee, votum: votumWithDate };
    }

    let funding = null;
    if (r.funding === true && r.funding_details && typeof r.funding_details === 'object') {
        funding = {
            agency: r.funding_details.agency || '',
            grantNumber: r.funding_details.grant_number || '',
        };
    }

    let studyDesignType = '';
    if (r.study_design === 'item1') studyDesignType = 'cross-sectional';
    else if (r.study_design === 'item2') studyDesignType = 'longitudinal';

    const timespan = r.timespan && typeof r.timespan === 'object' ? r.timespan : {};

    return {
        projectName: sanitizeProjectName(r.bids_title),
        studyDescription: String(r.study_description || '').trim(),
        keywords,
        authors,
        ethics,
        funding,
        sampleSize: r.nr_participants !== undefined && r.nr_participants !== null && r.nr_participants !== ''
            ? parseInt(r.nr_participants, 10)
            : null,
        studyDesignType,
        recruitmentStart: timespan.text1 || '',
        recruitmentEnd: timespan.text2 || '',
    };
}

function applyMappedFields(mapped, deps) {
    const {
        setAuthorsList,
        setEthicsApprovals,
        setFundingChoice,
        addFundingRow,
        setYearMonthValue,
        updateCreateProjectButton,
    } = deps;

    if (mapped.projectName) {
        const nameField = document.getElementById('projectName');
        if (nameField) nameField.value = mapped.projectName;
    }

    if (mapped.studyDescription) {
        const overviewMain = document.getElementById('smOverviewMain');
        if (overviewMain) overviewMain.value = mapped.studyDescription;
    }

    if (mapped.keywords.length) {
        const keywordsField = document.getElementById('metadataKeywords');
        if (keywordsField) keywordsField.value = mapped.keywords.join(', ');
    }

    if (mapped.authors.length) {
        setAuthorsList(mapped.authors);
    }

    if (mapped.ethics && mapped.ethics.committee) {
        setEthicsApprovals([`${mapped.ethics.committee}, ${mapped.ethics.votum}`]);
    }

    if (mapped.funding && (mapped.funding.agency || mapped.funding.grantNumber)) {
        setFundingChoice('yes');
        const fundingList = document.getElementById('metadataFundingList');
        if (fundingList) fundingList.innerHTML = '';
        addFundingRow(mapped.funding.agency, mapped.funding.grantNumber);
    }

    if (Number.isFinite(mapped.sampleSize) && mapped.sampleSize > 0) {
        const sampleSizeField = document.getElementById('smEligSampleSize');
        if (sampleSizeField) sampleSizeField.value = String(mapped.sampleSize);
    }

    if (mapped.studyDesignType) {
        const sdType = document.getElementById('smSDType');
        if (sdType) sdType.value = mapped.studyDesignType;
    }

    if (mapped.recruitmentStart) {
        setYearMonthValue('smRecPeriodStartYear', 'smRecPeriodStartMonth', mapped.recruitmentStart);
    }
    if (mapped.recruitmentEnd) {
        setYearMonthValue('smRecPeriodEndYear', 'smRecPeriodEndMonth', mapped.recruitmentEnd);
    }

    updateCreateProjectButton();
}

export function initSurveyImportController({
    setAuthorsList,
    setEthicsApprovals,
    setFundingChoice,
    addFundingRow,
    setYearMonthValue,
    updateCreateProjectButton,
    escapeHtml,
}) {
    const input = document.getElementById('surveyImportInput');
    const statusEl = document.getElementById('surveyImportStatus');
    if (!input) return;

    function setStatus(message, isError) {
        if (!statusEl) return;
        statusEl.className = `small w-100 ${isError ? 'text-danger' : 'text-success'}`;
        statusEl.innerHTML = message ? escapeHtml(message) : '';
    }

    input.addEventListener('change', () => {
        const file = input.files && input.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = () => {
            let response;
            try {
                response = JSON.parse(String(reader.result || ''));
            } catch (error) {
                setStatus(`Could not parse "${file.name}" as JSON: ${error.message}`, true);
                input.value = '';
                return;
            }

            try {
                const mapped = mapSurveyResponseToFormFields(response);
                applyMappedFields(mapped, {
                    setAuthorsList,
                    setEthicsApprovals,
                    setFundingChoice,
                    addFundingRow,
                    setYearMonthValue,
                    updateCreateProjectButton,
                });
                setStatus(`Imported survey response from "${file.name}". Review the prefilled fields below.`, false);
            } catch (error) {
                setStatus(`Failed to apply survey data: ${error.message}`, true);
            } finally {
                input.value = '';
            }
        };
        reader.onerror = () => {
            setStatus(`Could not read "${file.name}".`, true);
            input.value = '';
        };
        reader.readAsText(file);
    });
}
