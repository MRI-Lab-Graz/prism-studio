document.addEventListener('DOMContentLoaded', function() {
  const recipesRoot = document.getElementById('recipesRoot');
  // Resolve project path from global first, then template data attribute fallback
  const datasetPath = (
    (typeof window.currentProjectPath === 'string' && window.currentProjectPath.trim())
    || (recipesRoot?.dataset?.currentProjectPath || '').trim()
  );
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

  if (!derivFormat || !derivSurvey || !derivSessionsAll || !derivSessions || !derivRunBtn
    || !derivError || !derivInfo || !derivTerminalContainer || !derivTerminal || !derivClearLog) {
    console.error('Recipes UI initialization failed: required DOM elements are missing.');
    return;
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
        for (const ses of sessions) {
          const opt = document.createElement('option');
          opt.value = ses;
          opt.textContent = ses;
          derivSessions.appendChild(opt);
        }
      })
      .catch(() => {
        derivSessions.innerHTML = '';
      });
  }

  // Load sessions on page load
  refreshSessions();

  derivSessionsAll.addEventListener('change', function() {
    const all = derivSessionsAll.checked;
    derivSessions.disabled = all;
  });
  function getSessionsFilter() {
    if (derivSessionsAll.checked) return '';
    const selected = Array.from(derivSessions.selectedOptions)
      .map(opt => opt.value)
      .filter(Boolean);
    return selected.join(',');
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
      boilerplate: document.getElementById('derivBoilerplate').checked,
      merge_all: document.getElementById('derivMergeCombined').checked,
      anonymize: document.getElementById('derivAnonymize').checked,
      mask_questions: document.getElementById('derivMaskQuestions').checked,
      id_length: parseInt(document.getElementById('derivIdLength').value) || 8,
      random_ids: document.getElementById('derivRandomIds').checked,
      force_overwrite: forceOverwrite
    };

    derivRunBtn.disabled = true;
    if (!forceOverwrite) {
      logToTerminal(`Running processing on: ${datasetPath}`);
      logToTerminal(`Modality: ${payload.modality}, Format: ${payload.format}, Language: ${payload.lang}, Layout: ${payload.layout}`);
      if (payload.include_raw) logToTerminal(`Including raw data columns`);
      if (payload.boilerplate) logToTerminal(`Generating methods boilerplate`);
      if (payload.anonymize) {
        logToTerminal(`🔒 Anonymizing participant IDs (length: ${payload.id_length}, ${payload.random_ids ? 'random' : 'deterministic'})`, 'warning');
        if (payload.mask_questions) logToTerminal(`🔒 Masking copyrighted question text`, 'warning');
      }
      if (payload.survey) logToTerminal(`Recipe filter: ${payload.survey}`);
      if (payload.sessions) logToTerminal(`Sessions filter: ${payload.sessions}`);
    }
    derivInfo.textContent = 'Running processing... this may take a moment.';
    derivInfo.classList.remove('d-none');

    fetch('/api/recipes-surveys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(async response => {
        const data = await response.json().catch(() => null);
        if (!response.ok) {
          const msg = data && data.error ? data.error : 'Processing failed';
          throw new Error(msg);
        }
        return data;
      })
      .then(data => {
        // Check if we need to confirm overwrite
        if (data && data.confirm_overwrite) {
          derivInfo.classList.add('d-none');
          const confirmMsg = `${data.message}\n\nDo you want to overwrite these files?`;
          logToTerminal(`Existing files found: ${data.existing_files.join(', ')}`, 'warning');
          if (confirm(confirmMsg)) {
            logToTerminal('User confirmed overwrite', 'info');
            runRecipeProcessing(true);
          } else {
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
        
        if (data && data.validation_warning) {
          logToTerminal(data.validation_warning, 'warning');
        }

        if (data && data.out_format) {
          logToTerminal(`Output format used: ${data.out_format}`);
        }
        if (data && data.boilerplate_path) {
          logToTerminal(`Methods boilerplate (MD): ${data.boilerplate_path}`);
        }
        if (data && data.boilerplate_html_path) {
          logToTerminal(`Methods boilerplate (HTML): ${data.boilerplate_html_path}`);
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
        derivError.textContent = err.message;
        derivError.classList.remove('d-none');
        logToTerminal(err.message, 'error');
        derivRunBtn.disabled = false;
      });
  }
});
