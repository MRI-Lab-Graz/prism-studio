export function createProjectMaintenanceActions({
    fetchWithApiFallback,
    reloadProject,
    onCurrentProjectCleared,
}) {
    async function fixIssue(path, code) {
        try {
            const response = await fetchWithApiFallback('/api/projects/fix', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path, fix_codes: [code] })
            });
            const result = await response.json();

            if (result.success) {
                await reloadProject(path);
            } else {
                alert('Error applying fix: ' + result.error);
            }
        } catch (error) {
            alert('Error: ' + error.message);
        }
    }

    async function fixAllIssues(path) {
        try {
            const response = await fetchWithApiFallback('/api/projects/fix', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });
            const result = await response.json();

            if (result.success) {
                await reloadProject(path);
            } else {
                alert('Error applying fixes: ' + result.error);
            }
        } catch (error) {
            alert('Error: ' + error.message);
        }
    }

    async function clearCurrentProject() {
        try {
            await fetchWithApiFallback('/api/projects/current', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: null })
            });
            onCurrentProjectCleared();
        } catch (error) {
            console.error('Error clearing project:', error);
        }
    }

    return {
        fixIssue,
        fixAllIssues,
        clearCurrentProject,
    };
}