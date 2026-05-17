export function createSurveySelectedInputController({
    convertExcelFile = null,
    getConvertServerFilePath = () => '',
} = {}) {
    const getServerFilePath = () => String(getConvertServerFilePath() || '');

    function getSelectedSurveyFile() {
        return (convertExcelFile && convertExcelFile.files && convertExcelFile.files[0])
            ? convertExcelFile.files[0]
            : null;
    }

    function getSelectedSurveyFilename() {
        const selectedFile = getSelectedSurveyFile();
        if (selectedFile && selectedFile.name) {
            return selectedFile.name;
        }
        const serverFilePath = getServerFilePath();
        if (serverFilePath) {
            const tokens = serverFilePath.split('/');
            return tokens[tokens.length - 1] || serverFilePath;
        }
        return '';
    }

    function hasSelectedSurveyInput() {
        return Boolean(getSelectedSurveyFile() || getServerFilePath());
    }

    function appendSurveyInputToFormData(formData) {
        const selectedFile = getSelectedSurveyFile();
        if (selectedFile) {
            formData.append('excel', selectedFile);
            return { file: selectedFile, filename: selectedFile.name };
        }
        const serverFilePath = getServerFilePath();
        if (serverFilePath) {
            formData.append('source_file_path', serverFilePath);
            return { file: null, filename: getSelectedSurveyFilename() };
        }
        return { file: null, filename: '' };
    }

    function getSelectedSurveyFingerprint() {
        const selectedFile = getSelectedSurveyFile();
        if (selectedFile) {
            const lastModified = Number.isFinite(Number(selectedFile.lastModified))
                ? Number(selectedFile.lastModified)
                : 0;
            return `upload:${selectedFile.name}:${selectedFile.size}:${lastModified}`;
        }
        const serverFilePath = getServerFilePath();
        if (serverFilePath) {
            return `server:${serverFilePath}`;
        }
        return '';
    }

    return {
        getSelectedSurveyFile,
        getSelectedSurveyFilename,
        hasSelectedSurveyInput,
        appendSurveyInputToFormData,
        getSelectedSurveyFingerprint,
    };
}
