// HTML builders for the survey version wizard. Everything interpolated here comes
// from template JSON or the user's data files, so it is always escaped.
import { escapeHtml } from '../../shared/dom.js';

export function buildVariantDefinitionBadges(variantDefinitions, selectedVersion) {
    if (!Array.isArray(variantDefinitions) || variantDefinitions.length === 0) {
        return '';
    }

    return variantDefinitions
        .map((entry) => {
            if (!entry || typeof entry !== 'object') return '';
            const variantId = String(entry.VariantID || '').trim();
            if (!variantId) return '';
            const itemCount = entry.ItemCount ? `, ${entry.ItemCount} items` : '';
            const scaleType = entry.ScaleType ? `, ${entry.ScaleType}` : '';
            const badgeClass = variantId === selectedVersion
                ? 'survey-version-variant-badge survey-version-variant-badge-active'
                : 'survey-version-variant-badge';
            return `<span class="badge ${badgeClass}">${escapeHtml(`${variantId}${itemCount}${scaleType}`)}</span>`;
        })
        .filter(Boolean)
        .join(' ');
}

export function buildVersionOptions(versions, selectedVersion) {
    return versions
        .map((version) => {
            const safe = escapeHtml(version);
            return `<option value="${safe}"${version === selectedVersion ? ' selected' : ''}>${safe}</option>`;
        })
        .join('');
}
