import { askGitIdentity } from './git-identity-dialog.js';
import { showTopFeedback } from './helpers.js';
import { guardSave } from './row-state.js';

export function initCreateProjectController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    textToArray,
    getEligibilityCriteria,
    getProjectStateSnapshot,
    setCreateResultHtml,
    joinProjectTargetPath,
    resetCreateTargetStatusChecks,
    checkCreateTargetStatus,
    validateAllMandatoryFields,
    validateDatasetDescriptionDraftLive,
    getCitationAuthorsList,
    getEthicsApprovals,
    getFundingList,
    getRecMethodList,
    getRecLocationList,
    getYearMonthValue,
    saveProjectSchemaConfig,
    persistMetadataDeclarations,
    applyCurrentProject,
    getCurrentProjectState,
    addRecentProject,
    showStudyMetadataCard,
    updateCreateProjectButton,
    showMethodsCard,
}) {
    const createProjectFormEl = document.getElementById('createProjectForm');
    if (!createProjectFormEl) {
        return;
    }

    async function submitCreateProject(options = {}) {
        // Rows the user has typed into but not accepted yet would be lost: block the save.
        const metadataForm = document.getElementById('studyMetadataForm');
        if (metadataForm && !guardSave(metadataForm, showTopFeedback)) {
            return;
        }
        const triggerButton = options.triggerButton instanceof HTMLElement ? options.triggerButton : null;

        const projectName = document.getElementById('projectName').value.trim();
        const projectPath = document.getElementById('projectPath').value.trim();

        if (!projectPath) {
            alert('Please select a Project Location (output folder) before saving or creating the project.');
            const pathField = document.getElementById('projectPath');
            pathField?.focus();
            return;
        }

        if (!/^[a-zA-Z0-9_-]+$/.test(projectName)) {
            alert('Invalid project name. Only letters, numbers, underscores and hyphens allowed.');
            return;
        }

        resetCreateTargetStatusChecks();
        const targetStatus = await checkCreateTargetStatus();
        if (targetStatus.conflict) {
            return;
        }

        const validation = validateAllMandatoryFields({ forCreation: true });
        const requiredIssueCount = (validation.emptyFields?.length || 0) + (validation.requiredInvalidFields?.length || 0);
        const optionalIssueCount = validation.optionalInvalidFields?.length || 0;
        if (requiredIssueCount > 0) {
            showTopFeedback(`Fill in the ${requiredIssueCount} missing required field(s) in Study Metadata first.`, 'warning');
            return;
        }

        if (optionalIssueCount > 0) {
            alert(validation.optionalInvalidFields.join('\n'));
            return;
        }

        await validateDatasetDescriptionDraftLive();

        const createButtons = [
            document.getElementById('createProjectSubmitBtn'),
            document.getElementById('createProjectSubmitBtnTop')
        ].filter(Boolean);

        const fallbackCreateButton = createButtons[0] || null;
        const activeBtn = triggerButton || fallbackCreateButton;
        const originalText = activeBtn ? setButtonLoading(activeBtn, true, 'Creating...') : null;

        createButtons.forEach(btn => { btn.disabled = true; });

        const fullPath = joinProjectTargetPath(projectPath, projectName);

        const data = {
            path: fullPath,
            name: projectName,
            use_datalad: document.getElementById('projectUseDatalad')?.checked !== false,
            authors: getCitationAuthorsList(),
            license: document.getElementById('metadataLicense')?.value || 'CC0',
            doi: document.getElementById('metadataDOI').value.trim(),
            keywords: document.getElementById('metadataKeywords').value.split(',').map(s => s.trim()).filter(s => s),
            acknowledgements: document.getElementById('metadataAcknowledgements').value.trim(),
            ethics_approvals: getEthicsApprovals(),
            how_to_acknowledge: document.getElementById('metadataHowToAcknowledge').value.trim(),
            funding: getFundingList(),
            references_and_links: document.getElementById('metadataReferences').value.split('\n').map(s => s.trim()).filter(s => s),
            hed_version: document.getElementById('metadataHED').value.trim(),
            dataset_type: 'raw',
            Overview: {
                Main: document.getElementById('smOverviewMain').value || undefined,
                IndependentVariables: document.getElementById('smOverviewIV').value || undefined,
                DependentVariables: document.getElementById('smOverviewDV').value || undefined,
                ControlVariables: document.getElementById('smOverviewCV').value || undefined,
                QualityAssessment: document.getElementById('smOverviewQA').value || undefined,
            },
            StudyDesign: {
                Type: document.getElementById('smSDType').value || undefined,
                Timepoints: document.getElementById('smSDTimepoints').value || undefined,
                SessionLabels: document.getElementById('smSDSessionLabels').value || undefined,
                TypeDescription: document.getElementById('smSDTypeDesc').value || undefined,
                Blinding: document.getElementById('smSDBlinding').value || undefined,
                Randomization: document.getElementById('smSDRandomization').value || undefined,
                ControlCondition: document.getElementById('smSDControl').value || undefined,
            },
            Conditions: {
                Type: document.getElementById('smSDConditionType').value || undefined,
            },
            Recruitment: {
                Method: (function() {
                    const list = getRecMethodList();
                    return list.length ? list.join('; ') : undefined;
                })(),
                Location: (function() {
                    const list = getRecLocationList();
                    return list.length ? list.join('; ') : undefined;
                })(),
                Period: {
                    Start: getYearMonthValue('smRecPeriodStartYear', 'smRecPeriodStartMonth') || undefined,
                    End: getYearMonthValue('smRecPeriodEndYear', 'smRecPeriodEndMonth') || undefined,
                },
                Compensation: document.getElementById('smRecCompensation').value || undefined,
            },
            Eligibility: {
                InclusionCriteria: textToArray(document.getElementById('smEligInclusion').value) || undefined,
                ExclusionCriteria: textToArray(document.getElementById('smEligExclusion').value) || undefined,
                Criteria: getEligibilityCriteria().length ? getEligibilityCriteria() : undefined,
                TargetSampleSize: parseInt(document.getElementById('smEligSampleSize').value) || undefined,
                PowerAnalysis: document.getElementById('smEligPower').value || undefined,
            },
            Procedure: {
                Overview: document.getElementById('smProcOverview').value || undefined,
                InformedConsent: document.getElementById('smProcConsent').value || undefined,
                QualityControl: textToArray(document.getElementById('smProcQC').value) || undefined,
                Debriefing: document.getElementById('smProcDebriefing').value || undefined,
                AdditionalData: document.getElementById('smProcAdditionalData').value || undefined,
                Notes: document.getElementById('smProcNotes').value || undefined,
            },
            Preregistration: {
                DataStatus: document.getElementById('smPreregDataStatus').value || undefined,
                Hypotheses: textToArray(document.getElementById('smPreregHypotheses').value) || undefined,
                PrimaryOutcomes: document.getElementById('smPreregPrimaryOutcomes').value || undefined,
                SecondaryOutcomes: document.getElementById('smPreregSecondaryOutcomes').value || undefined,
                AnalysisPlan: document.getElementById('smPreregAnalysisPlan').value || undefined,
                InferenceCriteria: document.getElementById('smPreregInferenceCriteria').value || undefined,
                ExploratoryAnalyses: document.getElementById('smPreregExploratoryAnalyses').value || undefined,
            },
            MissingData: {
                Description: document.getElementById('smMissingDesc').value || undefined,
                MissingFiles: document.getElementById('smMissingFiles').value || undefined,
                KnownIssues: document.getElementById('smKnownIssues').value || undefined,
            },
            References: document.getElementById('smReferencesText').value || undefined
        };

        try {
            const response = await fetchWithApiFallback('/api/projects/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();

            if (result.success) {
                // DataLad was asked for but this project has no name and email yet: ask once, then switch it on.
                if (result.datalad?.needs_git_identity
                    && await askGitIdentity({ fetchWithApiFallback, projectPath: result.path })) {
                    const enabled = await (await fetchWithApiFallback('/api/projects/datalad/enable', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ confirmed: true })
                    })).json();
                    result.datalad = { ...result.datalad, ...(enabled.datalad || {}), message: enabled.message || enabled.error };
                }
                const dataladNotice = result.datalad?.message
                    ? `
                        <div class="alert alert-${result.datalad.saved ? 'info' : (result.datalad.requested ? 'warning' : 'secondary')} mt-3 mb-0">
                            <i class="fas fa-code-branch me-2"></i>${escapeHtml(result.datalad.message)}
                        </div>
                    `
                    : '';
                setCreateResultHtml(`
                    <div class="alert alert-success">
                        <h5><i class="fas fa-check-circle me-2"></i>Project Created Successfully!</h5>
                        <p class="mb-2">${escapeHtml(result.message)}</p>
                        <p class="mb-2"><strong>Location:</strong> <code>${escapeHtml(result.path)}</code></p>
                        <hr>
                        <p class="mb-1"><strong>Created files:</strong></p>
                        <ul class="mb-2">
                            ${(result.created_files || []).map(f => `<li><code>${escapeHtml(f)}</code></li>`).join('')}
                        </ul>
                        <div class="mt-3 pt-3 border-top">
                            <h6 class="text-muted mb-2">Next Steps:</h6>
                            <div class="btn-group" role="group">
                                <a href="/converter" class="btn btn-sm btn-outline-success">
                                    <i class="fas fa-magic me-1"></i>Open Converter Tool
                                </a>
                            </div>
                            <small class="text-muted d-block mt-2">
                                Add subject folders and metadata before validating to avoid missing data errors.
                            </small>
                        </div>
                        ${dataladNotice}
                        <div class="d-flex justify-content-end mt-3 pt-2 border-top">
                            <button type="button" class="btn btn-sm btn-outline-danger" id="projectBoxDeleteBtn"
                                    data-project-path="${escapeHtml(result.path)}" data-project-name="${escapeHtml(projectName)}">
                                <i class="fas fa-trash me-1"></i>Delete This Project
                            </button>
                        </div>
                    </div>
                `);

                applyCurrentProject(result.current_project);
                // Must happen before showStudyMetadataCard() below reloads the
                // form from the new project: an explicit Ethics/Funding "No"
                // is stored as an empty array, so without this declaration
                // the reload can't tell it from "never answered" and resets
                // both toggles to blank.
                try {
                    await persistMetadataDeclarations();
                } catch (declError) {
                    console.warn('Could not persist metadata declarations after create:', declError);
                }
                try {
                    await saveProjectSchemaConfig();
                } catch (schemaError) {
                    console.error('Error saving project schema version after create:', schemaError);
                }
                const currentState = getCurrentProjectState();
                addRecentProject(currentState.name, currentState.path, currentState.icon);
                showStudyMetadataCard();
                updateCreateProjectButton();
                showMethodsCard();
            } else {
                setCreateResultHtml(`
                    <div class="alert alert-danger">
                        <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                        <p class="mb-0">${escapeHtml(result.error)}</p>
                    </div>
                `);
            }
        } catch (error) {
            setCreateResultHtml(`
                <div class="alert alert-danger">
                    <h5><i class="fas fa-exclamation-circle me-2"></i>Error</h5>
                    <p class="mb-0">${escapeHtml(error.message)}</p>
                </div>
            `);
        } finally {
            if (activeBtn) {
                setButtonLoading(activeBtn, false, null, originalText);
            }
            createButtons.forEach(btn => { btn.disabled = false; });
        }
    }

    // A project already exists -> the create buttons act as save, whichever
    // tab is open. The Create tab stays active after a successful create, so
    // keying off the tab alone re-ran the create and only produced a "target
    // folder already exists" conflict. Matches the button label, which
    // updateCreateProjectButton() flips to "Save Changes to Project" under
    // the same condition.
    function submitStudyMetadataFormInstead() {
        const studyMetadataForm = document.getElementById('studyMetadataForm');
        if (!studyMetadataForm) return;
        if (typeof studyMetadataForm.requestSubmit === 'function') {
            studyMetadataForm.requestSubmit();
        } else {
            studyMetadataForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        }
    }

    const createProjectSubmitBtn = document.getElementById('createProjectSubmitBtn');
    if (createProjectSubmitBtn) {
        createProjectSubmitBtn.addEventListener('click', (event) => {
            event.preventDefault();
            if (getProjectStateSnapshot().path) {
                submitStudyMetadataFormInstead();
                return;
            }
            submitCreateProject();
        });
    }

    const createProjectSubmitBtnTop = document.getElementById('createProjectSubmitBtnTop');
    if (createProjectSubmitBtnTop) {
        createProjectSubmitBtnTop.addEventListener('click', (event) => {
            event.preventDefault();
            if (getProjectStateSnapshot().path) {
                submitStudyMetadataFormInstead();
                return;
            }
            submitCreateProject({ triggerButton: createProjectSubmitBtnTop });
        });
    }

    createProjectFormEl.addEventListener('submit', (event) => {
        event.preventDefault();
        submitCreateProject();
    });
}
