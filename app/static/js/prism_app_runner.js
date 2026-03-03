document.addEventListener('DOMContentLoaded', function () {
  const root = document.getElementById('appRunnerRoot');
  if (!root) return;

  const runBtn = document.getElementById('runCompatibilityBtn');
  const runBidsAppBtn = document.getElementById('runBidsAppBtn');
  const statusBox = document.getElementById('compatibilityStatus');
  const resultsBox = document.getElementById('compatibilityResults');
  const runStatus = document.getElementById('runStatus');
  const runOutputContainer = document.getElementById('runOutputContainer');
  const runOutput = document.getElementById('runOutput');
  const envSummary = document.getElementById('envSummary');
  const configSummary = document.getElementById('configSummary');
  const recommendations = document.getElementById('compatibilityRecommendations');
  const repoInput = document.getElementById('runnerRepoPath');
  const runAppName = document.getElementById('runAppName');
  const runBidsFolder = document.getElementById('runBidsFolder');
  const runOutputFolder = document.getElementById('runOutputFolder');
  const runTmpFolder = document.getElementById('runTmpFolder');
  const runTemplateflowDir = document.getElementById('runTemplateflowDir');
  const runFsLicense = document.getElementById('runFsLicense');
  const runImageFolder = document.getElementById('runImageFolder');
  const runLocalImage = document.getElementById('runLocalImage');
  const scanImagesBtn = document.getElementById('scanImagesBtn');
  const loadOptionsBtn = document.getElementById('loadOptionsBtn');
  const runHelpText = document.getElementById('runHelpText');
  const runContainerEngine = document.getElementById('runContainerEngine');
  const runMode = document.getElementById('runMode');
  const runExecutionTarget = document.getElementById('runExecutionTarget');
  const runContainerPath = document.getElementById('runContainerPath');
  const runApptainerArgs = document.getElementById('runApptainerArgs');
  const runAnalysisLevel = document.getElementById('runAnalysisLevel');
  const runSubjects = document.getElementById('runSubjects');
  const runOutputSubdir = document.getElementById('runOutputSubdir');
  const runJobs = document.getElementById('runJobs');
  const runTimeout = document.getElementById('runTimeout');
  const runLogLevel = document.getElementById('runLogLevel');
  const runDryRun = document.getElementById('runDryRun');
  const runMonitor = document.getElementById('runMonitor');
  const runSlurmOnly = document.getElementById('runSlurmOnly');
  const runAppOptionsJson = document.getElementById('runAppOptionsJson');
  const toggleHpcAdvancedBtn = document.getElementById('toggleHpcAdvancedBtn');
  const hpcAdvancedPanel = document.getElementById('hpcAdvancedPanel');
  const hpcPartition = document.getElementById('hpcPartition');
  const hpcTime = document.getElementById('hpcTime');
  const hpcMem = document.getElementById('hpcMem');
  const hpcCpus = document.getElementById('hpcCpus');
  const hpcJobName = document.getElementById('hpcJobName');
  const hpcOutputPattern = document.getElementById('hpcOutputPattern');
  const hpcErrorPattern = document.getElementById('hpcErrorPattern');
  const hpcModules = document.getElementById('hpcModules');
  const hpcEnvironment = document.getElementById('hpcEnvironment');
  const hpcMonitorJobs = document.getElementById('hpcMonitorJobs');
  const toggleDataladBtn = document.getElementById('toggleDataladBtn');
  const dataladPanel = document.getElementById('dataladPanel');
  const dataladInputRepo = document.getElementById('dataladInputRepo');
  const dataladBranchPrefix = document.getElementById('dataladBranchPrefix');
  const dataladOutputRepos = document.getElementById('dataladOutputRepos');
  const dataladCloneRoot = document.getElementById('dataladCloneRoot');
  const dataladAutoPush = document.getElementById('dataladAutoPush');
  const toggleRemotePanelBtn = document.getElementById('toggleRemotePanelBtn');
  const remotePanel = document.getElementById('remotePanel');
  const remoteHost = document.getElementById('remoteHost');
  const remoteProfileSelect = document.getElementById('remoteProfileSelect');
  const remoteProfileName = document.getElementById('remoteProfileName');
  const saveRemoteProfileBtn = document.getElementById('saveRemoteProfileBtn');
  const deleteRemoteProfileBtn = document.getElementById('deleteRemoteProfileBtn');
  const remotePassphrase = document.getElementById('remotePassphrase');
  const storeEncryptedPassphrase = document.getElementById('storeEncryptedPassphrase');
  const useSavedPassphrase = document.getElementById('useSavedPassphrase');
  const remoteUser = document.getElementById('remoteUser');
  const remotePython = document.getElementById('remotePython');
  const remotePort = document.getElementById('remotePort');
  const remoteIdentityFile = document.getElementById('remoteIdentityFile');
  const remoteStrictHostKey = document.getElementById('remoteStrictHostKey');
  const remoteProjectPath = document.getElementById('remoteProjectPath');
  const remoteRunnerRepoPath = document.getElementById('remoteRunnerRepoPath');
  const remoteKnownHostsFile = document.getElementById('remoteKnownHostsFile');
  const remoteProxyJump = document.getElementById('remoteProxyJump');
  const remoteConnectTimeout = document.getElementById('remoteConnectTimeout');
  const remoteExecute = document.getElementById('remoteExecute');

  if (!runBtn || !statusBox || !resultsBox || !envSummary || !configSummary || !recommendations
    || !repoInput) {
    return;
  }

  function boolBadge(ok) {
    return `<span class="badge ${ok ? 'bg-success' : 'bg-secondary'}">${ok ? 'available' : 'missing'}</span>`;
  }

  function listHtml(items, emptyText) {
    if (!items || items.length === 0) return `<p class="text-muted mb-0">${emptyText}</p>`;
    return `<ul class="mb-0">${items.map(item => `<li>${item}</li>`).join('')}</ul>`;
  }

  function setStatus(status, blockingCount, warningCount) {
    statusBox.classList.remove('d-none', 'alert-success', 'alert-warning', 'alert-danger', 'alert-info');
    if (status === 'compatible') {
      statusBox.classList.add('alert-success');
      statusBox.textContent = 'Compatible: host and config checks passed.';
      return;
    }
    if (status === 'partial') {
      statusBox.classList.add('alert-warning');
      statusBox.textContent = `Partially compatible: ${warningCount} warning(s), ${blockingCount} blocking issue(s).`;
      return;
    }
    if (status === 'incompatible') {
      statusBox.classList.add('alert-danger');
      statusBox.textContent = `Incompatible: ${blockingCount} blocking issue(s) detected.`;
      return;
    }
    statusBox.classList.add('alert-info');
    statusBox.textContent = 'Compatibility check completed.';
  }

  function render(report) {
    const env = report.environment || {};
    const container = env.container || {};
    const hpc = env.hpc || {};
    const cfg = report.config || {};
    const repo = report.runner_repo || {};

    setStatus(report.status, (report.blocking_issues || []).length, (report.warnings || []).length);

    envSummary.innerHTML = `
      <div class="mb-2">Docker runtime: ${boolBadge(container.docker && container.docker.available)}</div>
      <div class="small text-muted">Current mode is Docker + local execution only.</div>
    `;

    const configMessages = [];
    if (report.resolved_config_path) {
      configMessages.push(`Resolved config: <code>${report.resolved_config_path}</code>`);
    }
    if (!cfg.present) {
      configMessages.push('No config provided for schema-level checks.');
    }
    if (repo.provided) {
      configMessages.push(`Runner repo: <code>${repo.path || 'n/a'}</code> (${repo.exists ? 'found' : 'missing'})`);
      if (repo.missing_files && repo.missing_files.length) {
        configMessages.push(`Missing expected files: ${repo.missing_files.join(', ')}`);
      }
    }

    configSummary.innerHTML = `
      ${listHtml(configMessages, 'No config/repo metadata provided.')}
      <hr>
      <h6 class="mb-2">Blocking Issues</h6>
      ${listHtml(report.blocking_issues, 'None')}
      <h6 class="mt-3 mb-2">Warnings</h6>
      ${listHtml(report.warnings, 'None')}
    `;

    recommendations.innerHTML = listHtml(report.recommendations, 'No recommendations generated.');
    resultsBox.classList.remove('d-none');
  }

  runBtn.addEventListener('click', async function () {
    runBtn.disabled = true;
    statusBox.classList.remove('d-none', 'alert-success', 'alert-warning', 'alert-danger');
    statusBox.classList.add('alert-info');
    statusBox.textContent = 'Running compatibility check...';

    const payload = {
      project_path: (window.currentProjectPath || '').trim(),
      runner_repo_path: repoInput.value.trim(),
    };

    try {
      const response = await fetch('/api/prism-app-runner/compatibility', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const report = await response.json();
      render(report || {});
    } catch (err) {
      statusBox.classList.remove('alert-info');
      statusBox.classList.add('alert-danger');
      statusBox.textContent = `Compatibility check failed: ${err.message}`;
    } finally {
      runBtn.disabled = false;
    }
  });

  function setRunStatus(message, level) {
    if (!runStatus) return;
    runStatus.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-warning', 'alert-danger');
    runStatus.classList.add(level || 'alert-info');
    runStatus.textContent = message;
  }

  async function browsePath(kind) {
    const endpoint = kind === 'file'
      ? '/api/browse-file?project_json_only=0'
      : '/api/browse-folder';
    const response = await fetch(endpoint);
    const data = await response.json();
    if (!response.ok || data.error) {
      throw new Error(data.error || 'Path picker failed.');
    }
    return (data.path || '').trim();
  }

  document.querySelectorAll('[data-browse-kind][data-browse-target]').forEach(button => {
    button.addEventListener('click', async function () {
      const kind = (button.getAttribute('data-browse-kind') || 'folder').trim();
      const targetId = (button.getAttribute('data-browse-target') || '').trim();
      const target = document.getElementById(targetId);
      if (!target) return;

      button.disabled = true;
      try {
        const selected = await browsePath(kind);
        if (selected) {
          target.value = selected;
          if (targetId === 'runImageFolder') {
            setRunStatus('Image folder selected. Click Scan to load available images.', 'alert-info');
          }
        }
      } catch (err) {
        setRunStatus(`Could not open ${kind} picker: ${err.message}`, 'alert-danger');
      } finally {
        button.disabled = false;
      }
    });
  });

  function getRemoteFormConfig(includeSecret = false) {
    const config = {
      host: (remoteHost?.value || '').trim(),
      user: (remoteUser?.value || '').trim(),
      python_exec: (remotePython?.value || 'python3').trim(),
      port: parseInt(remotePort?.value || '0', 10) || undefined,
      identity_file: (remoteIdentityFile?.value || '').trim(),
      strict_host_key_checking: (remoteStrictHostKey?.value || 'accept-new').trim(),
      project_path: (remoteProjectPath?.value || '').trim(),
      runner_repo_path: (remoteRunnerRepoPath?.value || '').trim(),
      user_known_hosts_file: (remoteKnownHostsFile?.value || '').trim(),
      proxy_jump: (remoteProxyJump?.value || '').trim(),
      connect_timeout: parseInt(remoteConnectTimeout?.value || '0', 10) || undefined,
    };

    if (includeSecret) {
      config.passphrase = (remotePassphrase?.value || '').trim();
      config.store_encrypted_passphrase = Boolean(storeEncryptedPassphrase?.checked);
    }

    return config;
  }

  function applyRemoteFormConfig(config) {
    const cfg = config || {};
    if (remoteHost) remoteHost.value = cfg.host || '';
    if (remoteUser) remoteUser.value = cfg.user || '';
    if (remotePython) remotePython.value = cfg.python_exec || 'python3';
    if (remotePort) remotePort.value = cfg.port || '';
    if (remoteIdentityFile) remoteIdentityFile.value = cfg.identity_file || '';
    if (remoteStrictHostKey) remoteStrictHostKey.value = cfg.strict_host_key_checking || 'accept-new';
    if (remoteProjectPath) remoteProjectPath.value = cfg.project_path || '';
    if (remoteRunnerRepoPath) remoteRunnerRepoPath.value = cfg.runner_repo_path || '';
    if (remoteKnownHostsFile) remoteKnownHostsFile.value = cfg.user_known_hosts_file || '';
    if (remoteProxyJump) remoteProxyJump.value = cfg.proxy_jump || '';
    if (remoteConnectTimeout) remoteConnectTimeout.value = cfg.connect_timeout || '';
    if (remotePassphrase) remotePassphrase.value = '';
    if (storeEncryptedPassphrase) storeEncryptedPassphrase.checked = false;
    if (useSavedPassphrase) useSavedPassphrase.checked = Boolean(cfg.has_encrypted_passphrase);
  }

  async function refreshRemoteProfiles() {
    if (!remoteProfileSelect) return;
    try {
      const response = await fetch('/api/prism-app-runner/remote-profiles');
      const data = await response.json();
      if (!response.ok || data.error) {
        return;
      }
      remoteProfileSelect.innerHTML = '<option value="">-- select profile --</option>';
      (data.profiles || []).forEach(item => {
        const option = document.createElement('option');
        option.value = item.name;
        option.textContent = item.name;
        remoteProfileSelect.appendChild(option);
      });
    } catch (_err) {
      // keep silent to avoid noisy UI at startup
    }
  }

  remoteProfileSelect?.addEventListener('change', async function () {
    const profileName = (remoteProfileSelect.value || '').trim();
    if (!profileName) return;
    try {
      const response = await fetch(`/api/prism-app-runner/remote-profiles/${encodeURIComponent(profileName)}`);
      const data = await response.json();
      if (!response.ok || data.error) {
        setRunStatus(data.error || 'Could not load remote profile.', 'alert-danger');
        return;
      }
      applyRemoteFormConfig(data.config || {});
      if (remoteProfileName) remoteProfileName.value = data.name || profileName;
      setRunStatus(`Loaded remote profile: ${profileName}`, 'alert-success');
    } catch (err) {
      setRunStatus(`Could not load profile: ${err.message}`, 'alert-danger');
    }
  });

  saveRemoteProfileBtn?.addEventListener('click', async function () {
    const name = (remoteProfileName?.value || '').trim();
    if (!name) {
      setRunStatus('Please enter a profile name before saving.', 'alert-danger');
      return;
    }
    const remoteConfig = getRemoteFormConfig(true);
    if (!remoteConfig.host || !remoteConfig.project_path || !remoteConfig.runner_repo_path) {
      setRunStatus('Profile requires host, remote project path, and remote runner repo path.', 'alert-danger');
      return;
    }

    saveRemoteProfileBtn.disabled = true;
    try {
      const response = await fetch('/api/prism-app-runner/remote-profiles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, remote: remoteConfig }),
      });
      const data = await response.json();
      if (!response.ok || data.error) {
        setRunStatus(data.error || 'Could not save remote profile.', 'alert-danger');
        return;
      }
      await refreshRemoteProfiles();
      if (remoteProfileSelect) remoteProfileSelect.value = data.name || name;
      setRunStatus(`Saved remote profile: ${data.name || name}`, 'alert-success');
    } catch (err) {
      setRunStatus(`Could not save profile: ${err.message}`, 'alert-danger');
    } finally {
      saveRemoteProfileBtn.disabled = false;
    }
  });

  deleteRemoteProfileBtn?.addEventListener('click', async function () {
    const profileName = (remoteProfileSelect?.value || remoteProfileName?.value || '').trim();
    if (!profileName) {
      setRunStatus('Select a profile to delete.', 'alert-danger');
      return;
    }
    if (!confirm(`Delete remote profile "${profileName}"?`)) {
      return;
    }

    deleteRemoteProfileBtn.disabled = true;
    try {
      const response = await fetch(`/api/prism-app-runner/remote-profiles/${encodeURIComponent(profileName)}`, {
        method: 'DELETE',
      });
      const data = await response.json();
      if (!response.ok || data.error) {
        setRunStatus(data.error || 'Could not delete profile.', 'alert-danger');
        return;
      }
      await refreshRemoteProfiles();
      if (remoteProfileName) remoteProfileName.value = '';
      if (remoteProfileSelect) remoteProfileSelect.value = '';
      setRunStatus(`Deleted remote profile: ${profileName}`, 'alert-success');
    } catch (err) {
      setRunStatus(`Could not delete profile: ${err.message}`, 'alert-danger');
    } finally {
      deleteRemoteProfileBtn.disabled = false;
    }
  });

  function appendRunOutput(text) {
    if (!runOutput || !runOutputContainer) return;
    runOutput.textContent = text || '';
    runOutputContainer.classList.remove('d-none');
  }

  function tryParseJson(text, label) {
    const raw = (text || '').trim();
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (_err) {
      setRunStatus(`${label} must be valid JSON.`, 'alert-danger');
      throw new Error(`${label} must be valid JSON`);
    }
  }

  function syncContainerFromImageSelect() {
    const selected = (runLocalImage?.value || '').trim();
    const folder = (runImageFolder?.value || '').trim();
    if (!selected) return;
    if (!folder) {
      runContainerPath.value = selected;
      return;
    }
    const normalizedFolder = folder.endsWith('/') ? folder.slice(0, -1) : folder;
    runContainerPath.value = `${normalizedFolder}/${selected}`;
  }

  runLocalImage?.addEventListener('change', syncContainerFromImageSelect);

  function updateHpcPanelVisibility() {
    if (!hpcAdvancedPanel) return;
    const isHpc = (runMode?.value || 'local') === 'hpc';
    if (isHpc) {
      hpcAdvancedPanel.classList.remove('d-none');
      return;
    }
    if (!hpcAdvancedPanel.classList.contains('d-none')) {
      hpcAdvancedPanel.classList.add('d-none');
    }
  }

  runMode?.addEventListener('change', updateHpcPanelVisibility);
  updateHpcPanelVisibility();

  function updateRemotePanelVisibility() {
    if (!remotePanel) return;
    const isRemote = (runExecutionTarget?.value || 'local') === 'remote_ssh';
    if (isRemote) {
      remotePanel.classList.remove('d-none');
      return;
    }
    if (!remotePanel.classList.contains('d-none')) {
      remotePanel.classList.add('d-none');
    }
  }

  runExecutionTarget?.addEventListener('change', updateRemotePanelVisibility);
  updateRemotePanelVisibility();

  if (runContainerEngine) runContainerEngine.value = 'docker';
  if (runMode) runMode.value = 'local';
  if (runExecutionTarget) runExecutionTarget.value = 'local';

  toggleHpcAdvancedBtn?.addEventListener('click', function () {
    if (!hpcAdvancedPanel) return;
    hpcAdvancedPanel.classList.toggle('d-none');
  });

  toggleDataladBtn?.addEventListener('click', function () {
    if (!dataladPanel) return;
    dataladPanel.classList.toggle('d-none');
  });

  toggleRemotePanelBtn?.addEventListener('click', function () {
    if (!remotePanel) return;
    remotePanel.classList.toggle('d-none');
  });

  scanImagesBtn?.addEventListener('click', async function () {
    const imagesFolder = (runImageFolder?.value || '').trim();
    if (!imagesFolder) {
      setRunStatus('Please enter an images folder before scanning.', 'alert-danger');
      return;
    }

    scanImagesBtn.disabled = true;
    setRunStatus('Scanning image folder...', 'alert-info');
    try {
      const response = await fetch('/api/prism-app-runner/scan-images', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ images_folder: imagesFolder }),
      });
      const data = await response.json();
      if (!response.ok || data.error) {
        setRunStatus(data.error || 'Image scan failed.', 'alert-danger');
        return;
      }

      if (runLocalImage) {
        runLocalImage.innerHTML = '<option value="">-- no image selected --</option>';
        (data.images || []).forEach(name => {
          const option = document.createElement('option');
          option.value = name;
          option.textContent = name;
          runLocalImage.appendChild(option);
        });
      }

      setRunStatus(`Found ${data.count || 0} image(s).`, 'alert-success');
    } catch (err) {
      setRunStatus(`Image scan failed: ${err.message}`, 'alert-danger');
    } finally {
      scanImagesBtn.disabled = false;
    }
  });

  loadOptionsBtn?.addEventListener('click', async function () {
    syncContainerFromImageSelect();
    const container = (runContainerPath?.value || '').trim();
    if (!container) {
      setRunStatus('Select an image or enter a container path first.', 'alert-danger');
      return;
    }

    loadOptionsBtn.disabled = true;
    setRunStatus('Loading app help/options from container...', 'alert-info');
    try {
      const response = await fetch('/api/prism-app-runner/load-help', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          container_engine: runContainerEngine?.value || 'apptainer',
          container,
          timeout_seconds: 30,
        }),
      });
      const data = await response.json();
      if (!response.ok || data.error) {
        setRunStatus(data.error || 'Could not load container help.', 'alert-danger');
        if (runHelpText) runHelpText.textContent = '';
        return;
      }

      if (runHelpText) {
        const optionLines = (data.options || []).map(opt => `- ${opt}`).join('\n');
        runHelpText.textContent =
          `Command: ${(data.command || []).join(' ')}\n\n` +
          `Detected options:\n${optionLines || '(none detected)'}\n\n` +
          `--- Help Text ---\n${data.help_text || ''}`;
      }
      setRunStatus(`Loaded help/options (${(data.options || []).length} options detected).`, 'alert-success');
    } catch (err) {
      setRunStatus(`Could not load help: ${err.message}`, 'alert-danger');
      if (runHelpText) runHelpText.textContent = '';
    } finally {
      loadOptionsBtn.disabled = false;
    }
  });

  runBidsAppBtn?.addEventListener('click', async function () {
    const projectPath = (window.currentProjectPath || '').trim();
    if (!projectPath) {
      setRunStatus('No active PRISM project loaded.', 'alert-danger');
      return;
    }

    syncContainerFromImageSelect();
    let parsedOptions = null;
    try {
      parsedOptions = tryParseJson(runAppOptionsJson?.value || '', 'App Options JSON');
    } catch (_err) {
      return;
    }

    const appOptions = parsedOptions || {};
    const fsLicense = (runFsLicense?.value || '').trim();
    if (fsLicense) {
      appOptions['--fs-license-file'] = fsLicense;
    }

    const payload = {
      runner_repo_path: repoInput.value.trim(),
      app_name: (runAppName?.value || '').trim(),
      container_engine: 'docker',
      mode: 'local',
      execution_target: 'local',
      container: (runContainerPath?.value || '').trim(),
      analysis_level: runAnalysisLevel?.value || 'participant',
      subjects: (runSubjects?.value || '').trim(),
      output_subdir: (runOutputSubdir?.value || '').trim(),
      jobs: parseInt(runJobs?.value || '1', 10) || 1,
      timeout_seconds: parseInt(runTimeout?.value || '180', 10) || 180,
      log_level: runLogLevel?.value || 'INFO',
      dry_run: Boolean(runDryRun?.checked),
      app_options: appOptions,
      bids_folder: (runBidsFolder?.value || '').trim(),
      output_folder: (runOutputFolder?.value || '').trim(),
      tmp_folder: (runTmpFolder?.value || '').trim(),
      templateflow_dir: (runTemplateflowDir?.value || '').trim(),
    };

    if (!payload.app_name || !payload.container) {
      setRunStatus('App name and container are required.', 'alert-danger');
      return;
    }

    if (!payload.runner_repo_path) {
      setRunStatus('Runner repository path is required for local execution.', 'alert-danger');
      return;
    }

    runBidsAppBtn.disabled = true;
    setRunStatus('Preparing runner config and executing...', 'alert-info');

    try {
      const response = await fetch('/api/prism-app-runner/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json();

      if (!response.ok && !data) {
        throw new Error('Runner request failed.');
      }

      if (data.error) {
        setRunStatus(data.error, 'alert-danger');
        appendRunOutput('');
        return;
      }

      const prepared = data.prepared || {};
      const lines = [];
      lines.push(`Mode: local (docker) | Dry-run: ${String(data.dry_run)}`);
      lines.push(`Config: ${prepared.config_path || 'n/a'}`);
      lines.push(`Input BIDS: ${prepared.bids_folder || 'n/a'}`);
      lines.push(`Output: ${prepared.output_folder || 'n/a'}`);
      lines.push(`Temp: ${(prepared.config?.common?.tmp_folder) || payload.tmp_folder || 'n/a'}`);
      lines.push(`Command: ${(data.command || []).join(' ')}`);
      lines.push('');
      if (data.stdout) {
        lines.push('--- STDOUT ---');
        lines.push(data.stdout);
      }
      if (data.stderr) {
        lines.push('--- STDERR ---');
        lines.push(data.stderr);
      }
      appendRunOutput(lines.join('\n'));

      if (data.success) {
        setRunStatus('Runner completed successfully.', 'alert-success');
      } else if (data.timed_out) {
        setRunStatus(`Runner timed out after ${data.timeout_seconds}s.`, 'alert-warning');
      } else {
        setRunStatus(`Runner finished with exit code ${data.exit_code}.`, 'alert-warning');
      }
    } catch (err) {
      setRunStatus(`Run failed: ${err.message}`, 'alert-danger');
    } finally {
      runBidsAppBtn.disabled = false;
    }
  });

  refreshRemoteProfiles();
});
