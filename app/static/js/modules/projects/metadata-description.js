export function createMetadataDescriptionController({
    fetchWithApiFallback,
    getCurrentProjectPath,
    getMetadataLoadToken,
    isProjectRequestCurrent,
    withProjectPathQuery,
    buildDraftDatasetDescriptionForValidation,
    buildDraftCitationFieldsForValidation,
    displayMetadataIssues,
    refreshMetadataValidationState,
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

                document.getElementById('metadataName').value = cleanMetadataText(desc.Name || '');
                setAuthorsList(Array.isArray(desc.Authors) ? desc.Authors : (desc.Authors ? [desc.Authors] : []));
                document.getElementById('metadataLicense').value = cleanMetadataText(desc.License || '') || 'CC0';
                document.getElementById('metadataAcknowledgements').value = cleanMetadataText(desc.Acknowledgements || '');
                document.getElementById('metadataDOI').value = cleanMetadataText(desc.DatasetDOI || '');
                setEthicsApprovals(desc.EthicsApprovals);
                document.getElementById('metadataKeywords').value = cleanMetadataList(desc.Keywords).join(', ');
                document.getElementById('metadataType').value = cleanMetadataText(desc.DatasetType || '');
                document.getElementById('metadataHED').value = cleanMetadataList(desc.HEDVersion).join(', ');
                setFundingFromDescription(desc.Funding);
                document.getElementById('metadataHowToAcknowledge').value = cleanMetadataText(desc.HowToAcknowledge || '');
                document.getElementById('metadataReferences').value = cleanMetadataList(desc.ReferencesAndLinks).join(', ');

                displayMetadataIssues(data.issues || []);

                setTimeout(() => {
                    refreshMetadataValidationState({
                        onlyFilled: true,
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

    return {
        getDefaultProjectSchemaVersion,
        validateDatasetDescriptionDraftLive,
        scheduleLiveDescriptionValidation,
        saveProjectSchemaConfig,
        loadDatasetDescriptionFields,
    };
}