/** Short texts for the green chips of structured entries (pure, unit tested).
 *  The stored values stay the serialized strings the hidden fields already use. */
import { MISSING_FILE_REASON_OPTIONS, parseMissingFilesValue } from './missing-files-row.js';

/** "file | issue" -> "file – issue". */
export const knownIssueChipText = (value) => String(value).split('|').map((p) => p.trim()).filter(Boolean).join(' – ');

/** "sub | ses | modality | reason | detail" -> "sub · ses · modality · Reason (detail)". */
export function missingFilesChipText(line) {
    const [row] = parseMissingFilesValue(line);
    if (!row) return '';
    const reason = MISSING_FILE_REASON_OPTIONS.find((o) => o.value && o.value === row.reason)?.label || row.reason;
    const parts = [row.subject, row.session, row.modality, reason].filter(Boolean);
    const text = parts.join(' · ');
    return row.detail ? `${text} (${row.detail})` : text;
}

const num = (n) => String(n);

/** One Checked Criterion as a chip text: "Age · include 18–35 years". */
export function criterionSummary(c) {
    if (c.type === 'categorical') return `${c.label} · ${c.mode} ${(c.values || []).join(', ')}`;
    const hasMin = c.min !== undefined && c.min !== '';
    const hasMax = c.max !== undefined && c.max !== '';
    let range;
    if (hasMin && hasMax) range = `${num(c.min)}–${num(c.max)}`;
    else if (hasMin) range = `≥ ${num(c.min)}`;
    else range = `≤ ${num(c.max)}`;
    return `${c.label} · ${c.mode} ${range}${c.unit ? ` ${c.unit}` : ''}`;
}
