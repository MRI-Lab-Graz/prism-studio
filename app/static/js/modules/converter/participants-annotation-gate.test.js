import { describe, expect, it } from 'vitest';

import { createAnnotationGate } from './participants-annotation-gate.js';

describe('participants annotation gate', () => {
    it('starts unconfirmed so Create/Replace stays blocked after a preview', () => {
        expect(createAnnotationGate().isConfirmed()).toBe(false);
    });

    it('confirm unblocks, reset (new preview, changed columns, new file) blocks again', () => {
        const gate = createAnnotationGate();
        gate.confirm();
        expect(gate.isConfirmed()).toBe(true);
        gate.reset();
        expect(gate.isConfirmed()).toBe(false);
    });
});
