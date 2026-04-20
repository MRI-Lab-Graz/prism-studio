document.addEventListener('DOMContentLoaded', function() {
    const specificationsRoot = document.getElementById('specificationsRoot');
    const surveyExportLink = document.getElementById('specSurveyExportLink');
    const recipesLink = document.getElementById('specRecipesLink');

    let currentProjectPath = specificationsRoot
        ? String(specificationsRoot.dataset.currentProjectPath || '').trim()
        : '';

    function syncProjectBoundLink(link) {
        if (!link || link.dataset.toolAvailable !== 'true') {
            return;
        }

        const hasCurrentProject = Boolean(currentProjectPath);
        link.href = hasCurrentProject ? (link.dataset.enabledUrl || '#') : '#';
        link.classList.toggle('disabled', !hasCurrentProject);

        if (hasCurrentProject) {
            link.removeAttribute('title');
            link.removeAttribute('aria-disabled');
            return;
        }

        link.setAttribute('title', 'Please load a project first');
        link.setAttribute('aria-disabled', 'true');
    }

    function syncDerivativeLinks() {
        syncProjectBoundLink(surveyExportLink);
        syncProjectBoundLink(recipesLink);
    }

    window.addEventListener('prism-project-changed', function(event) {
        const eventState = event && event.detail ? event.detail : null;
        currentProjectPath = eventState && typeof eventState.path === 'string'
            ? eventState.path.trim()
            : '';
        syncDerivativeLinks();
    });

    syncDerivativeLinks();
});