import { describe, expect, it } from 'vitest';

import { createStudyMetadataLoadController } from './metadata-load.js';
import { isSameProjectPath } from '../../shared/project-state.js';

/**
 * Builds a controller with every collaborator faked, so the load lifecycle can
 * be exercised without a DOM. `overrides` lets a test slow down or fail one
 * step to reproduce a race.
 */
function buildController(overrides = {}) {
    const calls = { formLocked: [], applied: 0 };
    let token = 0;

    const controller = createStudyMetadataLoadController({
        getCurrentProjectPath: () => '/tmp/project',
        getSubmitInFlight: () => false,
        getFormSnapshot: () => 'snapshot',
        incrementMetadataLoadToken: () => ++token,
        isProjectRequestCurrent: () => true,
        onLoadStateChanged: () => {},
        beforeLoad: async () => {},
        fetchStudyMetadata: async () => ({ json: async () => ({ success: true }) }),
        applyStudyMetadataPayload: () => { calls.applied += 1; },
        refreshStatusSnapshots: async () => {},
        setLoadErrorStatus: () => {},
        clearLoadStatus: () => {},
        setFormLocked: (locked) => calls.formLocked.push(locked),
        ...overrides,
    });

    return { controller, calls };
}

describe('study metadata load lifecycle', () => {
    it('locks the form before fetching and unlocks it after a successful load', async () => {
        const { controller, calls } = buildController();

        await controller.loadStudyMetadata();

        expect(calls.formLocked).toEqual([true, false]);
        expect(calls.applied).toBe(1);
    });

    it('locks the form before the first fetch is even issued', async () => {
        // The card is already visible at this point, so anything typed between
        // "form shown" and "payload applied" would be silently overwritten.
        let lockedWhenFetchStarted = null;
        const { controller, calls } = buildController({
            fetchStudyMetadata: async () => {
                lockedWhenFetchStarted = calls.formLocked[calls.formLocked.length - 1];
                return { json: async () => ({ success: true }) };
            },
        });

        await controller.loadStudyMetadata();

        expect(lockedWhenFetchStarted).toBe(true);
    });

    it('keeps the form locked when the load fails', async () => {
        // An unpopulated form must not be savable: it would write blanks over
        // the stored metadata.
        const { controller, calls } = buildController({
            fetchStudyMetadata: async () => { throw new Error('network down'); },
        });

        await controller.loadStudyMetadata();

        expect(calls.formLocked).toEqual([true]);
        expect(controller.isReadyForCurrentProject()).toBe(false);
    });

    it('keeps the form locked when the server reports failure', async () => {
        const { controller, calls } = buildController({
            fetchStudyMetadata: async () => ({ json: async () => ({ success: false }) }),
        });

        await controller.loadStudyMetadata();

        expect(calls.formLocked).toEqual([true]);
        expect(calls.applied).toBe(0);
    });

    it('never locks the form when there is no project to load', async () => {
        const { controller, calls } = buildController({
            getCurrentProjectPath: () => '',
        });

        await controller.loadStudyMetadata();

        expect(calls.formLocked).toEqual([]);
    });

    it('leaves the lock to the newer request when a load is superseded', async () => {
        const { controller, calls } = buildController({
            isProjectRequestCurrent: () => false,
        });

        await controller.loadStudyMetadata();

        expect(calls.formLocked).toEqual([true]);
    });

    it('still unlocks when the project path changes separator spelling mid-load', async () => {
        // Windows regression: the server answers /api/projects/current with
        // str(Path(...)) - the backslash spelling - which the navbar store
        // writes back over the forward-slash spelling the page started with.
        // That fired a project-state event mid-load, and because the unlock is
        // gated on "is this still the current project", a raw string compare
        // left the form inert forever: every field gray and non-editable, with
        // the sync/citation rows stuck on "pending...".
        let currentPath = 'C:/Users/karl/proj';
        const { controller, calls } = buildController({
            getCurrentProjectPath: () => currentPath,
            isProjectRequestCurrent: (path) => isSameProjectPath(path, currentPath),
            fetchStudyMetadata: async () => {
                currentPath = 'C:\\Users\\karl\\proj';
                return { json: async () => ({ success: true }) };
            },
        });

        await controller.loadStudyMetadata();

        expect(calls.formLocked).toEqual([true, false]);
        expect(controller.isReadyForCurrentProject()).toBe(true);
    });
});
