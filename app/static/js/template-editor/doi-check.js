/** DOI check of the template editor: the same /api/projects/lookup-doi route and wording as the project page. */
const UNREACHABLE = { cls: 'text-muted', text: 'Could not check DOI online (offline?).' };

/** Lookup result -> {cls, text} for the feedback line; "could not be checked" is never "wrong". */
export function doiMessage(result) {
  if (result.status === 'ok') return { cls: 'text-success', text: result.citation || result.doi };
  if (result.status === 'not_found') return { cls: 'text-danger', text: 'DOI not found (Crossref, DataCite).' };
  if (result.status === 'invalid') return { cls: 'text-danger', text: 'Not a valid DOI.' };
  return UNREACHABLE;
}

/** The message for a typed DOI; null when it is empty (nothing to check). */
export async function checkDoi(value, fetchFn = fetch) {
  if (!String(value ?? '').trim()) return null;
  try {
    const res = await fetchFn(`/api/projects/lookup-doi?doi=${encodeURIComponent(value)}`);
    return doiMessage(await res.json());
  } catch (err) { return UNREACHABLE; }
}

/** Check on change (blur), not on every keystroke; the result shows in a line below the input. */
export function attachDoiCheck(input, fetchFn = fetch) {
  const line = document.createElement('div');
  line.className = 'form-text';
  input.addEventListener('change', async () => {
    const msg = await checkDoi(input.value, fetchFn);
    line.className = `form-text ${msg ? msg.cls : ''}`;
    line.textContent = msg ? msg.text : '';
  });
  return line;
}
