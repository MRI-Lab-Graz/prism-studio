document.addEventListener('DOMContentLoaded', function() {
  const recipesRoot = document.getElementById('recipesRoot');

  function getFallbackApiOrigin() {
    const configuredOrigin = (window.PRISM_API_ORIGIN || '').trim();
    if (configuredOrigin) {
      return configuredOrigin.replace(/\/$/, '');
    }
    return 'http://127.0.0.1:5001';
  }

  function canRetryApiWithFallback(url) {
    const protocol = (window.location && window.location.protocol) ? window.location.protocol : '';
    const isRelativeApiRequest = typeof url === 'string' && url.startsWith('/api/');
    return isRelativeApiRequest && protocol !== 'http:' && protocol !== 'https:';
  }

  async function fetchWithApiFallback(
    url,
    options = {},
    fallbackMessage = 'Cannot reach PRISM backend API. Please restart PRISM Studio and try again.'
  ) {
    try {
      return await fetch(url, options);
    } catch (primaryError) {
      if (!canRetryApiWithFallback(url)) {
        throw primaryError;
      }

      const fallbackUrl = `${getFallbackApiOrigin()}${url}`;
      try {
        return await fetch(fallbackUrl, options);
      } catch (_fallbackError) {
        throw new Error(fallbackMessage);
      }
    }
  }

  function resolveProjectPath() {
    if (typeof window.resolveCurrentProjectPath === 'function') {
      const fromSharedResolver = window.resolveCurrentProjectPath();
      if (fromSharedResolver) return fromSharedResolver;
    }

    return (recipesRoot?.dataset?.currentProjectPath || '').trim();
  }

  let datasetPath = resolveProjectPath();
  let modalitiesRequestToken = 0;
  let sessionsRequestToken = 0;
  let preferencesLoadToken = 0;
  let recipeRunToken = 0;

  const derivFormat = document.getElementById('derivFormat');
  const derivSurvey = document.getElementById('derivSurvey');
  const derivSessionsAll = document.getElementById('derivSessionsAll');
  const derivSessions = document.getElementById('derivSessions');
  const derivRunBtn = document.getElementById('derivRunBtn');
  const derivError = document.getElementById('derivError');
  const derivInfo = document.getElementById('derivInfo');
  const derivTerminalContainer = document.getElementById('derivTerminalContainer');
  const derivTerminal = document.getElementById('derivTerminal');
  const derivClearLog = document.getElementById('derivClearLog');
  const derivRecipeDir = document.getElementById('derivRecipeDir');
  const derivModality = document.getElementById('derivModality');
  const derivLayout = document.getElementById('derivLayout');
  const derivLang = document.getElementById('derivLang');
  const derivIncludeRaw = document.getElementById('derivIncludeRaw');
  const derivMergeSeparate = document.getElementById('derivMergeSeparate');
  const derivMergeCombined = document.getElementById('derivMergeCombined');
  const derivAnonymize = document.getElementById('derivAnonymize');
  const derivMaskQuestions = document.getElementById('derivMaskQuestions');
  const derivIdLength = document.getElementById('derivIdLength');
  const derivRandomIds = document.getElementById('derivRandomIds');
  const derivSummaryContainer = document.getElementById('derivSummaryContainer');
  const derivSummaryBody = document.getElementById('derivSummaryBody');
  const derivToggleSummary = document.getElementById('derivToggleSummary');
  const derivProcessedCount = document.getElementById('derivProcessedCount');
  const derivWrittenCount = document.getElementById('derivWrittenCount');
  const derivOutputFormat = document.getElementById('derivOutputFormat');
  const derivOutputPath = document.getElementById('derivOutputPath');
  const derivRecipesUsed = document.getElementById('derivRecipesUsed');
  const derivBoilerplateInfo = document.getElementById('derivBoilerplateInfo');
  const derivBoilerplateLink = document.getElementById('derivBoilerplateLink');
  const derivProgressContainer = document.getElementById('derivProgressContainer');
  const derivProgressBar = document.getElementById('derivProgressBar');

  if (!derivFormat || !derivSurvey || !derivSessionsAll || !derivSessions || !derivRunBtn
    || !derivError || !derivInfo || !derivTerminalContainer || !derivTerminal || !derivClearLog
    || !derivLayout || !derivLang || !derivIncludeRaw || !derivMergeSeparate || !derivMergeCombined
    || !derivAnonymize || !derivMaskQuestions || !derivIdLength || !derivRandomIds
    || !derivSummaryContainer || !derivSummaryBody || !derivToggleSummary || !derivProcessedCount
    || !derivWrittenCount || !derivOutputFormat || !derivOutputPath || !derivRecipesUsed
    || !derivBoilerplateInfo || !derivBoilerplateLink || !derivProgressContainer || !derivProgressBar) {
    console.error('Recipes UI initialization failed: required DOM elements are missing.');
    return;
  }

  const defaultRecipesPreferences = {
    format: derivFormat.value,
    layout: derivLayout.value,
    lang: derivLang.value,
    include_raw: derivIncludeRaw.checked,
    merge_all: derivMergeCombined.checked,
    anonymize: derivAnonymize.checked,
    mask_questions: derivMaskQuestions.checked,
    id_length: derivIdLength.value,
    random_ids: derivRandomIds.checked,
  };

  function normalizeFormat(value) {
    const normalized = (value || '').toString().trim().toLowerCase();
    return normalized === 'save' ? 'sav' : normalized;
  }

  function normalizeNameList(values) {
    if (!Array.isArray(values)) return [];
    const unique = [];
    for (const value of values) {
      const token = String(value || '').trim();
      if (token && !unique.includes(token)) {
        unique.push(token);
      }
    }
    return unique;
  }

  function formatRecipesUsedSummary(data) {
    const details = (data && data.details) ? data.details : {};
    const used = normalizeNameList(details.written_surveys || data?.written_surveys);
    const missing = normalizeNameList(details.missing_surveys || data?.missing_surveys);
    const parts = [];

    if (used.length > 0) {
      parts.push(`Used: ${used.join(', ')}`);
    } else if (missing.length > 0) {
      parts.push('Used: none');
    } else {
      parts.push('No recipes found here');
    }

    if (missing.length > 0) {
      parts.push(`Skipped (no recipe found): ${missing.join(', ')}`);
    }

    if (data && data.recipe_source) {
      const sourceLabel = data.recipe_source === 'official' ? 'Official Library' : 'Project Recipes';
      parts.push(`Source: ${sourceLabel}`);
    }

    return parts.join(' | ');
  }

  function isProjectRequestCurrent(requestToken, activeToken, requestProjectPath) {
    return requestToken === activeToken && requestProjectPath === resolveProjectPath();
  }

  function isRecipeRunCurrent(runToken, requestProjectPath) {
    return runToken === recipeRunToken && requestProjectPath === resolveProjectPath();
  }

  function setRunAvailability() {
    derivRunBtn.disabled = !Boolean(datasetPath);
  }

  function setDefaultModalities() {
    derivModality.innerHTML = '';
    const defaultOption = document.createElement('option');
    defaultOption.value = 'survey';
    defaultOption.textContent = 'Survey';
    defaultOption.selected = true;
    derivModality.appendChild(defaultOption);
  }

  function renderSessionsPlaceholder(label) {
    derivSessions.innerHTML = '';
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = label;
    opt.selected = true;
    derivSessions.appendChild(opt);
  }

  function resetRecipesPreferenceControls() {
    derivFormat.value = normalizeFormat(defaultRecipesPreferences.format);
    derivLayout.value = defaultRecipesPreferences.layout;
    derivLang.value = defaultRecipesPreferences.lang;
    derivIncludeRaw.checked = defaultRecipesPreferences.include_raw;
    derivMergeSeparate.checked = !defaultRecipesPreferences.merge_all;
    derivMergeCombined.checked = defaultRecipesPreferences.merge_all;
    derivAnonymize.checked = defaultRecipesPreferences.anonymize;
    derivMaskQuestions.checked = defaultRecipesPreferences.mask_questions;
    derivIdLength.value = defaultRecipesPreferences.id_length;
    derivRandomIds.checked = defaultRecipesPreferences.random_ids;
  }

  function resetRecipesResultsState() {
    derivError.classList.add('d-none');
    derivInfo.classList.add('d-none');
    derivError.textContent = '';
    derivInfo.textContent = '';
    derivSummaryContainer.classList.add('d-none');
    derivProcessedCount.textContent = '0';
    derivWrittenCount.textContent = '0';
    derivOutputFormat.textContent = '-';
    derivOutputPath.textContent = '-';
    derivRecipesUsed.textContent = '-';
    derivBoilerplateInfo.classList.add('d-none');
    derivBoilerplateLink.removeAttribute('href');
    derivProgressContainer.classList.add('d-none');
    derivProgressBar.style.width = '0%';
    derivProgressBar.textContent = 'Initializing...';
    derivTerminal.innerHTML = '';
    derivTerminalContainer.classList.add('d-none');
  }

  function refreshModalities() {
    const requestProjectPath = resolveProjectPath();
    if (!requestProjectPath) {
      setDefaultModalities();
      return Promise.resolve();
    }

    const requestToken = ++modalitiesRequestToken;
    return fetchWithApiFallback(`/api/recipes-modalities?dataset_path=${encodeURIComponent(requestProjectPath)}`)
      .then(r => r.json())
      .then(data => {
        if (!isProjectRequestCurrent(requestToken, modalitiesRequestToken, requestProjectPath)) return;
        if (!data || !data.modalities || !derivModality) return;
        const current = derivModality.value;
        derivModality.innerHTML = '';
        for (const m of data.modalities) {
          const opt = document.createElement('option');
          opt.value = m.value;
          opt.textContent = m.label;
          if (m.value === current) opt.selected = true;
          derivModality.appendChild(opt);
        }
        if (!derivModality.value && data.default) {
          derivModality.value = data.default;
        }
      })
      .catch(err => {
        if (!isProjectRequestCurrent(requestToken, modalitiesRequestToken, requestProjectPath)) return;
        console.warn('Could not refresh analysis output modalities:', err);
        setDefaultModalities();
      });
  }

  // ---- Project preferences (remembered per-project) ----
  const RECIPES_PREF_KEYS = {
    format: 'derivFormat',
    layout: 'derivLayout',
    lang: 'derivLang',
    include_raw: 'derivIncludeRaw',
    merge_all: 'derivMergeCombined',
    anonymize: 'derivAnonymize',
    mask_questions: 'derivMaskQuestions',
    id_length: 'derivIdLength',
    random_ids: 'derivRandomIds',
  };

  function loadRecipesPreferences() {
    const requestProjectPath = resolveProjectPath();
    resetRecipesPreferenceControls();
    if (!requestProjectPath) return Promise.resolve();

    const requestToken = ++preferencesLoadToken;
    return fetchWithApiFallback(`/api/projects/preferences/recipes?project_path=${encodeURIComponent(requestProjectPath)}`)
      .then(r => r.json())
      .then(data => {
        if (!isProjectRequestCurrent(requestToken, preferencesLoadToken, requestProjectPath)) return;
        if (!data.success || !data.preferences) return;
        const prefs = data.preferences;
        // Apply saved preferences to form controls
        if (prefs.format && derivFormat) derivFormat.value = normalizeFormat(prefs.format);
        if (prefs.layout) derivLayout.value = prefs.layout;
        if (prefs.lang) derivLang.value = prefs.lang;
        if (typeof prefs.include_raw === 'boolean') derivIncludeRaw.checked = prefs.include_raw;
        if (typeof prefs.merge_all === 'boolean') {
          derivMergeSeparate.checked = !prefs.merge_all;
          derivMergeCombined.checked = prefs.merge_all;
        }
        if (typeof prefs.anonymize === 'boolean') derivAnonymize.checked = prefs.anonymize;
        if (typeof prefs.mask_questions === 'boolean') derivMaskQuestions.checked = prefs.mask_questions;
        if (typeof prefs.id_length === 'number') derivIdLength.value = prefs.id_length;
        if (typeof prefs.random_ids === 'boolean') derivRandomIds.checked = prefs.random_ids;
      })
      .catch(err => {
        if (!isProjectRequestCurrent(requestToken, preferencesLoadToken, requestProjectPath)) return;
        console.warn('Could not load recipes preferences:', err);
      });
  }

  function saveRecipesPreference(key, value) {
    const requestProjectPath = resolveProjectPath();
    if (!requestProjectPath) return;
    const prefs = {};
    prefs[key] = value;
    fetchWithApiFallback('/api/projects/preferences/recipes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: requestProjectPath, preferences: prefs }),
    }).catch(err => console.warn('Could not save recipes preference:', err));
  }

  // Wire up preference-saving on change
  function setupPreferenceSaving() {
    derivFormat?.addEventListener('change', () => saveRecipesPreference('format', derivFormat.value));
    derivLayout?.addEventListener('change', function() {
      saveRecipesPreference('layout', derivLayout.value);
    });
    derivLang?.addEventListener('change', function() {
      saveRecipesPreference('lang', derivLang.value);
    });
    derivIncludeRaw?.addEventListener('change', function() {
      saveRecipesPreference('include_raw', derivIncludeRaw.checked);
    });
    derivMergeSeparate?.addEventListener('change', function() {
      if (this.checked) saveRecipesPreference('merge_all', false);
    });
    derivMergeCombined?.addEventListener('change', function() {
      if (this.checked) saveRecipesPreference('merge_all', true);
    });
    derivAnonymize?.addEventListener('change', function() {
      saveRecipesPreference('anonymize', derivAnonymize.checked);
    });
    derivMaskQuestions?.addEventListener('change', function() {
      saveRecipesPreference('mask_questions', derivMaskQuestions.checked);
    });
    derivIdLength?.addEventListener('change', function() {
      saveRecipesPreference('id_length', parseInt(derivIdLength.value, 10) || 8);
    });
    derivRandomIds?.addEventListener('change', function() {
      saveRecipesPreference('random_ids', derivRandomIds.checked);
    });
  }
  setupPreferenceSaving();

  function logToTerminal(msg, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    let prefix = '';
    let color = 'text-light';
    if (type === 'error') { prefix = '❌ '; color = 'text-danger'; }
    else if (type === 'success') { prefix = '✅ '; color = 'text-success'; }
    else if (type === 'warning') { prefix = '⚠️ '; color = 'text-warning'; }
    else { prefix = '→ '; }
    const line = document.createElement('span');
    line.className = color;
    line.textContent = `[${timestamp}] ${prefix}${msg}\n`;
    derivTerminal.appendChild(line);
    derivTerminal.scrollTop = derivTerminal.scrollHeight;
    derivTerminalContainer.classList.remove('d-none');
  }

  derivClearLog.addEventListener('click', function() {
    derivTerminal.innerHTML = '';
    derivTerminalContainer.classList.add('d-none');
  });

  derivToggleSummary.addEventListener('click', function() {
    const icon = this.querySelector('i');
    const body = derivSummaryBody;
    if (body.style.display === 'none') {
      body.style.display = 'block';
      icon.className = 'fas fa-chevron-down';
    } else {
      body.style.display = 'none';
      icon.className = 'fas fa-chevron-up';
    }
  });

  function refreshSessions() {
    const requestProjectPath = resolveProjectPath();
    if (!requestProjectPath) {
      renderSessionsPlaceholder('No project loaded');
      derivSessions.disabled = true;
      return Promise.resolve();
    }

    const requestToken = ++sessionsRequestToken;
    return fetchWithApiFallback(`/api/recipes-sessions?dataset_path=${encodeURIComponent(requestProjectPath)}`)
      .then(r => r.json())
      .then(data => {
        if (!isProjectRequestCurrent(requestToken, sessionsRequestToken, requestProjectPath)) return;
        const sessions = (data && data.sessions) ? data.sessions : [];
        derivSessions.innerHTML = '';
        if (sessions.length === 0) {
          renderSessionsPlaceholder('No sessions found');
          derivSessions.disabled = true;
          return;
        }
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Select a session';
        placeholder.selected = true;
        derivSessions.appendChild(placeholder);
        for (const ses of sessions) {
          const opt = document.createElement('option');
          opt.value = ses;
          opt.textContent = ses;
          derivSessions.appendChild(opt);
        }
        derivSessions.disabled = derivSessionsAll.checked;
      })
      .catch(err => {
        if (!isProjectRequestCurrent(requestToken, sessionsRequestToken, requestProjectPath)) return;
        console.error('Failed to load sessions:', err);
        renderSessionsPlaceholder('Failed to load sessions');
        derivSessions.disabled = true;
      });
  }

  // Load sessions on page load
  setRunAvailability();
  refreshModalities();
  refreshSessions();
  loadRecipesPreferences();

  window.addEventListener('prism-project-changed', function() {
    datasetPath = resolveProjectPath();
    recipeRunToken += 1;
    resetRecipesResultsState();
    refreshModalities();
    refreshSessions();
    loadRecipesPreferences();
    setRunAvailability();
  });

  derivSessionsAll.addEventListener('change', function() {
    const all = derivSessionsAll.checked;
    derivSessions.disabled = all || !datasetPath || derivSessions.options.length <= 1;
  });
  function getSessionsFilter() {
    if (derivSessionsAll.checked) return '';
    const selected = (derivSessions.value || '').trim();
    return selected;
  }

  derivRunBtn.addEventListener('click', function() {
    runRecipeProcessing(false);
  });

  async function runRecipeProcessing(forceOverwrite) {
    derivError.classList.add('d-none');
    derivInfo.classList.add('d-none');
    derivError.textContent = '';
    derivInfo.textContent = '';
    derivSummaryContainer.classList.add('d-none');
    derivBoilerplateInfo.classList.add('d-none');

    const requestProjectPath = resolveProjectPath();
    datasetPath = requestProjectPath;
    setRunAvailability();

    if (!requestProjectPath) {
      derivError.textContent = 'No project loaded. Please select a project first.';
      derivError.classList.remove('d-none');
      logToTerminal('No project loaded', 'error');
      return;
    }

    const runToken = ++recipeRunToken;

    const payload = {
      dataset_path: requestProjectPath,
      modality: derivModality.value,
      format: derivFormat.value,
      survey: derivSurvey.value.trim(),
      sessions: getSessionsFilter(),
      lang: derivLang.value,
      layout: derivLayout.value,
      include_raw: derivIncludeRaw.checked,
      merge_all: derivMergeCombined.checked,
      anonymize: derivAnonymize.checked,
      mask_questions: derivMaskQuestions.checked,
      id_length: parseInt(derivIdLength.value, 10) || 8,
      random_ids: derivRandomIds.checked,
      force_overwrite: forceOverwrite,
      recipe_dir: derivRecipeDir ? derivRecipeDir.value.trim() : '',
    };

    derivRunBtn.disabled = true;
    if (!forceOverwrite) {
      logToTerminal(`Creating outputs for: ${requestProjectPath}`);
      logToTerminal(`Modality: ${payload.modality}, Format: ${payload.format}, Language: ${payload.lang}, Layout: ${payload.layout}`);
      if (payload.include_raw) logToTerminal(`Including raw data columns`);
      if (payload.anonymize) {
        logToTerminal(`🔒 Anonymizing participant IDs (length: ${payload.id_length}, ${payload.random_ids ? 'random' : 'deterministic'})`, 'warning');
        if (payload.mask_questions) logToTerminal(`🔒 Masking copyrighted question text`, 'warning');
      }
      if (payload.survey) logToTerminal(`Recipe filter: ${payload.survey}`);
      if (payload.sessions) logToTerminal(`Sessions filter: ${payload.sessions}`);
    } else {
      logToTerminal('Overwrite confirmed. Re-running output creation now...');
    }
    derivInfo.textContent = 'Creating outputs... this may take a moment.';
    derivInfo.classList.remove('d-none');
    derivProgressContainer.classList.remove('d-none');
    derivProgressBar.style.width = '10%';
    derivProgressBar.textContent = 'Starting...';

    try {
      const response = await fetchWithApiFallback('/api/recipes-surveys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!isRecipeRunCurrent(runToken, requestProjectPath)) return;

      derivProgressBar.style.width = '50%';
      derivProgressBar.textContent = 'Processing...';
      const data = await response.json().catch(() => null);

      if (!isRecipeRunCurrent(runToken, requestProjectPath)) return;

      if (!response.ok) {
        const msg = data && data.error ? data.error : 'Processing failed';
        throw new Error(msg);
      }

      derivProgressBar.style.width = '100%';
      derivProgressBar.textContent = 'Complete!';
      derivProgressContainer.classList.add('d-none');

      if (data && data.confirm_overwrite) {
        derivInfo.classList.add('d-none');
        const confirmMsg = `${data.message}\n\nDo you want to overwrite these files?`;
        logToTerminal(`Existing files found: ${data.existing_files.join(', ')}`, 'warning');
        if (confirm(confirmMsg)) {
          logToTerminal('User confirmed overwrite', 'info');
          runRecipeProcessing(true);
        } else {
          derivProgressContainer.classList.add('d-none');
          logToTerminal('Output creation cancelled by user', 'info');
          derivInfo.textContent = 'Output creation cancelled - existing files not overwritten.';
          derivInfo.classList.remove('d-none');
        }
        return;
      }

      const msg = data && data.message ? data.message : 'Done.';
      derivInfo.textContent = msg;
      derivInfo.classList.remove('d-none');
      logToTerminal(msg, 'success');

      if (data && data.details) {
        derivProcessedCount.textContent = data.details.processed_files || 0;
        derivWrittenCount.textContent = data.details.written_files || 0;
        derivOutputFormat.textContent = data.out_format ? normalizeFormat(data.out_format).toUpperCase() : '-';
        derivOutputPath.textContent = data.details.out_root || '-';
        derivRecipesUsed.textContent = formatRecipesUsedSummary(data);

        if (data.details.boilerplate_html_path) {
          derivBoilerplateLink.href = `/api/files/download?path=${encodeURIComponent(data.details.boilerplate_html_path)}`;
          derivBoilerplateInfo.classList.remove('d-none');
        } else {
          derivBoilerplateInfo.classList.add('d-none');
        }

        derivSummaryContainer.classList.remove('d-none');
      }

      if (data && data.validation_warning) {
        logToTerminal(data.validation_warning, 'warning');
      }

      if (data && data.missing_recipe_warning) {
        logToTerminal(data.missing_recipe_warning, 'warning');
      }

      if (data && data.recipe_source) {
        if (data.recipe_source === 'official') {
          logToTerminal('Recipes loaded from official library', 'info');
          if (data.recipes_seeded > 0) {
            logToTerminal(`Seeded ${data.recipes_seeded} recipe(s) into project/code/recipes/ for future runs`, 'info');
            refreshModalities();
          }
        } else {
          logToTerminal('Recipes loaded from project (code/recipes/)', 'info');
        }
      }

      if (data && data.out_format) {
        const formatLabel = normalizeFormat(data.out_format);
        logToTerminal(`Output format used: ${formatLabel}`);
      }
      if (payload.format === 'csv') {
        logToTerminal('CSV labels are in companion codebook files (*_codebook.json and *_codebook.tsv) in the output folder.');
      }
      if (data && data.nan_report) {
        logToTerminal('Columns with all n/a:', 'warning');
        for (const [key, cols] of Object.entries(data.nan_report)) {
          logToTerminal(`  - ${key}: ${cols.sort().join(', ')}`, 'warning');
        }
      }
      if (data && data.details) {
        logToTerminal(`Processed: ${data.details.processed_files || 0} files`);
        logToTerminal(`Written: ${data.details.written_files || 0} output files`);
        const writtenSurveys = Array.isArray(data.details.written_surveys) ? data.details.written_surveys : [];
        if (writtenSurveys.length > 0) {
          logToTerminal(`Written surveys: ${writtenSurveys.join(', ')}`);
        }
        if (data.details.out_root) logToTerminal(`Output: ${data.details.out_root}`);
      }
    } catch (err) {
      if (!isRecipeRunCurrent(runToken, requestProjectPath)) return;
      derivProgressContainer.classList.add('d-none');
      derivError.textContent = err.message;
      derivError.classList.remove('d-none');
      logToTerminal(err.message, 'error');
    } finally {
      if (isRecipeRunCurrent(runToken, requestProjectPath)) {
        setRunAvailability();
      }
    }
  }
});
