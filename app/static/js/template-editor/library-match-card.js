export function libraryMatchSummary(match) {
  if (!match) {
    return '';
  }
  return `match: ${match.template_key} (${match.source}, ${match.confidence})`;
}

export function renderLibraryMatchCard(match, escapeHtml) {
  if (!match) {
    return '';
  }
  const wording = match.reworded.length === 0 ? 'wording identical' : `${match.reworded.length} item(s) reworded`;
  const levels = match.levels_ok ? 'levels identical' : 'levels differ';
  const ids = match.ids_identical ? 'item IDs identical' : 'item IDs differ';
  const notes = [];
  if (match.unpaired_imported.length) {
    notes.push(`${match.unpaired_imported.length} imported item(s) without a match`);
  }
  if (match.unpaired_library.length) {
    notes.push(`${match.unpaired_library.length} library item(s) not in your survey`);
  }
  if (match.ids_conflict) {
    notes.push('an imported ID is already used by a different library item');
  }
  const changed = Object.entries(match.id_map).filter(([imported, library]) => imported !== library);
  const rows = changed
    .map(([imported, library]) => `<tr><td><code>${escapeHtml(imported)}</code></td><td><code>${escapeHtml(library)}</code></td></tr>`)
    .join('');
  const table = rows
    ? `<details class="mt-1"><summary>Item ID mapping (${changed.length})</summary>`
      + `<table class="table table-sm mb-0"><thead><tr><th>Your survey</th><th>Library</th></tr></thead><tbody>${rows}</tbody></table></details>`
    : '';
  const useButton = match.adoptable
    ? '<button type="button" class="btn btn-sm btn-success me-1" data-action="use-library">Use library template</button>'
    : '';
  return `<div class="lib-match-title fw-semibold">Library match: ${escapeHtml(match.template_key)} (${escapeHtml(match.source)}, ${escapeHtml(match.confidence)})</div>`
    + `<div>${match.paired}/${match.imported_items} items paired &middot; ${wording} &middot; ${levels} &middot; ${ids}</div>`
    + (notes.length ? `<div>${notes.map(escapeHtml).join(' &middot; ')}</div>` : '')
    + table
    + `<div class="mt-2">${useButton}<button type="button" class="btn btn-sm btn-outline-secondary" data-action="import-new">Import as new</button></div>`;
}
