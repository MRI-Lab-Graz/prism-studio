document.addEventListener('DOMContentLoaded', function() {
  const recipesRoot = document.getElementById('recipesRoot');
  function resolveProjectPath() {
    if (typeof window.resolveCurrentProjectPath === 'function') {
      const fromSharedResolver = window.resolveCurrentProjectPath();
      if (fromSharedResolver) return fromSharedResolver;
    }

    return (recipesRoot?.dataset?.currentProjectPath || '').trim();
  }

  let datasetPath = resolveProjectPath();
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
    || !derivSummaryContainer || !derivSummaryBody || !derivToggleSummary || !derivProcessedCount
    || !derivWrittenCount || !derivOutputFormat || !derivOutputPath || !derivRecipesUsed
    || !derivBoilerplateInfo || !derivBoilerplateLink || !derivProgressContainer || !derivProgressBar) {
    console.error('Recipes UI initialization failed: required DOM elements are missing.');
    return;
  }

  function refreshModalities() {
    if (!datasetPath) return;
    fetch(`/api/recipes-modalities?dataset_path=${encodeURIComponent(datasetPath)}`)
      .then(r => r.json())
      .then(data => {
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
  }

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
    if (!datasetPath) {
      derivSessions.innerHTML = '';
      derivSessions.disabled = true;
      return;
    }
    fetch(`/api/recipes-sessions?dataset_path=${encodeURIComponent(datasetPath)}`)
      .then(r => r.json())
      .then(data => {
        const sessions = (data && data.sessions) ? data.sessions : [];
        derivSessions.innerHTML = '';
        if (sessions.length === 0) {
          const opt = document.createElement('option');
          opt.value = '';
          opt.textContent = 'No sessions found';
          derivSessions.appendChild(opt);
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
      })
      .catch(err => {
        console.error('Failed to load sessions:', err);
        derivSessions.innerHTML = '';
      });
  }

  // Load sessions on page load
  refreshSessions();

  window.addEventListener('prism-project-changed', function() {
    datasetPath = resolveProjectPath();
    refreshSessions();
  });

  derivSessionsAll.addEventListener('change', function() {
    const all = derivSessionsAll.checked;
    derivSessions.disabled = all;
  });
  function getSessionsFilter() {
    if (derivSessionsAll.checked) return '';
    const selected = (derivSessions.value || '').trim();
    return selected;
  }

  derivRunBtn.addEventListener('click', function() {
    runRecipeProcessing(false);
  });

  function runRecipeProcessing(forceOverwrite) {
    derivError.classList.add('d-none');
    derivInfo.classList.add('d-none');
    derivError.textContent = '';
    derivInfo.textContent = '';

    if (!datasetPath) {
      derivError.textContent = 'No project loaded. Please select a project first.';
      derivError.classList.remove('d-none');
      logToTerminal('No project loaded', 'error');
      return;
    }

    const payload = {
      dataset_path: datasetPath,
      modality: document.getElementById('derivModality').value,
      format: derivFormat.value,
      survey: derivSurvey.value.trim(),
      sessions: getSessionsFilter(),
      lang: document.getElementById('derivLang').value,
      layout: document.getElementById('derivLayout').value,
      include_raw: document.getElementById('derivIncludeRaw').checked,
      merge_all: document.getElementById('derivMergeCombined').checked,
      anonymize: document.getElementById('derivAnonymize').checked,
      mask_questions: document.getElementById('derivMaskQuestions').checked,
      id_length: parseInt(document.getElementById('derivIdLength').value) || 8,
      random_ids: document.getElementById('derivRandomIds').checked,
      force_overwrite: forceOverwrite,
      recipe_dir: derivRecipeDir ? derivRecipeDir.value.trim() : '',
    };

    derivRunBtn.disabled = true;
    if (!forceOverwrite) {
      logToTerminal(`Running processing on: ${datasetPath}`);
      logToTerminal(`Modality: ${payload.modality}, Format: ${payload.format}, Language: ${payload.lang}, Layout: ${payload.layout}`);
      if (payload.include_raw) logToTerminal(`Including raw data columns`);
      if (payload.anonymize) {
        logToTerminal(`🔒 Anonymizing participant IDs (length: ${payload.id_length}, ${payload.random_ids ? 'random' : 'deterministic'})`, 'warning');
        if (payload.mask_questions) logToTerminal(`🔒 Masking copyrighted question text`, 'warning');
      }
      if (payload.survey) logToTerminal(`Recipe filter: ${payload.survey}`);
      if (payload.sessions) logToTerminal(`Sessions filter: ${payload.sessions}`);
    } else {
      logToTerminal('Overwrite confirmed. Re-running processing now...');
    }
    derivInfo.textContent = 'Running processing... this may take a moment.';
    derivInfo.classList.remove('d-none');
    derivProgressContainer.classList.remove('d-none');
    derivProgressBar.style.width = '10%';
    derivProgressBar.textContent = 'Starting...';

    fetch('/api/recipes-surveys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(async response => {
        derivProgressBar.style.width = '50%';
        derivProgressBar.textContent = 'Processing...';
        const data = await response.json().catch(() => null);
        if (!response.ok) {
          const msg = data && data.error ? data.error : 'Processing failed';
          throw new Error(msg);
        }
        return data;
      })
      .then(data => {
        derivProgressBar.style.width = '100%';
        derivProgressBar.textContent = 'Complete!';
        derivProgressContainer.classList.add('d-none');
        
        // Check if we need to confirm overwrite
        if (data && data.confirm_overwrite) {
          derivInfo.classList.add('d-none');
          const confirmMsg = `${data.message}\n\nDo you want to overwrite these files?`;
          logToTerminal(`Existing files found: ${data.existing_files.join(', ')}`, 'warning');
          if (confirm(confirmMsg)) {
            logToTerminal('User confirmed overwrite', 'info');
            runRecipeProcessing(true);
          } else {
            derivProgressContainer.classList.add('d-none');
            logToTerminal('Processing cancelled by user', 'info');
            derivInfo.textContent = 'Processing cancelled - existing files not overwritten.';
            derivInfo.classList.remove('d-none');
            derivRunBtn.disabled = false;
          }
          return;
        }
        
        const msg = data && data.message ? data.message : 'Done.';
        derivInfo.textContent = msg;
        derivInfo.classList.remove('d-none');
        logToTerminal(msg, 'success');
        
        // Populate summary
        if (data && data.details) {
          derivProcessedCount.textContent = data.details.processed_files || 0;
          derivWrittenCount.textContent = data.details.written_files || 0;
          derivOutputFormat.textContent = data.out_format ? (data.out_format === 'save' ? 'SAV' : data.out_format.toUpperCase()) : '-';
          derivOutputPath.textContent = data.details.out_root || '-';
          
          if (data.recipe_source) {
            derivRecipesUsed.textContent = data.recipe_source === 'official' ? 'Official Library' : 'Project Recipes';
          } else {
            derivRecipesUsed.textContent = '-';
          }
          
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

        // Recipe source info (Gap 5)
        if (data && data.recipe_source) {
          if (data.recipe_source === 'official') {
            logToTerminal('Recipes loaded from official library', 'info');
            if (data.recipes_seeded > 0) {
              logToTerminal(`Seeded ${data.recipes_seeded} recipe(s) into project/code/recipes/ for future runs`, 'info');
              // Refresh modality dropdown now project has local recipes (Gap 6)
              refreshModalities();
            }
          } else {
            logToTerminal('Recipes loaded from project (code/recipes/)', 'info');
          }
        }

        if (data && data.out_format) {
          const formatLabel = data.out_format === 'save' ? 'sav' : data.out_format;
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
          if (data.details.out_root) logToTerminal(`Output: ${data.details.out_root}`);
        }
        derivRunBtn.disabled = false;
      })
      .catch(err => {
        derivProgressContainer.classList.add('d-none');
        derivError.textContent = err.message;
        derivError.classList.remove('d-none');
        logToTerminal(err.message, 'error');
        derivRunBtn.disabled = false;
      });
  }
});
