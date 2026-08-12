export function createMetadataDescriptionController({
    fetchWithApiFallback,
    getCurrentProjectPath,
    getCurrentProjectName,
    setCurrentProjectName,
    getMetadataLoadToken,
    isProjectRequestCurrent,
    withProjectPathQuery,
    getAuthorsList,
    getCitationAuthorsList,
    getEthicsApprovals,
    getFundingList,
    getBidsVersion,
    getAuthorOptionalFormatErrors,
    normalizeDoi,
    isValidDoiFormat,
    buildDraftDatasetDescriptionForValidation,
    buildDraftCitationFieldsForValidation,
    displayMetadataIssues,
    refreshMetadataValidationState,
    refreshCitationHealthStatus,
    refreshMetadataSyncStatus,
    cleanMetadataText,
    cleanMetadataList,
    setAuthorsList,
    setEthicsApprovals,
    setFundingFromDescription,
}) {
    let descriptionValidationTimer = null;

    function getDefaultProjectSchemaVersion() {
        const schemaSelect = document.getElementById('metadataSchemaVersion');
        const selectedDefault = schemaSelect?.querySelector('option[selected]')?.value;
        const stableOption = schemaSelect?.querySelector('option[value="stable"]')?.value;
        return selectedDefault || stableOption || schemaSelect?.options?.[0]?.value || 'stable';
    }

    function getSelectedProjectSchemaVersion() {
        return (document.getElementById('metadataSchemaVersion')?.value || '').trim() || getDefaultProjectSchemaVersion();
    }

    function setProjectSchemaVersionSelection(schemaVersion) {
        const schemaSelect = document.getElementById('metadataSchemaVersion');
        if (!schemaSelect) return;

        const requestedVersion = String(schemaVersion || '').trim();
        const fallbackVersion = getDefaultProjectSchemaVersion();
        const nextValue = requestedVersion || fallbackVersion;
        const hasOption = Array.from(schemaSelect.options).some(option => option.value === nextValue);
        schemaSelect.value = hasOption ? nextValue : fallbackVersion;
    }

    async function validateDatasetDescriptionDraftLive() {
        const requestProjectPath = getCurrentProjectPath();
        if (!requestProjectPath) {
            return;
        }

        const payload = {
            description: buildDraftDatasetDescriptionForValidation(),
            citation_fields: buildDraftCitationFieldsForValidation(),
        };
        try {
            const response = await fetchWithApiFallback('/api/projects/description/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...payload, project_path: requestProjectPath })
            });
            const result = await response.json();
            if (result.success) {
                displayMetadataIssues(result.issues || []);
            }
        } catch (error) {
            console.debug('Live description validation failed:', error);
        }
    }

    function scheduleLiveDescriptionValidation() {
        if (descriptionValidationTimer) {
            clearTimeout(descriptionValidationTimer);
        }
        descriptionValidationTimer = setTimeout(() => {
            validateDatasetDescriptionDraftLive();
        }, 250);
    }

    async function loadProjectSchemaConfig() {
        const requestProjectPath = getCurrentProjectPath();
        if (!requestProjectPath) {
            setProjectSchemaVersionSelection(getDefaultProjectSchemaVersion());
            return;
        }

        const requestToken = getMetadataLoadToken();

        try {
            const response = await fetchWithApiFallback(
                withProjectPathQuery('/api/projects/schema-config', requestProjectPath)
            );
            const data = await response.json();
            if (!isProjectRequestCurrent(requestProjectPath, requestToken)) {
                return;
            }
            if (data.success) {
                setProjectSchemaVersionSelection(data.schema_version || getDefaultProjectSchemaVersion());
            }
        } catch (error) {
            if (!isProjectRequestCurrent(requestProjectPath, requestToken)) {
                return;
            }
            console.error('Error loading project schema config:', error);
            setProjectSchemaVersionSelection(getDefaultProjectSchemaVersion());
        }
    }

    async function saveProjectSchemaConfig() {
        const schemaVersion = getSelectedProjectSchemaVersion();
        const requestProjectPath = getCurrentProjectPath();
        if (!requestProjectPath) {
            return { success: true, schema_version: schemaVersion, deferred: true };
        }

        const response = await fetchWithApiFallback('/api/projects/schema-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_path: requestProjectPath, schema_version: schemaVersion })
        });
        const result = await response.json();
        if (!result.success) {
            throw new Error(result.error || 'Failed to save project schema version');
        }
        return result;
    }

    async function loadDatasetDescriptionFields() {
        const requestProjectPath = getCurrentProjectPath();
        if (!requestProjectPath) return;

        const requestToken = getMetadataLoadToken();

        try {
            await loadProjectSchemaConfig();
            if (!isProjectRequestCurrent(requestProjectPath, requestToken)) {
                return;
            }

            const response = await fetchWithApiFallback(
                withProjectPathQuery('/api/projects/description', requestProjectPath)
            );
            const data = await response.json();
            if (!isProjectRequestCurrent(requestProjectPath, requestToken)) {
                return;
            }

            if (data.success && data.description) {
                const desc = data.description;

                // An empty EthicsApprovals/Funding array in dataset_description.json
                // is ambiguous (never answered vs. explicitly declared none) - this
                // preference namespace is the only place that distinction is
                // recorded (set by the Yes/No click handlers). Best-effort: if it
                // fails to load, both toggles fall back to neutral/unanswered
                // rather than wrongly assuming a declared "No".
                let declared = {};
                try {
                    const declResponse = await fetchWithApiFallback(
                        withProjectPathQuery('/api/projects/preferences/metadataDeclarations', requestProjectPath)
                    );
                    const declData = await declResponse.json();
                    if (declData.success) declared = declData.preferences || {};
                } catch { /* fall back to neutral */ }

                document.getElementById('metadataName').value = cleanMetadataText(desc.Name || '');
                setAuthorsList(Array.isArray(desc.Authors) ? desc.Authors : (desc.Authors ? [desc.Authors] : []));
                document.getElementById('metadataAcknowledgements').value = cleanMetadataText(desc.Acknowledgements || '');
                document.getElementById('metadataDOI').value = cleanMetadataText(desc.DatasetDOI || '');
                setEthicsApprovals(desc.EthicsApprovals, declared.ethicsApprovalsDeclared === true);
                document.getElementById('metadataKeywords').value = cleanMetadataList(desc.Keywords).join(', ');
                document.getElementById('metadataHED').value = cleanMetadataList(desc.HEDVersion).join(', ');
                setFundingFromDescription(desc.Funding, declared.fundingDeclared === true);
                document.getElementById('metadataHowToAcknowledge').value = cleanMetadataText(desc.HowToAcknowledge || '');
                document.getElementById('metadataReferences').value = cleanMetadataList(desc.ReferencesAndLinks).join(', ');

                displayMetadataIssues(data.issues || []);

                setTimeout(() => {
                    refreshMetadataValidationState({
                        includeRequirementGapWarning: true
                    });
                }, 100);
            }
        } catch (error) {
            if (!isProjectRequestCurrent(requestProjectPath, requestToken)) {
                return;
            }
            console.error('Error loading dataset description:', error);
        }
    }

    async function saveDatasetDescription(projectPath = null) {
        try {
            const requestProjectPath = String(projectPath || getCurrentProjectPath()).trim();
            if (!requestProjectPath) {
                throw new Error('No project selected');
            }

            const nameField = document.getElementById('metadataName');
            if (!nameField || !nameField.value.trim()) {
                throw new Error('REQUIRED FIELD: Dataset Name is mandatory per BIDS specification');
            }

            const overviewMain = document.getElementById('smOverviewMain');
            const overviewText = overviewMain ? overviewMain.value.trim() : '';
            const doiValue = document.getElementById('metadataDOI').value.trim();
            const normalizedDoi = normalizeDoi(doiValue);

            const formatErrors = getAuthorOptionalFormatErrors();
            if (doiValue && !isValidDoiFormat(doiValue)) {
                formatErrors.push('Dataset DOI format is invalid (use 10.xxxx/... or https://doi.org/10.xxxx/...).');
            }
            if (formatErrors.length) {
                throw new Error(formatErrors.join(' '));
            }

            const description = {
                Name: nameField.value.trim(),
                Authors: getAuthorsList(),
                Acknowledgements: document.getElementById('metadataAcknowledgements').value,
                DatasetDOI: normalizedDoi,
                EthicsApprovals: getEthicsApprovals(),
                Keywords: document.getElementById('metadataKeywords').value.split(',').map(s => s.trim()).filter(s => s),
                BIDSVersion: getBidsVersion(),
                DatasetType: 'raw',
                HowToAcknowledge: document.getElementById('metadataHowToAcknowledge').value,
                Funding: getFundingList(),
                ReferencesAndLinks: document.getElementById('metadataReferences').value.split(',').map(s => s.trim()).filter(s => s),
                HEDVersion: document.getElementById('metadataHED').value.trim(),
                Description: overviewText || undefined
            };

            const citationFields = {
                Authors: getCitationAuthorsList(),
                HowToAcknowledge: document.getElementById('metadataHowToAcknowledge').value,
                ReferencesAndLinks: document.getElementById('metadataReferences').value.split(',').map(s => s.trim()).filter(s => s),
            };

            try {
                const currentResp = await fetchWithApiFallback(
                    withProjectPathQuery('/api/projects/description', requestProjectPath)
                );
                const currentData = await currentResp.json();
                if (currentData.success && currentData.description) {
                    description.GeneratedBy = currentData.description.GeneratedBy;
                    description.SourceDatasets = currentData.description.SourceDatasets;
                    description.DatasetLinks = currentData.description.DatasetLinks;
                }
            } catch (e) {
                console.warn('Could not merge with existing description', e);
            }

            const response = await fetchWithApiFallback('/api/projects/description', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: requestProjectPath, description, citation_fields: citationFields })
            });

            const result = await response.json();
            if (result.success) {
                await saveProjectSchemaConfig();
                displayMetadataIssues(result.issues || []);
                if (requestProjectPath === getCurrentProjectPath()) {
                    await refreshCitationHealthStatus();
                    await refreshMetadataSyncStatus();
                }

                if (requestProjectPath === getCurrentProjectPath() && description.Name && description.Name !== getCurrentProjectName()) {
                    setCurrentProjectName(description.Name);
                }
            } else {
                throw new Error(result.error || 'Failed to save metadata');
            }
        } catch (error) {
            console.error('Error saving dataset description:', error);
            throw error;
        }
    }

    return {
        getDefaultProjectSchemaVersion,
        validateDatasetDescriptionDraftLive,
        scheduleLiveDescriptionValidation,
        saveProjectSchemaConfig,
        loadDatasetDescriptionFields,
        saveDatasetDescription,
    };
}