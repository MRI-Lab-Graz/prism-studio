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

/**
 * Pure mapping from a survey.json response object to a normalized,
 * form-agnostic shape. No DOM access here.
 */
export function mapSurveyResponseToFormFields(response) {
    const r = response && typeof response === 'object' ? response : {};

    // Support both old Pavlovia format (PI_Name) and new internal format (pi_contact.pi_name)
    const piContact = r.pi_contact && typeof r.pi_contact === 'object' ? r.pi_contact : {};
    const piName = String(r.PI_Name || piContact.pi_name || '').trim();
    const piEmail = String(r.PI_email || piContact.pi_email || '').trim();
    const piOrcid = String(r.PI_orcid || piContact.pi_orcid || '').trim();
    const pi = splitPersonName(piName);
    const authors = [];
    if (pi.first || pi.last) {
        authors.push({
            'given-names': pi.first,
            'family-names': pi.last,
            email: piEmail,
            orcid: piOrcid,
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

    // Support keyword dict {keyword_1: 'x', ...} (new format) or plain array (old format)
    let keywords = [];
    if (Array.isArray(r.keywords)) {
        keywords = r.keywords.map(String).filter(Boolean);
    } else if (r.keywords && typeof r.keywords === 'object') {
        keywords = Object.values(r.keywords).map(String).filter(Boolean);
    }

    // Support both r.Ethics (old) and r.ethics_approved (new)
    let ethics = null;
    if (r.Ethics === true || r.ethics_approved === true) {
        const committee = String(r.ethics_committee || '').trim();
        const votum = String(r.code_ethic || r.ethics_reference || '').trim();
        const date = String(r.date_ethic || r.ethics_approval_date || '').trim();
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

    // Support direct string values (new: 'longitudinal') and old item codes ('item2')
    let studyDesignType = '';
    if (r.study_design === 'item1' || r.study_design === 'cross-sectional') studyDesignType = 'cross-sectional';
    else if (r.study_design === 'item2' || r.study_design === 'longitudinal') studyDesignType = 'longitudinal';

    // Support old timespan.text1/text2 and new study_period.start_date/end_date (ISO YYYY-MM-DD)
    const timespan = r.timespan && typeof r.timespan === 'object' ? r.timespan : {};
    const studyPeriod = r.study_period && typeof r.study_period === 'object' ? r.study_period : {};

    // financial_compensation: boolean in new format
    let financialCompensation = null;
    if (r.financial_compensation === true) financialCompensation = 'Financial compensation';
    else if (r.financial_compensation === false) financialCompensation = 'No financial compensation';

    // Recruitment methods: array of method-key strings
    const recruitmentMethods = Array.isArray(r.recruitment_method)
        ? r.recruitment_method.filter(Boolean)
        : [];

    // Inclusion/exclusion criteria: [{criterion: '...'}, ...] in new format
    const inclusionCriteria = Array.isArray(r.inclusion_criteria)
        ? r.inclusion_criteria.map(item => {
            if (typeof item === 'string') return item.trim();
            if (item && typeof item === 'object') {
                return String(item.criterion || item.text || Object.values(item)[0] || '').trim();
            }
            return '';
        }).filter(Boolean)
        : [];
    const exclusionCriteria = Array.isArray(r.exclusion_criteria)
        ? r.exclusion_criteria.map(item => {
            if (typeof item === 'string') return item.trim();
            if (item && typeof item === 'object') {
                return String(item.criterion || item.text || item.question1 || Object.values(item)[0] || '').trim();
            }
            return '';
        }).filter(Boolean)
        : [];

    return {
        title: String(r.bids_title || '').trim(),
        studyDescription: String(r.study_description || '').trim(),
        keywords,
        authors,
        ethics,
        funding,
        sampleSize: r.nr_participants !== undefined && r.nr_participants !== null && r.nr_participants !== ''
            ? parseInt(r.nr_participants, 10)
            : r.number_of_participants !== undefined && r.number_of_participants !== null
                ? parseInt(r.number_of_participants, 10)
                : null,
        studyDesignType,
        financialCompensation,
        recruitmentMethods,
        inclusionCriteria,
        exclusionCriteria,
        recruitmentStart: timespan.text1 || studyPeriod.start_date || '',
        recruitmentEnd: timespan.text2 || studyPeriod.end_date || '',
    };
}

function applyMappedFields(mapped, deps) {
    const {
        setAuthorsList,
        setEthicsApprovals,
        setFundingChoice,
        addFundingRow,
        setYearMonthValue,
        setRecMethodList,
        setOverviewList,
        updateCreateProjectButton,
    } = deps;

    if (mapped.title) {
        // #metadataName is the actual required BIDS "Basics.Name" field.
        // Its own input listener auto-derives the sanitized #projectName
        // (folder name) from it when that field is still empty, so setting
        // it here and dispatching 'input' keeps both fields consistent with
        // the app's normal typing flow instead of duplicating the sanitizer.
        const nameField = document.getElementById('metadataName');
        if (nameField) {
            nameField.value = mapped.title;
            nameField.dispatchEvent(new Event('input', { bubbles: true }));
        }
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

    if (mapped.financialCompensation) {
        const compField = document.getElementById('smRecCompensation');
        if (compField) compField.value = mapped.financialCompensation;
    }

    if (mapped.recruitmentMethods && mapped.recruitmentMethods.length && setRecMethodList) {
        setRecMethodList(mapped.recruitmentMethods);
    }

    if (mapped.inclusionCriteria && mapped.inclusionCriteria.length && setOverviewList) {
        setOverviewList('smEligInclusion', mapped.inclusionCriteria);
    }

    if (mapped.exclusionCriteria && mapped.exclusionCriteria.length && setOverviewList) {
        setOverviewList('smEligExclusion', mapped.exclusionCriteria);
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
    setRecMethodList,
    setOverviewList,
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
                    setRecMethodList,
                    setOverviewList,
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
