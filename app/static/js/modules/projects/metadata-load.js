export function createStudyMetadataLoadController({
    getCurrentProjectPath,
    getSubmitInFlight,
    getFormSnapshot,
    incrementMetadataLoadToken,
    isProjectRequestCurrent,
    onLoadStateChanged,
    beforeLoad,
    fetchStudyMetadata,
    applyStudyMetadataPayload,
    refreshStatusSnapshots,
    setLoadErrorStatus,
    clearLoadStatus,
    setFormLocked,
}) {
    let studyMetadataLoadInFlight = false;
    let studyMetadataLoadInFlightToken = 0;
    let studyMetadataReadyProjectPath = '';
    let studyMetadataBaselineSnapshot = '';

    function captureBaseline() {
        studyMetadataBaselineSnapshot = getFormSnapshot();
    }

    function resetTracking() {
        studyMetadataLoadInFlight = false;
        studyMetadataLoadInFlightToken = 0;
        studyMetadataReadyProjectPath = '';
        studyMetadataBaselineSnapshot = '';
    }

    function isReadyForCurrentProject() {
        const currentProjectPath = getCurrentProjectPath();
        return Boolean(currentProjectPath) && studyMetadataReadyProjectPath === currentProjectPath;
    }

    function isBusy() {
        return studyMetadataLoadInFlight || getSubmitInFlight();
    }

    function hasUnsavedChanges() {
        if (!isReadyForCurrentProject() || studyMetadataLoadInFlight || getSubmitInFlight()) {
            return false;
        }

        return getFormSnapshot() !== studyMetadataBaselineSnapshot;
    }

    async function loadStudyMetadata() {
        let requestProjectPath = '';
        let requestToken = null;
        let loadSucceeded = false;

        try {
            requestProjectPath = getCurrentProjectPath();
            if (!requestProjectPath) return;

            requestToken = incrementMetadataLoadToken();
            // Lock the form for the whole round trip. applyStudyMetadataPayload()
            // overwrites every field unconditionally, so anything typed while a
            // load is in flight would be silently wiped when it lands - and then
            // saved back over, because the submit path reloads an unready form.
            setFormLocked(true);
            studyMetadataLoadInFlight = true;
            studyMetadataLoadInFlightToken = requestToken;
            studyMetadataReadyProjectPath = '';
            studyMetadataBaselineSnapshot = '';
            onLoadStateChanged();

            await beforeLoad();
            if (!isProjectRequestCurrent(requestProjectPath, requestToken)) {
                return;
            }

            const response = await fetchStudyMetadata(requestProjectPath);
            const data = await response.json();
            if (!isProjectRequestCurrent(requestProjectPath, requestToken)) {
                return;
            }
            if (!data.success) {
                setLoadErrorStatus();
                return;
            }

            applyStudyMetadataPayload(data);
            await refreshStatusSnapshots();
            loadSucceeded = true;
        } catch (error) {
            console.error('Error loading study metadata:', error);
            if (requestToken !== null && isProjectRequestCurrent(requestProjectPath, requestToken)) {
                setLoadErrorStatus();
            }
        } finally {
            if (requestToken !== null && requestToken === studyMetadataLoadInFlightToken) {
                studyMetadataLoadInFlight = false;
            }

            if (requestToken !== null && isProjectRequestCurrent(requestProjectPath, requestToken)) {
                if (loadSucceeded) {
                    studyMetadataReadyProjectPath = requestProjectPath;
                    captureBaseline();
                    setFormLocked(false);
                    if (!getSubmitInFlight()) {
                        clearLoadStatus();
                    }
                } else {
                    // Deliberately stays locked: a form that never received the
                    // stored metadata would save blanks over it.
                    studyMetadataReadyProjectPath = '';
                }

                onLoadStateChanged();
            }
        }
    }

    return {
        captureBaseline,
        resetTracking,
        isReadyForCurrentProject,
        isBusy,
        hasUnsavedChanges,
        getLoadInFlight: () => studyMetadataLoadInFlight,
        getReadyProjectPath: () => studyMetadataReadyProjectPath,
        loadStudyMetadata,
    };
}