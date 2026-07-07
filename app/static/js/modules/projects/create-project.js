export function initCreateProjectController({
    fetchWithApiFallback,
    setButtonLoading,
    escapeHtml,
    textToArray,
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
    applyCurrentProject,
    getCurrentProjectState,
    addRecentProject,
    showStudyMetadataCard,
    updateCreateProjectButton,
    showMethodsCard,
}) {
    function showIncompleteMetadataModal(missingItems) {
        return new Promise((resolve) => {
            const existingModal = document.getElementById('_incompleteMetadataModal');
            if (existingModal) existingModal.remove();

            const listHtml = missingItems
                .map(item => `<li class="mb-1">${escapeHtml(item)}</li>`)
                .join('');

            const modalEl = document.createElement('div');
            modalEl.id = '_incompleteMetadataModal';
            modalEl.className = 'modal fade';
            modalEl.tabIndex = -1;
            modalEl.setAttribute('aria-modal', 'true');
            modalEl.setAttribute('role', 'dialog');
            modalEl.innerHTML = `
                <div class="modal-dialog modal-dialog-centered modal-lg">
                    <div class="modal-content border-warning">
                        <div class="modal-header bg-warning bg-opacity-10 border-bottom border-warning">
                            <h5 class="modal-title">
                                <i class="fas fa-exclamation-triangle text-warning me-2"></i>
                                Required Fields Missing
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p>The following required fields are still empty or invalid. The project will be created, but the metadata will be <strong>incomplete</strong>. You can fill in missing fields later.</p>
                            <ul class="text-danger mb-0 ps-3">${listHtml}</ul>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal" id="_incompleteModalCancel">
                                <i class="fas fa-arrow-left me-1"></i>Go back and fill fields
                            </button>
                            <button type="button" class="btn btn-warning" id="_incompleteModalConfirm">
                                <i class="fas fa-folder-plus me-1"></i>Create anyway (incomplete)
                            </button>
                        </div>
                    </div>
                </div>`;

            document.body.appendChild(modalEl);

            const bsModal = new bootstrap.Modal(modalEl, { backdrop: 'static' });

            document.getElementById('_incompleteModalConfirm').addEventListener('click', () => {
                bsModal.hide();
                resolve(true);
            });
            document.getElementById('_incompleteModalCancel').addEventListener('click', () => {
                bsModal.hide();
                resolve(false);
            });
            modalEl.addEventListener('hidden.bs.modal', () => {
                modalEl.remove();
            }, { once: true });

            bsModal.show();
        });
    }

    const createProjectFormEl = document.getElementById('createProjectForm');
    if (!createProjectFormEl) {
        return;
    }

    async function submitCreateProject(options = {}) {
        const forcePreliminary = Boolean(options.forcePreliminary);
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

        const validation = validateAllMandatoryFields();
        const requiredIssueCount = (validation.emptyFields?.length || 0) + (validation.requiredInvalidFields?.length || 0);
        const optionalIssueCount = validation.optionalInvalidFields?.length || 0;
        if (requiredIssueCount > 0 && !forcePreliminary) {
            const issues = [
                ...validation.emptyFields.map(f => `• ${f}`),
                ...(validation.requiredInvalidFields || []).map(f => `• ${f}`)
            ];
            const confirmed = await showIncompleteMetadataModal(issues);
            if (!confirmed) return;
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
        const preliminaryButtons = [
            document.getElementById('preliminaryCreateBtn'),
            document.getElementById('preliminaryCreateBtnTop')
        ].filter(Boolean);

        const fallbackCreateButton = createButtons[0] || null;
        const fallbackPreliminaryButton = preliminaryButtons[0] || null;
        const activeBtn = triggerButton || (forcePreliminary ? fallbackPreliminaryButton : fallbackCreateButton);
        const originalText = activeBtn ? setButtonLoading(activeBtn, true, forcePreliminary ? 'Saving...' : 'Creating...') : null;

        createButtons.forEach(btn => { btn.disabled = true; });
        preliminaryButtons.forEach(btn => { btn.disabled = true; });

        const fullPath = joinProjectTargetPath(projectPath, projectName);

        const data = {
            path: fullPath,
            name: projectName,
            use_datalad: document.getElementById('projectUseDatalad')?.checked !== false,
            authors: getCitationAuthorsList(),
            license: document.getElementById('metadataLicense').value,
            doi: document.getElementById('metadataDOI').value.trim(),
            keywords: document.getElementById('metadataKeywords').value.split(',').map(s => s.trim()).filter(s => s),
            acknowledgements: document.getElementById('metadataAcknowledgements').value.trim(),
            ethics_approvals: getEthicsApprovals(),
            how_to_acknowledge: document.getElementById('metadataHowToAcknowledge').value.trim(),
            funding: getFundingList(),
            references_and_links: document.getElementById('metadataReferences').value.split(',').map(s => s.trim()).filter(s => s),
            hed_version: document.getElementById('metadataHED').value.trim(),
            dataset_type: document.getElementById('metadataType').value,
            Overview: {
                Main: document.getElementById('smOverviewMain').value || undefined,
                IndependentVariables: document.getElementById('smOverviewIV').value || undefined,
                DependentVariables: document.getElementById('smOverviewDV').value || undefined,
                ControlVariables: document.getElementById('smOverviewCV').value || undefined,
                QualityAssessment: document.getElementById('smOverviewQA').value || undefined,
            },
            StudyDesign: {
                Type: document.getElementById('smSDType').value || undefined,
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
                    return list.length ? list : undefined;
                })(),
                Location: (function() {
                    const list = getRecLocationList();
                    return list.length ? list : undefined;
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
                TargetSampleSize: parseInt(document.getElementById('smEligSampleSize').value) || undefined,
                PowerAnalysis: document.getElementById('smEligPower').value || undefined,
            },
            Procedure: {
                Overview: document.getElementById('smProcOverview').value || undefined,
                InformedConsent: document.getElementById('smProcConsent').value || undefined,
                QualityControl: textToArray(document.getElementById('smProcQC').value) || undefined,
                MissingDataHandling: document.getElementById('smProcMissing').value || undefined,
                Debriefing: document.getElementById('smProcDebriefing').value || undefined,
                AdditionalData: document.getElementById('smProcAdditionalData').value || undefined,
                Notes: document.getElementById('smProcNotes').value || undefined,
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
                    </div>
                `);

                applyCurrentProject(result.current_project);
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
            preliminaryButtons.forEach(btn => { btn.disabled = false; });
        }
    }

    const createProjectSubmitBtn = document.getElementById('createProjectSubmitBtn');
    if (createProjectSubmitBtn) {
        createProjectSubmitBtn.addEventListener('click', (event) => {
            const createSection = document.getElementById('section-create');
            const createActive = createSection && createSection.classList.contains('active');
            if (!createActive && getProjectStateSnapshot().path) {
                event.preventDefault();
                const studyMetadataForm = document.getElementById('studyMetadataForm');
                if (studyMetadataForm && typeof studyMetadataForm.requestSubmit === 'function') {
                    studyMetadataForm.requestSubmit();
                } else if (studyMetadataForm) {
                    studyMetadataForm.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                }
                return;
            }
            event.preventDefault();
            submitCreateProject();
        });
    }

    const createProjectSubmitBtnTop = document.getElementById('createProjectSubmitBtnTop');
    if (createProjectSubmitBtnTop) {
        createProjectSubmitBtnTop.addEventListener('click', (event) => {
            event.preventDefault();
            submitCreateProject({ triggerButton: createProjectSubmitBtnTop });
        });
    }

    const preliminaryCreateBtn = document.getElementById('preliminaryCreateBtn');
    if (preliminaryCreateBtn) {
        preliminaryCreateBtn.addEventListener('click', (event) => {
            event.preventDefault();
            submitCreateProject({ forcePreliminary: true, triggerButton: preliminaryCreateBtn });
        });
    }

    const preliminaryCreateBtnTop = document.getElementById('preliminaryCreateBtnTop');
    if (preliminaryCreateBtnTop) {
        preliminaryCreateBtnTop.addEventListener('click', (event) => {
            event.preventDefault();
            submitCreateProject({ forcePreliminary: true, triggerButton: preliminaryCreateBtnTop });
        });
    }

    createProjectFormEl.addEventListener('submit', (event) => {
        event.preventDefault();
        submitCreateProject();
    });
}
