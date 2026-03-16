/**
 * Shared project state helpers.
 * Uses the centralized store when available and falls back to legacy globals.
 */

function normalizeStateValue(value) {
    return typeof value === 'string' ? value.trim() : '';
}

export function getProjectStateStore() {
    return window.prismProjectStateStore && typeof window.prismProjectStateStore.getState === 'function'
        ? window.prismProjectStateStore
        : null;
}

export function getProjectStateSnapshot() {
    const stateStore = getProjectStateStore();
    if (stateStore) {
        return stateStore.getState();
    }

    if (typeof window.getCurrentProjectState === 'function') {
        const fromGlobalHelper = window.getCurrentProjectState();
        return {
            path: normalizeStateValue(fromGlobalHelper && fromGlobalHelper.path),
            name: normalizeStateValue(fromGlobalHelper && fromGlobalHelper.name),
        };
    }

    return {
        path: normalizeStateValue(window.currentProjectPath),
        name: normalizeStateValue(window.currentProjectName),
    };
}

export function resolveCurrentProjectPath() {
    return normalizeStateValue(getProjectStateSnapshot().path);
}

export function resolveCurrentProjectName() {
    return normalizeStateValue(getProjectStateSnapshot().name);
}

export function setProjectStateSnapshot(path, name) {
    const nextState = {
        path: normalizeStateValue(path),
        name: normalizeStateValue(name),
    };

    const stateStore = getProjectStateStore();
    if (stateStore && typeof stateStore.setState === 'function') {
        return stateStore.setState(nextState);
    }

    window.currentProjectPath = nextState.path;
    window.currentProjectName = nextState.name;
    return { ...nextState };
}
