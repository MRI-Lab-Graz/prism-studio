document.addEventListener('DOMContentLoaded', () => {
    const backToTopBtn = document.getElementById('backToTopBtn');
    if (backToTopBtn) {
        backToTopBtn.addEventListener('click', (event) => {
            event.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    const revalidateForm = document.getElementById('revalidateForm');
    if (!revalidateForm) {
        return;
    }

    const revalidateMode = document.getElementById('revalidateMode');
    const revalidateSubmitBtn = document.getElementById('revalidateSubmitBtn');
    const progressPanel = document.getElementById('revalidateProgressPanel');
    const progressBar = document.getElementById('revalidateProgressBar');
    const progressLabel = document.getElementById('revalidateProgressLabel');
    const statusText = document.getElementById('revalidateStatusText');
    const progressError = document.getElementById('revalidateProgressError');
    const resultActionNodes = Array.from(document.querySelectorAll('[data-result-action]'));
    const defaultSubmitHtml = revalidateSubmitBtn ? revalidateSubmitBtn.innerHTML : '';

    let revalidationInProgress = false;
    let progressDisplayState = {
        phase: 'idle',
        visualProgress: 0,
        phaseStartedAt: 0,
    };

    function getFallbackApiOrigin() {
        const configuredOrigin = (window.PRISM_API_ORIGIN || '').trim();
        if (configuredOrigin) {
            return configuredOrigin.replace(/\/$/, '');
        }
        return 'http://127.0.0.1:5001';
    }

    function canRetryApiWithFallback(url) {
        const protocol = (window.location && window.location.protocol) ? window.location.protocol : '';
        const isRelativeApiRequest = typeof url === 'string' && url.startsWith('/');
        return isRelativeApiRequest && protocol !== 'http:' && protocol !== 'https:';
    }

    async function fetchWithApiFallback(
        url,
        options = {},
        fallbackMessage = 'Cannot reach PRISM backend API. Please restart PRISM Studio and try again.'
    ) {
        try {
            return await fetch(url, options);
        } catch (primaryError) {
            if (!canRetryApiWithFallback(url)) {
                throw primaryError;
            }

            const fallbackUrl = `${getFallbackApiOrigin()}${url}`;
            try {
                return await fetch(fallbackUrl, options);
            } catch (_fallbackError) {
                throw new Error(fallbackMessage);
            }
        }
    }

    function hideRevalidationError() {
        if (!progressError) {
            return;
        }
        progressError.textContent = '';
        progressError.classList.add('d-none');
    }

    function showRevalidationError(message) {
        if (!progressError) {
            return;
        }
        progressError.textContent = message;
        progressError.classList.remove('d-none');
    }

    function setSubmitLoading(loading) {
        if (!revalidateSubmitBtn) {
            return;
        }
        if (loading) {
            revalidateSubmitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Re-validating...';
            return;
        }
        revalidateSubmitBtn.innerHTML = defaultSubmitHtml;
    }

    function setActionsDisabled(disabled) {
        resultActionNodes.forEach((node) => {
            if (node.tagName === 'A') {
                if (disabled) {
                    node.dataset.prevAriaDisabled = node.getAttribute('aria-disabled') || '';
                    node.classList.add('result-action-disabled');
                    node.setAttribute('aria-disabled', 'true');
                } else {
                    node.classList.remove('result-action-disabled');
                    const previousAriaDisabled = node.dataset.prevAriaDisabled || '';
                    if (previousAriaDisabled) {
                        node.setAttribute('aria-disabled', previousAriaDisabled);
                    } else {
                        node.removeAttribute('aria-disabled');
                    }
                    delete node.dataset.prevAriaDisabled;
                }
                return;
            }

            if (disabled) {
                node.dataset.prevDisabled = node.disabled ? 'true' : 'false';
                node.disabled = true;
            } else {
                const previousDisabled = node.dataset.prevDisabled === 'true';
                node.disabled = previousDisabled;
                delete node.dataset.prevDisabled;
            }
        });

        if (!revalidateMode) {
            return;
        }

        if (disabled) {
            revalidateMode.dataset.prevDisabled = revalidateMode.disabled ? 'true' : 'false';
            revalidateMode.disabled = true;
            return;
        }

        const previousDisabled = revalidateMode.dataset.prevDisabled === 'true';
        revalidateMode.disabled = previousDisabled;
        delete revalidateMode.dataset.prevDisabled;
    }

    function setProgressPhase(phase, percent) {
        if (progressDisplayState.phase === phase) {
            return;
        }

        progressDisplayState.phase = phase;
        progressDisplayState.phaseStartedAt = Date.now();
        if (Number.isFinite(Number(percent))) {
            progressDisplayState.visualProgress = Math.max(
                progressDisplayState.visualProgress || 0,
                Number(percent) || 0
            );
        }
    }

    function setRevalidationProgress(percent, message, options = {}) {
        const safePercent = Math.max(0, Math.min(100, Number(percent) || 0));
        const animated = options.animated !== false;
        const barText = Object.prototype.hasOwnProperty.call(options, 'barText')
            ? String(options.barText)
            : `${Math.round(safePercent)}%`;
        const labelText = Object.prototype.hasOwnProperty.call(options, 'labelText')
            ? String(options.labelText)
            : `${Math.round(safePercent)}%`;

        if (progressPanel) {
            progressPanel.classList.remove('d-none');
        }

        if (progressBar) {
            progressBar.style.width = `${safePercent}%`;
            progressBar.setAttribute('aria-valuenow', String(Math.round(safePercent)));
            progressBar.textContent = barText;
            progressBar.classList.toggle('progress-bar-striped', animated);
            progressBar.classList.toggle('progress-bar-animated', animated);
        }

        if (progressLabel) {
            progressLabel.textContent = labelText;
        }

        if (statusText) {
            statusText.textContent = message || 'Running re-validation...';
        }
    }

    function computeDisplayedProgress(payload, progressFloor) {
        const reportedProgress = Number.isFinite(Number(payload.progress))
            ? Number(payload.progress)
            : 0;
        const phase = payload.phase || 'validation';
        const status = payload.status || 'running';
        const baseProgress = Math.max(progressFloor, Math.round(reportedProgress));

        setProgressPhase(phase, baseProgress);

        if (status === 'complete' || status === 'error') {
            progressDisplayState.visualProgress = baseProgress;
            return {
                displayProgress: baseProgress,
                labelText: `${Math.round(baseProgress)}%`,
                barText: `${Math.round(baseProgress)}%`,
                animated: false,
            };
        }

        if (phase === 'bids') {
            const elapsedSeconds = Math.max(
                0,
                (Date.now() - progressDisplayState.phaseStartedAt) / 1000
            );
            const estimatedTarget = Math.min(
                97,
                Math.max(baseProgress, reportedProgress + Math.floor(elapsedSeconds / 4))
            );
            progressDisplayState.visualProgress = Math.max(
                baseProgress,
                progressDisplayState.visualProgress,
                estimatedTarget
            );
            const visualProgress = Math.min(97, progressDisplayState.visualProgress);
            return {
                displayProgress: visualProgress,
                labelText: visualProgress >= 95 ? 'Almost done' : 'Final stage',
                barText: '',
                animated: true,
            };
        }

        progressDisplayState.visualProgress = baseProgress;
        return {
            displayProgress: baseProgress,
            labelText: `${Math.round(baseProgress)}%`,
            barText: `${Math.round(baseProgress)}%`,
            animated: true,
        };
    }

    async function pollRevalidationProgress(progressUrl, progressFloor = 0) {
        const MAX_POLLS = 4500;

        for (let attempt = 0; attempt < MAX_POLLS; attempt += 1) {
            await new Promise((resolve) => setTimeout(resolve, 800));

            const response = await fetchWithApiFallback(progressUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                cache: 'no-store',
            });
            const payload = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(payload.error || 'Failed to retrieve re-validation progress.');
            }

            const status = payload.status || 'running';
            const progressUi = computeDisplayedProgress(payload, progressFloor);
            let statusMessage = payload.message || 'Running re-validation...';
            if (payload.phase === 'bids' && status === 'running') {
                statusMessage = 'Running BIDS validator... final phase, progress is estimated.';
            }

            setRevalidationProgress(progressUi.displayProgress, statusMessage, {
                animated: progressUi.animated,
                barText: progressUi.barText,
                labelText: progressUi.labelText,
            });

            if (status === 'complete') {
                if (payload.redirect_url) {
                    window.location.href = payload.redirect_url;
                    return;
                }
                if (payload.result_id) {
                    window.location.href = `/results/${encodeURIComponent(payload.result_id)}`;
                    return;
                }
                window.location.reload();
                return;
            }

            if (status === 'error') {
                throw new Error(payload.error || payload.message || 'Re-validation failed.');
            }
        }

        throw new Error('Re-validation timed out. Please check logs and try again.');
    }

    function modeLabelFromValue(modeValue) {
        if (modeValue === 'bids-only' || modeValue === 'bids') {
            return 'BIDS-only';
        }
        if (modeValue === 'prism-only' || modeValue === 'prism') {
            return 'PRISM-only';
        }
        return 'standard';
    }

    async function startRevalidation(event) {
        event.preventDefault();

        if (revalidationInProgress) {
            return;
        }

        revalidationInProgress = true;
        progressDisplayState = {
            phase: 'idle',
            visualProgress: 0,
            phaseStartedAt: 0,
        };

        hideRevalidationError();
        setActionsDisabled(true);
        setSubmitLoading(true);

        const selectedMode = revalidateMode ? revalidateMode.value : 'standard';
        setRevalidationProgress(1, `Starting ${modeLabelFromValue(selectedMode)} re-validation...`, {
            animated: true,
        });

        const formData = new FormData(revalidateForm);

        try {
            const response = await fetchWithApiFallback(revalidateForm.action, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                body: formData,
                cache: 'no-store',
            });
            const payload = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(payload.error || 'Failed to start re-validation.');
            }

            if (!payload.progress_url) {
                throw new Error('Re-validation job did not provide a progress URL.');
            }

            await pollRevalidationProgress(payload.progress_url, 5);
        } catch (error) {
            revalidationInProgress = false;
            setActionsDisabled(false);
            setSubmitLoading(false);
            showRevalidationError(error.message || 'Re-validation failed.');
        }
    }

    revalidateForm.addEventListener('submit', startRevalidation);
});
