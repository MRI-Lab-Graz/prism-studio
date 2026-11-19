/* Studio theme: the shared parts every page uses (see CLAUDE.md, "One theme for every page").
   The Jinja macros in includes/ui/macros.html emit the same markup; tests/test_studio_theme_parity.py enforces it. */
(function (root) {
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&#34;').replace(/'/g, '&#39;');

  const TIERS = {
    required: ['bg-danger', 'REQUIRED'],
    core: ['badge-tier-core', 'CORE'],
    optional: ['bg-secondary', 'OPTIONAL'],
    // required in a project, open (neither missing nor filled) in a library template
    project: ['badge-tier-project', 'PROJECT'],
  };
  const PROJECT_TIP = 'Set when the questionnaire is used in a project';

  // Field heading: tier badge, label text, hover tip. All parts but the text are optional.
  function fieldLabelHtml({ text, tier, tip }) {
    const t = TIERS[tier];
    return '<label class="form-label studio-field-label">'
      + (t ? `<span class="badge ${t[0]}"${tier === 'project' ? ` title="${PROJECT_TIP}"` : ''}>${t[1]}</span> ` : '')
      + esc(text)
      + (tip ? ` <span class="info-tip text-muted" data-bs-toggle="tooltip" title="${esc(tip)}">&#9432;</span>` : '')
      + '</label>';
  }

  // The colour of a field's tier badge: green once the field is filled, its tier colour while it is empty.
  function tierBadgeClass(label, filled) {
    if (filled) return 'bg-success';
    const tier = Object.values(TIERS).find((t) => t[1] === label);
    return tier ? tier[0] : '';
  }

  // Recolour a rendered tier badge (the project page's rule, kept here so every page uses the one).
  // `projectOpen`: the field is required only in a project and still empty here: the neutral PROJECT state.
  function setFilled(badge, filled, projectOpen = false) {
    const was = badge.textContent.trim();
    const label = projectOpen ? 'PROJECT' : (was === 'PROJECT' ? 'REQUIRED' : was);
    if (label !== was) badge.textContent = label;
    if (projectOpen) badge.setAttribute('title', PROJECT_TIP);
    else if (was === 'PROJECT') badge.removeAttribute('title');
    badge.classList.remove('bg-success', ...Object.values(TIERS).map((t) => t[0]));
    const cls = tierBadgeClass(label, filled && !projectOpen);
    if (cls) badge.classList.add(cls);
  }

  // The one "not filled in" rule (same as the backend's is_blank).
  function isBlank(v) {
    if (v === undefined || v === null) return true;
    if (typeof v === 'string') return !v.trim();
    if (Array.isArray(v)) return v.length === 0;
    if (typeof v === 'object') return isBlank(v.en);
    return false;
  }

  // Paint the REQUIRED badge of a rendered field (direct label child) from its value: green filled, red blank.
  function paintRequired(fieldEl, value) {
    const tier = fieldEl.querySelector(':scope > .studio-field-label > .badge');
    if (tier && tier.textContent.trim() === 'REQUIRED') setFilled(tier, !isBlank(value));
  }

  // Required/Core/FAIR counts, each [filled, total] or [filled, total, title]; a total of 0 is not shown.
  // `project` ([filled, total]) counts the fields only a project needs: neutral until all are filled.
  function tally({ required, core, fair, project }) {
    const badge = (label, c, openClass) => (c && c[1] > 0)
      ? `<span class="badge ${c[0] === c[1] ? 'bg-success' : openClass} bg-opacity-75"${c[2] ? ` title="${esc(c[2])}"` : ''}>${label} ${c[0]}/${c[1]}</span>`
      : '';
    return badge('Required', required, 'bg-danger')
      + badge('Project', project, 'badge-tier-project')
      + badge('Core', core, 'badge-tier-core')
      + badge('FAIR', fair, 'bg-warning text-dark');
  }

  // Descriptive fields are English only (a stored translation object still displays; only the offer to add or convert a language goes).
  // Instructions, OriginalName, items and Levels stay free: they are the instrument's own text.
  const ENGLISH_ONLY = {
    Study: ['ShortName', 'Description', 'Construct', 'Reliability', 'Validity', 'Norming', 'Notes', 'PermissionsNote', 'Keywords', 'Citation', 'LicenseTerms', 'RecallPeriod',
      'ExclusionCriteria', 'TargetPopulation', 'WarmupProtocol'],
    Technical: ['Equipment'],
    Scoring: ['ScoringMethod', 'CutoffsSource', 'NormsSource'],
    Normative: ['ReferencePopulation', 'ReferenceSource'],
  };
  // Outside surveys the item-level Description describes a column (metadata); in a survey an item is the instrument's own text.
  const offersMultilingual = (sectionKey, fieldName, modality = 'survey') =>
    !(ENGLISH_ONLY[sectionKey] || []).includes(fieldName) && !(sectionKey === 'ITEM' && fieldName === 'Description' && modality !== 'survey');

  // Long text (a citation, a description): a full-width text area that grows with its text, never a one-line input.
  // It starts at 6 rows (a citation 4), grows to 25 rows and scrolls inside the box from there.
  const LONG_TEXT = ['Citation', 'Description', 'Reliability', 'Validity', 'Norming', 'Notes', 'PermissionsNote', 'Construct']
    .map((f) => `Study/${f}`).concat('Study/References/Citation');
  const MAX_ROWS = 25;
  const isLongText = (path) => LONG_TEXT.includes(path); // a field path like "Study/Citation", not a bare name
  const LONG_TEXT_ROWS = { 'Study/Construct': 2, 'Study/PermissionsNote': 3 };
  const longTextRows = (path) => LONG_TEXT_ROWS[path] || (/Citation$/.test(path) ? 4 : 6);

  function autoGrow(ta, maxHeight = Infinity) {
    ta.style.height = 'auto';
    const h = ta.scrollHeight;
    ta.style.height = `${Math.min(h, maxHeight)}px`;
    ta.style.overflowY = h > maxHeight ? 'auto' : 'hidden';
  }

  function longText(value, onInput, placeholder, path = '') {
    const ta = document.createElement('textarea');
    ta.className = 'form-control studio-long-text';
    ta.rows = longTextRows(path);
    ta.style.width = '100%';
    ta.style.minWidth = '0';
    ta.style.resize = 'vertical';
    ta.value = value;
    if (placeholder) ta.placeholder = placeholder;
    const grow = () => {
      const cs = typeof getComputedStyle === 'function' ? getComputedStyle(ta) : null;
      const line = (cs && parseFloat(cs.lineHeight)) || 24;
      const pad = cs ? (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0) + (parseFloat(cs.borderTopWidth) || 0) + (parseFloat(cs.borderBottomWidth) || 0) : 0;
      autoGrow(ta, line * MAX_ROWS + pad);
    };
    ta.addEventListener('input', () => { grow(); onInput(ta.value); });
    // a hidden section has no height yet: grow when it gets a width
    if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => { if (ta.offsetWidth) grow(); }).observe(ta);
    return ta;
  }

  const api = {
    offersMultilingual,
    isLongText,
    longTextRows,
    autoGrow,
    longText,
    fieldLabelHtml,
    tierBadgeClass,
    setFilled,
    isBlank,
    paintRequired,
    tally,
    fieldLabel(opts) {
      const tpl = document.createElement('template');
      tpl.innerHTML = fieldLabelHtml(opts);
      return tpl.content.firstElementChild;
    },
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.StudioTheme = api;
})(typeof window !== 'undefined' ? window : globalThis);
