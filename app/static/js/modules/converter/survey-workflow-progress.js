export function createSurveyWorkflowProgressController({
    surveyRunProgressContainer,
    surveyRunProgressBar,
    surveyRunProgressLabel,
    surveyRunProgressPercent,
    onProgressStateChanged,
}) {
    let runProgressMode = null;
    let runProgressPercentValue = 0;
    let runProgressLabelValue = '';
    let runProgressTimer = null;
    let runProgressHideTimer = null;
    let isSurveyRunAwaitingConfirmation = false;

    function notifyStateChanged() {
        if (typeof onProgressStateChanged === 'function') {
            onProgressStateChanged();
        }
    }

    function stopSurveyRunProgressTimer() {
        if (runProgressTimer !== null) {
            window.clearInterval(runProgressTimer);
            runProgressTimer = null;
        }
    }

    function clearSurveyRunProgressHideTimer() {
        if (runProgressHideTimer !== null) {
            window.clearTimeout(runProgressHideTimer);
            runProgressHideTimer = null;
        }
    }

    function getSurveyRunModeLabel(mode) {
        return mode === 'convert' ? 'conversion' : 'preview';
    }

    function setSurveyRunProgressAppearance(variant = 'info', animated = true) {
        if (!surveyRunProgressContainer || !surveyRunProgressBar) {
            return;
        }

        const normalizedVariant = variant === 'danger'
            ? 'danger'
            : (variant === 'success'
                ? 'success'
                : (variant === 'warning' ? 'warning' : 'info'));

        surveyRunProgressContainer.classList.remove('alert-info', 'alert-success', 'alert-warning', 'alert-danger');
        surveyRunProgressContainer.classList.add(`alert-${normalizedVariant}`);

        surveyRunProgressBar.classList.remove('bg-info', 'bg-success', 'bg-warning', 'bg-danger');
        surveyRunProgressBar.classList.remove('progress-bar-striped', 'progress-bar-animated');
        surveyRunProgressBar.classList.add(`bg-${normalizedVariant}`);

        if (animated) {
            surveyRunProgressBar.classList.add('progress-bar-striped', 'progress-bar-animated');
        }
    }

    function renderSurveyRunProgress() {
        if (!surveyRunProgressContainer || !surveyRunProgressBar) {
            return;
        }

        const rounded = Math.max(0, Math.min(100, Math.round(runProgressPercentValue)));
        surveyRunProgressBar.style.width = `${rounded}%`;
        surveyRunProgressBar.setAttribute('aria-valuenow', String(rounded));

        if (surveyRunProgressPercent) {
            surveyRunProgressPercent.textContent = `${rounded}%`;
        }
        if (surveyRunProgressLabel) {
            surveyRunProgressLabel.textContent = runProgressLabelValue || 'Running...';
        }
    }

    function hideSurveyRunProgress() {
        stopSurveyRunProgressTimer();
        clearSurveyRunProgressHideTimer();
        runProgressMode = null;
        runProgressPercentValue = 0;
        runProgressLabelValue = '';
        isSurveyRunAwaitingConfirmation = false;

        if (!surveyRunProgressContainer || !surveyRunProgressBar) {
            notifyStateChanged();
            return;
        }

        surveyRunProgressContainer.classList.add('d-none');
        surveyRunProgressBar.style.width = '0%';
        surveyRunProgressBar.setAttribute('aria-valuenow', '0');
        if (surveyRunProgressPercent) {
            surveyRunProgressPercent.textContent = '0%';
        }
        if (surveyRunProgressLabel) {
            surveyRunProgressLabel.textContent = 'Preparing preview...';
        }
        notifyStateChanged();
    }

    function startSurveyRunProgressTimer(mode) {
        stopSurveyRunProgressTimer();

        runProgressTimer = window.setInterval(() => {
            if (runProgressMode !== mode || isSurveyRunAwaitingConfirmation) {
                stopSurveyRunProgressTimer();
                return;
            }

            const cap = mode === 'convert' ? 94 : 90;
            const increment = runProgressPercentValue < 25
                ? 7
                : (runProgressPercentValue < 50 ? 4 : (runProgressPercentValue < 75 ? 2 : 1));

            runProgressPercentValue = Math.min(cap, runProgressPercentValue + increment);
            renderSurveyRunProgress();
        }, 800);
    }

    function setSurveyRunProgress({
        mode,
        percent,
        label,
        variant = 'info',
        animated = true,
    }) {
        if (!surveyRunProgressContainer || !surveyRunProgressBar) {
            return;
        }

        clearSurveyRunProgressHideTimer();
        surveyRunProgressContainer.classList.remove('d-none');

        if (mode) {
            runProgressMode = mode;
        }

        if (Number.isFinite(Number(percent))) {
            runProgressPercentValue = Math.max(0, Math.min(100, Number(percent)));
        }

        if (typeof label === 'string' && label.trim()) {
            runProgressLabelValue = label.trim();
        }

        setSurveyRunProgressAppearance(variant, animated);
        renderSurveyRunProgress();
    }

    function startSurveyRunProgress(mode) {
        if (!surveyRunProgressContainer || !surveyRunProgressBar) {
            return;
        }

        const modeLabel = getSurveyRunModeLabel(mode);
        isSurveyRunAwaitingConfirmation = false;
        setSurveyRunProgress({
            mode,
            percent: 8,
            label: `Preparing ${modeLabel}...`,
            variant: 'info',
            animated: true,
        });

        startSurveyRunProgressTimer(mode);
        notifyStateChanged();
    }

    function advanceSurveyRunProgress(mode, percent, label) {
        if (!surveyRunProgressContainer || !surveyRunProgressBar) {
            return;
        }
        if (runProgressMode !== mode) {
            return;
        }

        const nextPercent = Number(percent);
        if (Number.isFinite(nextPercent)) {
            runProgressPercentValue = Math.max(runProgressPercentValue, Math.min(100, nextPercent));
        }
        if (typeof label === 'string' && label.trim()) {
            runProgressLabelValue = label.trim();
        }
        setSurveyRunProgressAppearance('info', true);
        renderSurveyRunProgress();
    }

    function pauseSurveyRunProgress(mode, label) {
        if (!surveyRunProgressContainer || !surveyRunProgressBar) {
            return;
        }
        if (runProgressMode !== mode) {
            return;
        }

        isSurveyRunAwaitingConfirmation = true;
        stopSurveyRunProgressTimer();
        if (typeof label === 'string' && label.trim()) {
            runProgressLabelValue = label.trim();
        }
        setSurveyRunProgressAppearance('warning', false);
        renderSurveyRunProgress();
        notifyStateChanged();
    }

    function resumeSurveyRunProgress(mode, percent, label) {
        if (!surveyRunProgressContainer || !surveyRunProgressBar) {
            return;
        }
        if (runProgressMode !== mode) {
            return;
        }

        isSurveyRunAwaitingConfirmation = false;
        const nextPercent = Number(percent);
        if (Number.isFinite(nextPercent)) {
            runProgressPercentValue = Math.max(runProgressPercentValue, Math.min(100, nextPercent));
        }
        if (typeof label === 'string' && label.trim()) {
            runProgressLabelValue = label.trim();
        }
        setSurveyRunProgressAppearance('info', true);
        renderSurveyRunProgress();
        startSurveyRunProgressTimer(mode);
        notifyStateChanged();
    }

    function finishSurveyRunProgress(mode, outcome) {
        if (!surveyRunProgressContainer || !surveyRunProgressBar) {
            return;
        }

        isSurveyRunAwaitingConfirmation = false;
        stopSurveyRunProgressTimer();
        const modeTitle = mode === 'convert' ? 'Conversion' : 'Preview';

        if (outcome === 'success') {
            setSurveyRunProgress({
                mode,
                percent: 100,
                label: `${modeTitle} completed.`,
                variant: 'success',
                animated: false,
            });
            runProgressHideTimer = window.setTimeout(() => {
                hideSurveyRunProgress();
            }, 1800);
            notifyStateChanged();
            return;
        }

        if (outcome === 'paused') {
            setSurveyRunProgress({
                mode,
                percent: 100,
                label: `${modeTitle} paused. Apply questionnaire versions, then run again.`,
                variant: 'warning',
                animated: false,
            });
            notifyStateChanged();
            return;
        }

        if (outcome === 'action_required') {
            setSurveyRunProgress({
                mode,
                percent: 100,
                label: `${modeTitle} stopped. Resolve required issues and run again.`,
                variant: 'warning',
                animated: false,
            });
            notifyStateChanged();
            return;
        }

        if (outcome === 'error') {
            setSurveyRunProgress({
                mode,
                percent: 100,
                label: `${modeTitle} failed.`,
                variant: 'danger',
                animated: false,
            });
            notifyStateChanged();
            return;
        }

        if (outcome === 'canceled') {
            setSurveyRunProgress({
                mode,
                percent: 100,
                label: `${modeTitle} canceled.`,
                variant: 'warning',
                animated: false,
            });
            runProgressHideTimer = window.setTimeout(() => {
                hideSurveyRunProgress();
            }, 1800);
            notifyStateChanged();
            return;
        }

        if (outcome === 'retrying') {
            hideSurveyRunProgress();
            return;
        }

        hideSurveyRunProgress();
    }

    function getRunProgressMode() {
        return runProgressMode;
    }

    function getRunProgressPercent() {
        return runProgressPercentValue;
    }

    function getIsSurveyRunAwaitingConfirmation() {
        return isSurveyRunAwaitingConfirmation;
    }

    return {
        setSurveyRunProgress,
        hideSurveyRunProgress,
        startSurveyRunProgress,
        advanceSurveyRunProgress,
        pauseSurveyRunProgress,
        resumeSurveyRunProgress,
        finishSurveyRunProgress,
        getRunProgressMode,
        getRunProgressPercent,
        getIsSurveyRunAwaitingConfirmation,
    };
}
