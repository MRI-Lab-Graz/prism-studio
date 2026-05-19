/**
 * Shared project state helpers.
 * Uses the centralized store when available and falls back to legacy globals.
 */

function normalizeStateValue(value) {
    return typeof value === 'string' ? value.trim() : '';
}

function normalizeBooleanStateValue(value) {
    if (typeof value === 'boolean') {
        return value;
    }
    if (typeof value === 'string') {
        const normalized = value.trim().toLowerCase();
        return normalized === 'true' || normalized === '1' || normalized === 'yes' || normalized === 'on';
    }
    return Boolean(value);
}

function normalizeDataladStateValue(value, fallbackPath = '') {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
        return {
            enabled: false,
            available: false,
            annexAvailable: false,
            canSave: false,
            canEnable: false,
            message: fallbackPath ? 'Current project is not a DataLad dataset.' : 'Load a project to see DataLad status.',
            path: fallbackPath,
        };
    }

    const resolvedPath = normalizeStateValue(value.path) || fallbackPath;
    return {
        enabled: normalizeBooleanStateValue(value.enabled),
        available: normalizeBooleanStateValue(value.available),
        annexAvailable: normalizeBooleanStateValue(value.annex_available ?? value.annexAvailable),
        canSave: normalizeBooleanStateValue(value.can_save ?? value.canSave),
        canEnable: normalizeBooleanStateValue(value.can_enable ?? value.canEnable),
        message: normalizeStateValue(value.message) || (resolvedPath ? 'Current project is not a DataLad dataset.' : 'Load a project to see DataLad status.'),
        path: resolvedPath,
    };
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
            icon: normalizeStateValue(fromGlobalHelper && fromGlobalHelper.icon),
            datalad: normalizeDataladStateValue(
                fromGlobalHelper && fromGlobalHelper.datalad,
                normalizeStateValue(fromGlobalHelper && fromGlobalHelper.path)
            ),
        };
    }

    return {
        path: normalizeStateValue(window.currentProjectPath),
        name: normalizeStateValue(window.currentProjectName),
        icon: normalizeStateValue(window.currentProjectIcon),
        datalad: normalizeDataladStateValue(window.currentProjectDatalad, normalizeStateValue(window.currentProjectPath)),
    };
}

export function resolveCurrentProjectPath() {
    return normalizeStateValue(getProjectStateSnapshot().path);
}

export function resolveCurrentProjectName() {
    return normalizeStateValue(getProjectStateSnapshot().name);
}

export function resolveCurrentProjectIcon() {
    return normalizeStateValue(getProjectStateSnapshot().icon);
}

export function setProjectStateSnapshot(pathOrState, name, icon = '', datalad = undefined) {
    const nextStateInput = pathOrState && typeof pathOrState === 'object' && !Array.isArray(pathOrState)
        ? pathOrState
        : { path: pathOrState, name, icon, datalad };
    const nextPath = normalizeStateValue(nextStateInput.path);
    const nextState = {
        path: nextPath,
        name: normalizeStateValue(nextStateInput.name),
        icon: normalizeStateValue(nextStateInput.icon),
        datalad: normalizeDataladStateValue(nextStateInput.datalad, nextPath),
    };

    const stateStore = getProjectStateStore();
    if (stateStore && typeof stateStore.setState === 'function') {
        return stateStore.setState(nextState);
    }

    window.currentProjectPath = nextState.path;
    window.currentProjectName = nextState.name;
    window.currentProjectIcon = nextState.icon;
    window.currentProjectDatalad = nextState.datalad;
    return { ...nextState };
}
