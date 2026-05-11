export function parseNumericOffsetValue(rawValue) {
    if (rawValue === null || rawValue === undefined) {
        return null;
    }
    const normalized = String(rawValue).trim().replace(',', '.');
    if (!normalized) {
        return null;
    }
    const parsed = Number(normalized);
    if (!Number.isFinite(parsed)) {
        return null;
    }
    return parsed;
}

export function formatSignedOffset(offset) {
    const numeric = Number(offset);
    if (!Number.isFinite(numeric)) {
        return String(offset);
    }
    const rounded = Number.isInteger(numeric)
        ? String(numeric)
        : numeric.toFixed(6).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
    return `${numeric >= 0 ? '+' : ''}${rounded}`;
}

export function formatOffsetMagnitude(offset) {
    const numeric = Math.abs(Number(offset));
    if (!Number.isFinite(numeric)) {
        return '';
    }
    return Number.isInteger(numeric)
        ? String(numeric)
        : numeric.toFixed(6).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
}

export function normalizeTaskValueOffsets(offsetMap, normalizeTaskName) {
    if (!offsetMap || typeof offsetMap !== 'object') {
        return {};
    }

    const normalizeTask = typeof normalizeTaskName === 'function'
        ? normalizeTaskName
        : (value) => String(value || '').trim();

    const normalized = {};
    Object.entries(offsetMap).forEach(([rawTask, rawOffset]) => {
        const task = normalizeTask(rawTask);
        const parsedOffset = parseNumericOffsetValue(rawOffset);
        if (!task || parsedOffset === null) {
            return;
        }
        normalized[task] = parsedOffset;
    });
    return normalized;
}

export function parseTaskValueOffsetsText(rawText, normalizeTaskName) {
    const normalizeTask = typeof normalizeTaskName === 'function'
        ? normalizeTaskName
        : (value) => String(value || '').trim();
    const normalized = {};
    const lines = String(rawText || '').split(/\r?\n/);

    lines.forEach((rawLine, index) => {
        const line = String(rawLine || '').trim();
        if (!line || line.startsWith('#')) {
            return;
        }

        const match = line.match(/^([^:=]+?)\s*[:=]\s*(.+)$/);
        if (!match) {
            throw new Error(`Invalid task value offset on line ${index + 1}. Use "task = offset".`);
        }

        const task = normalizeTask(match[1]);
        const offset = parseNumericOffsetValue(match[2]);
        if (!task) {
            throw new Error(`Missing task name on line ${index + 1}.`);
        }
        if (task === '*') {
            throw new Error('Use a specific survey task name for manual offsets. Wildcard offsets are disabled in Advanced options.');
        }
        if (offset === null) {
            throw new Error(`Invalid numeric offset on line ${index + 1}.`);
        }

        normalized[task] = offset;
    });

    return normalized;
}

export function collectSuggestedValueOffsets(payload) {
    if (!Array.isArray(payload && payload.suggested_offsets)) {
        return [];
    }
    const deduped = [];
    const seen = new Set();
    payload.suggested_offsets.forEach((entry) => {
        const parsed = parseNumericOffsetValue(entry);
        if (parsed === null) {
            return;
        }
        const key = parsed.toFixed(6);
        if (seen.has(key)) {
            return;
        }
        seen.add(key);
        deduped.push(parsed);
    });
    return deduped;
}
