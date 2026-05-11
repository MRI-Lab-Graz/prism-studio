export function isDelimitedSurveyFilename(filename) {
    const normalized = String(filename || '').toLowerCase();
    return normalized.endsWith('.csv') || normalized.endsWith('.tsv');
}

export function getSelectedSeparator(filename = '', convertSeparator = null) {
    if (!isDelimitedSurveyFilename(filename)) {
        return 'auto';
    }
    if (!convertSeparator) {
        return 'auto';
    }
    return (convertSeparator.value || 'auto').toLowerCase();
}

export function updateSeparatorVisibility(filename = '', surveySeparatorGroup = null) {
    if (!surveySeparatorGroup) return;
    surveySeparatorGroup.classList.toggle('d-none', !isDelimitedSurveyFilename(filename));
}
