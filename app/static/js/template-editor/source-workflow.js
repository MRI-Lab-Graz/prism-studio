export async function refreshTemplateList(context, { silent = false } = {}) {
  const modality = context.modalityEl.value;
  const requestProjectPath = context.getCurrentProjectPath();
  const requestToken = context.projectContextRequestToken;
  if (!silent) {
    context.clearAlert();
    context.btnDownload.disabled = true;
    context.btnSave.disabled = true;
  }
  context.templateMetadata = {};

  const schemaVersion = context.schemaEl.value || 'stable';
  const data = await context.apiGet(
    context.withProjectPathQuery(
      `/api/template-editor/list-merged?modality=${encodeURIComponent(modality)}&schema_version=${encodeURIComponent(schemaVersion)}`,
      requestProjectPath
    )
  );
  if (!context.isProjectContextCurrent(requestProjectPath, requestToken)) {
    return;
  }

  const projectTemplates = (data.templates || []).filter((template) => template.source === 'project');
  const globalTemplates = (data.templates || []).filter((template) => template.source !== 'project');

  context.projectTemplateSelectEl.innerHTML = '<option value="">(none in project)</option>';
  for (const template of projectTemplates) {
    const expectedPrefix = `${modality}-`;
    if (!template.filename.startsWith(expectedPrefix) && template.filename !== 'participants_mapping.json') {
      continue;
    }
    if (modality === 'survey' && template.filename === 'participants_mapping.json') {
      continue;
    }
    const option = document.createElement('option');
    option.value = template.filename;
    option.textContent = `${context.templateStatusPrefix(template)} ${template.filename}`;
    option.dataset.source = template.source;
    option.dataset.path = template.path;
    option.dataset.readonly = template.readonly;
    option.dataset.templateValid = String(template.template_valid);
    option.title = context.templateStatusTitle(template);
    context.projectTemplateSelectEl.appendChild(option);
    context.templateMetadata[template.filename] = template;
  }

  context.globalTemplateSelectEl.innerHTML = '<option value="">(select one)</option>';
  for (const template of globalTemplates) {
    const expectedPrefix = `${modality}-`;
    if (!template.filename.startsWith(expectedPrefix)) {
      continue;
    }
    const option = document.createElement('option');
    option.value = template.filename;
    option.textContent = `${context.templateStatusPrefix(template)} ${template.filename}`;
    option.dataset.source = template.source;
    option.dataset.path = template.path;
    option.dataset.readonly = template.readonly;
    option.dataset.templateValid = String(template.template_valid);
    option.title = context.templateStatusTitle(template);
    context.globalTemplateSelectEl.appendChild(option);
    context.templateMetadata[template.filename] = template;
  }

  context.projectLibraryRoot = data.sources?.project_library_path || null;
  context.projectLibraryExists = Boolean(data.sources?.project_library_exists);
  context.editorProjectContextPath = requestProjectPath;

  context.updateProjectLibraryStatus();
  context.updateLoadButtonState();
}

export async function loadSelectedTemplate(context) {
  const modality = context.modalityEl.value;
  const schemaVersion = context.schemaEl.value;
  const requestProjectPath = context.getCurrentProjectPath();
  const requestToken = context.projectContextRequestToken;
  const isProjectSelection = Boolean(context.projectTemplateSelectEl.value);
  const activeSelectEl = isProjectSelection ? context.projectTemplateSelectEl : context.globalTemplateSelectEl;
  const filename = activeSelectEl.value;

  if (!filename) {
    context.showAlert('warning', 'Select a template to load.');
    return;
  }

  if (context.hasUnsavedChanges() && !confirm('You have unsaved changes. Load a new template and discard them?')) {
    return;
  }

  context.clearAlert();
  context.btnDownload.disabled = true;
  context.btnSave.disabled = true;

  await context.refreshSchema();

  const selectedOpt = activeSelectEl.options[activeSelectEl.selectedIndex];
  const absolutePath = selectedOpt?.dataset?.path || null;
  const isReadonly = selectedOpt ? selectedOpt.dataset.readonly === 'true' : true;
  const queryParams = new URLSearchParams({ modality, schema_version: schemaVersion, filename });

  if (absolutePath) {
    queryParams.set('absolute_path', absolutePath);
  } else {
    const meta = context.templateMetadata[filename];
    if (meta && meta.path) {
      const normalizedPath = meta.path.replace(/\\/g, '/');
      const pathParts = normalizedPath.split('/');
      const modalityIdx = pathParts.lastIndexOf(modality);
      if (modalityIdx > 0) {
        const libraryPath = pathParts.slice(0, modalityIdx).join('/');
        if (libraryPath) {
          queryParams.set('library_path', libraryPath);
        }
      }
    }
  }

  const data = await context.apiGet(`/api/template-editor/load?${queryParams.toString()}`);
  if (!context.isProjectContextCurrent(requestProjectPath, requestToken)) {
    return;
  }

  context.currentTemplate = context.stripInternalTemplateKeys(data.template);
  context.stripScoreAnnotationsInTemplate(context.currentTemplate);
  context.originalTemplate = context.cloneDeep(context.currentTemplate);
  context.currentTemplateFilename = data.filename || filename;
  context.loadedFromReadonly = isReadonly;
  context.loadedFromProjectLibrary = !isReadonly;
  context.loadedTemplateProjectPath = isReadonly ? '' : requestProjectPath;
  if (context.btnDelete) {
    context.btnDelete.classList.toggle('d-none', isReadonly);
  }
  context.checkedItemIds = new Set();
  context.selectedItemId = context.itemKeysFromTemplate(context.currentTemplate)[0] || null;
  context.hasUserInteracted = true;
  context.hasExplicitTemplate = true;
  context.previewVariantOverride = null;
  if (context.activeVariantSelectEl) {
    context.activeVariantSelectEl.value = '';
  }
  context.renderAll();
  context.renderJsonDiff();
  await validateCurrent(context);
}

export async function loadNewTemplate(context) {
  const modality = context.modalityEl.value;
  const schemaVersion = context.schemaEl.value;
  context.clearAlert();
  context.btnDownload.disabled = true;
  context.btnSave.disabled = true;

  await context.refreshSchema();

  const data = await context.apiGet(
    `/api/template-editor/new?modality=${encodeURIComponent(modality)}&schema_version=${encodeURIComponent(schemaVersion)}`
  );
  context.currentTemplate = context.stripInternalTemplateKeys(data.template);
  context.stripScoreAnnotationsInTemplate(context.currentTemplate);
  context.originalTemplate = null;
  context.currentTemplateFilename = null;
  context.clearTemplateSelections();
  context.checkedItemIds = new Set();
  context.selectedItemId = context.itemKeysFromTemplate(context.currentTemplate)[0] || null;
  context.hasUserInteracted = true;
  context.loadedFromReadonly = false;
  context.loadedFromProjectLibrary = false;
  context.loadedTemplateProjectPath = '';
  if (context.btnDelete) {
    context.btnDelete.classList.add('d-none');
  }
  context.previewVariantOverride = null;
  if (context.activeVariantSelectEl) {
    context.activeVariantSelectEl.value = '';
  }
  context.renderAll();
  context.renderJsonDiff();
}

export async function validateCurrent(context) {
  const modality = context.modalityEl.value;
  const schemaVersion = context.schemaEl.value;
  const requestProjectPath = context.getCurrentProjectPath();
  const requestToken = context.projectContextRequestToken;
  const exportWordButton = context.getExportWordButton();

  const obj = context.currentTemplate;
  if (!obj || typeof obj !== 'object') {
    context.btnDownload.disabled = true;
    context.showAlert('danger', 'No template loaded');
    return false;
  }

  if (!context.hasExplicitTemplate) {
    context.showAlert('warning', '⚠️ No template loaded yet. Select a template from the dropdown, or click <strong>Create</strong> to start a new one.');
    return false;
  }

  context.hasUserInteracted = true;
  const data = await context.apiPost('/api/template-editor/validate', {
    modality,
    schema_version: schemaVersion,
    template: obj,
    is_global: context.loadedFromReadonly,
  });
  if (!context.isProjectContextCurrent(requestProjectPath, requestToken)) {
    context.btnSave.disabled = true;
    return false;
  }

  const langWarnings = data.language_warnings || [];
  let langWarnHtml = '';
  if (langWarnings.length > 0) {
    const items = langWarnings
      .map((warning) => `<li><i class="fas fa-globe text-warning me-1"></i>${warning.message}${warning.details ? ` <small class="text-muted">(${warning.details})</small>` : ''}</li>`)
      .join('');
    langWarnHtml = `<div class="alert alert-warning mt-2 mb-0"><strong>Language warnings:</strong><ul class="mb-0">${items}</ul></div>`;
  }

  if (data.ok) {
    context.btnDownload.disabled = false;
    if (exportWordButton) {
      exportWordButton.disabled = false;
    }
    const targetDirectory = context.projectLibraryRoot
      ? context.addTrailingDisplaySeparator(context.joinDisplayPath(context.projectLibraryRoot, context.modalityEl.value))
      : null;
    const successMessage = context.projectLibraryRoot
      ? (context.loadedFromReadonly
        ? `✅ Valid template! Ready to save an editable project copy to <code>${targetDirectory}</code>`
        : `✅ Valid template! Ready to save to <code>${targetDirectory}</code>`)
      : '⚠️ Valid template, but <strong>no project selected</strong>. Select a project to enable saving, or download the JSON.';
    context.btnSave.disabled = !context.projectLibraryRoot;
    context.showAlert(context.projectLibraryRoot ? 'success' : 'warning', successMessage + langWarnHtml);
    return true;
  }

  context.btnDownload.disabled = false;
  if (exportWordButton) {
    exportWordButton.disabled = false;
  }
  context.btnSave.disabled = true;
  const errs = (data.errors || []).slice(0, 50);
  const list = errs
    .map((error) => {
      const path = error.path || '(root)';
      const focusPath = context.deriveFocusPath(error.path, error.message);
      const link = `<a href="#" class="error-link" data-path="${context.escapeHtml(focusPath)}"><code>${context.escapeHtml(path)}</code></a>`;
      return `<li>${link}: ${context.escapeHtml(error.message)}</li>`;
    })
    .join('');
  const extra = (data.errors || []).length > errs.length ? `<div class="mt-2 text-muted small">(showing first ${errs.length} errors)</div>` : '';
  context.showAlert('danger', `❌ Validation failed.<ul class="mb-0">${list}</ul>${extra}` + langWarnHtml);
  context.alertAreaEl.querySelectorAll('.error-link').forEach((linkEl) => {
    linkEl.addEventListener('click', (event) => {
      event.preventDefault();
      context.focusField(linkEl.dataset.path);
    });
  });
  context.renderMissingSummary();
  return false;
}

export async function saveCurrent(context) {
  const obj = context.currentTemplate;
  if (!obj || typeof obj !== 'object') {
    context.showAlert('danger', 'No template loaded');
    return;
  }

  const modality = context.modalityEl.value;
  const currentProjectPath = context.getCurrentProjectPath();
  if (!context.projectLibraryRoot || !currentProjectPath) {
    context.showAlert('danger', `<strong>No project selected!</strong><br>All template saves go to <code>${context.getProjectLibraryPattern('{modality}')}</code><br>Please select or create a project first.`);
    return;
  }

  const filename = context.resolveTemplateFilenameForSave(obj, modality);
  const validationPassed = await validateCurrent(context);
  if (!validationPassed) {
    context.showAlert('danger', 'Cannot save: template is currently invalid. Fix validation errors and validate again.');
    return;
  }

  const wasFork = context.loadedFromReadonly;
  const saveDecision = context.getSaveDecision(filename);
  if (!saveDecision.proceed) {
    return;
  }

  context.ensureTemplateNormalized();
  try {
    const data = await context.apiPost('/api/template-editor/save', {
      modality,
      schema_version: context.schemaEl.value || 'stable',
      filename,
      project_path: currentProjectPath,
      allow_overwrite: saveDecision.allowOverwrite,
      is_global: wasFork,
      template: obj,
    });
    if (currentProjectPath !== context.getCurrentProjectPath()) {
      context.loadedFromReadonly = false;
      context.loadedFromProjectLibrary = false;
      context.loadedTemplateProjectPath = '';
      if (context.btnDelete) {
        context.btnDelete.classList.add('d-none');
      }
      context.btnSave.disabled = true;
      context.clearTemplateSelections();
      context.showAlert('warning', `Saved to the previous project library before the active project changed. The current editor state is kept as a detached draft.<br><small>${context.escapeHtml(data.message || '')}</small>`);
      await refreshTemplateList(context, { silent: true });
      return;
    }
    context.currentTemplateFilename = filename;
    context.originalTemplate = context.cloneDeep(context.currentTemplate);
    context.loadedFromReadonly = false;
    context.loadedFromProjectLibrary = true;
    context.loadedTemplateProjectPath = currentProjectPath;
    context.renderJsonDiff();
    const savedPath = context.joinDisplayPath(context.projectLibraryRoot, modality, filename);
    const forkNote = wasFork
      ? '<br><small class="text-info">↗ Saved as a project copy — the global template was not changed.</small>'
      : '';
    context.showAlert('success', `✅ Saved to project library: <code>${savedPath}</code>${forkNote}`);
    await refreshTemplateList(context, { silent: true });
  } catch (error) {
    context.showAlert('danger', `Save failed: ${context.escapeHtml(error.message)}`);
  }
}

export async function downloadCurrent(context) {
  const obj = context.currentTemplate;
  if (!obj || typeof obj !== 'object') {
    context.showAlert('danger', 'No template loaded');
    return;
  }

  context.ensureTemplateNormalized();
  const filename = context.resolveTemplateFilenameForSave(obj, context.modalityEl.value);

  const res = await context.fetchWithApiFallback('/api/template-editor/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, modality: context.modalityEl.value, template: obj }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || `Download failed (${res.status})`);
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename.toLowerCase().endsWith('.json') ? filename : `${filename}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

function applyImportedTemplate(context, data, file) {
  context.currentTemplate = context.stripInternalTemplateKeys(data.template);
  context.stripScoreAnnotationsInTemplate(context.currentTemplate);
  context.originalTemplate = null;
  context.currentTemplateFilename = context.normalizeTemplateFilename(data.suggested_filename, context.modalityEl.value, context.currentTemplate);
  context.loadedFromReadonly = false;
  context.loadedFromProjectLibrary = false;
  context.loadedTemplateProjectPath = '';
  context.hasUserInteracted = true;
  context.hasExplicitTemplate = true;
  context.clearTemplateSelections();
  context.checkedItemIds = new Set();
  context.selectedItemId = context.itemKeysFromTemplate(context.currentTemplate)[0] || null;
  if (context.btnDelete) {
    context.btnDelete.classList.add('d-none');
  }
  context.renderAll();

  const source = (file.name.split('.').pop() || '').toLowerCase().toUpperCase();
  const itemCount = data.item_count || data.question_count || context.itemKeysFromTemplate(context.currentTemplate).length;
  return `<strong>Imported ${context.escapeHtml(file.name)}</strong> (${context.escapeHtml(source)})<br>${context.escapeHtml(String(itemCount))} item(s) extracted.`;
}

async function finishImport(context, importSummaryMessage) {
  context.showAlert('success', importSummaryMessage);
  try {
    await validateCurrent(context);
  } catch (error) {
    context.btnDownload.disabled = false;
    context.btnSave.disabled = true;
    context.showAlert('warning', `${importSummaryMessage}<br><small>Validation could not be completed: ${context.escapeHtml(error.message)}</small>`);
  }
}

function hideExcelGroupPicker(context) {
  if (context.excelGroupPickerRowEl) {
    context.excelGroupPickerRowEl.classList.add('d-none');
  }
  if (context.excelGroupPickerSelectEl) {
    context.excelGroupPickerSelectEl.innerHTML = '';
  }
}

async function loadExcelGroup(context, file, group, previousEditorState) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('modality', context.modalityEl.value);
    formData.append('schema_version', context.schemaEl.value || 'stable');
    formData.append('group', group);

    const res = await context.fetchWithApiFallback('/api/template-editor/import-excel', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || `Import failed (${res.status})`);
    }

    hideExcelGroupPicker(context);
    const importSummaryMessage = applyImportedTemplate(context, data, file);
    await finishImport(context, importSummaryMessage);
  } catch (error) {
    context.restoreEditorState(previousEditorState);
    context.showAlert('danger', `Template import failed: ${context.escapeHtml(error.message)}`);
  }
}

async function importExcelCodebook(context, file, previousEditorState) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('modality', context.modalityEl.value);
  formData.append('schema_version', context.schemaEl.value || 'stable');

  const res = await context.fetchWithApiFallback('/api/template-editor/import-excel', {
    method: 'POST',
    body: formData,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `Template import failed (${res.status})`);
  }

  const groups = data.groups || [];
  if (groups.length === 0) {
    throw new Error('No instrument groups detected in the file.');
  }

  if (groups.length === 1) {
    await loadExcelGroup(context, file, groups[0].prefix, previousEditorState);
    return;
  }

  if (!context.excelGroupPickerRowEl || !context.excelGroupPickerSelectEl || !context.btnLoadExcelGroup) {
    throw new Error(`Detected ${groups.length} instrument groups, but this editor build has no group picker UI to choose one.`);
  }

  context.excelGroupPickerSelectEl.innerHTML = groups
    .map((g) => `<option value="${context.escapeHtml(g.prefix)}">${context.escapeHtml(g.prefix)} (${g.item_count} item${g.item_count === 1 ? '' : 's'})</option>`)
    .join('');
  context.excelGroupPickerRowEl.classList.remove('d-none');

  context.btnLoadExcelGroup.onclick = () => {
    const selected = context.excelGroupPickerSelectEl.value;
    if (!selected) {
      return;
    }
    loadExcelGroup(context, file, selected, previousEditorState);
  };

  context.showAlert('info', `Detected ${groups.length} instrument groups in ${context.escapeHtml(file.name)}. Choose one above to load it into the editor.`);
}

export async function importTemplateSource(context) {
  const file = context.templateImportInput.files[0];
  if (!file) {
    return;
  }
  context.templateImportInput.value = '';

  if (context.hasUnsavedChanges() && !confirm('You have unsaved changes. Importing a template source will discard them. Continue?')) {
    return;
  }

  const previousEditorState = context.captureEditorState();
  context.clearAlert();
  context.btnDownload.disabled = true;
  context.btnSave.disabled = true;
  hideExcelGroupPicker(context);

  let importSummaryMessage = '';

  try {
    await context.refreshSchema();

    const lowerName = (file.name || '').toLowerCase();
    const isLsqOrLsg = lowerName.endsWith('.lsq') || lowerName.endsWith('.lsg');
    const isExcelCodebook = lowerName.endsWith('.xlsx') || lowerName.endsWith('.csv') || lowerName.endsWith('.tsv');

    if (isExcelCodebook) {
      // The Excel/CSV/TSV codebook path may pause for the user to pick an
      // instrument group; it handles its own success/validate/error flow.
      await importExcelCodebook(context, file, previousEditorState);
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    let data;
    if (isLsqOrLsg) {
      const res = await context.fetchWithApiFallback('/api/template-editor/import-lsq-lsg', {
        method: 'POST',
        body: formData,
      });
      data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Import failed (${res.status})`);
      }
      importSummaryMessage = applyImportedTemplate(context, data, file);
    } else {
      const nameWithoutExt = (file.name || 'imported').replace(/\.[^.]+$/, '').trim();
      formData.append('mode', 'combined');
      if (nameWithoutExt) {
        formData.append('task_name', context.sanitizeTaskNameForFilename(nameWithoutExt));
      }

      const res = await context.fetchWithApiFallback('/api/survey-generate-templates', {
        method: 'POST',
        body: formData,
      });
      data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Template import failed (${res.status})`);
      }

      if (!data.prism_json || typeof data.prism_json !== 'object') {
        throw new Error('No PRISM template returned by generator.');
      }
      importSummaryMessage = applyImportedTemplate(context, { ...data, template: data.prism_json }, file);
    }
  } catch (error) {
    context.restoreEditorState(previousEditorState);
    context.showAlert('danger', `Template import failed: ${context.escapeHtml(error.message)}`);
    return;
  }

  await finishImport(context, importSummaryMessage);
}

export async function deleteCurrentTemplate(context) {
  const filename = context.currentTemplateFilename;
  if (!filename || context.loadedFromReadonly) {
    return;
  }
  const currentProjectPath = context.getCurrentProjectPath();
  if (!currentProjectPath) {
    context.showAlert('warning', 'No project selected. Reload the template from the current project before deleting it.');
    return;
  }
  if (!confirm(`Permanently delete "${filename}" from the project library? This cannot be undone.`)) {
    return;
  }
  const modality = context.modalityEl.value;
  try {
    const res = await context.fetchWithApiFallback('/api/template-editor/delete', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ modality, filename, project_path: currentProjectPath }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || `Delete failed (${res.status})`);
    }
    context.currentTemplate = null;
    context.originalTemplate = null;
    context.currentTemplateFilename = null;
    context.selectedItemId = null;
    context.checkedItemIds = new Set();
    context.previewVariantOverride = null;
    if (context.activeVariantSelectEl) {
      context.activeVariantSelectEl.value = '';
    }
    context.loadedFromReadonly = false;
    context.loadedFromProjectLibrary = false;
    context.loadedTemplateProjectPath = '';
    context.hasUserInteracted = false;
    context.hasExplicitTemplate = false;
    context.clearTemplateSelections();
    context.btnDelete.classList.add('d-none');
    context.btnSave.disabled = true;
    context.btnDownload.disabled = true;
    context.renderAll();
    context.showAlert('success', `🗑️ Deleted <code>${context.escapeHtml(filename)}</code> from the project library.`);
    await refreshTemplateList(context, { silent: true });
  } catch (error) {
    context.showAlert('danger', context.escapeHtml(error.message));
  }
}

export function bindTemplateEditorSourceWorkflowEvents(context) {
  context.btnImportTemplateSource.addEventListener('click', () => {
    context.templateImportInput.click();
  });

  context.templateImportInput.addEventListener('change', async () => {
    try {
      await importTemplateSource(context);
    } catch (error) {
      context.showAlert('danger', context.escapeHtml(error.message));
    }
  });

  window.addEventListener('beforeunload', (event) => {
    if (context.hasUnsavedChanges()) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  context.modalityEl.addEventListener('change', async () => {
    const previousModality = context.getTrackedSelectValue(context.modalityEl);
    if (context.hasUnsavedChanges() && !confirm('You have unsaved changes. Switch modality and discard them?')) {
      context.revertTrackedSelectValue(context.modalityEl, previousModality);
      return;
    }
    try {
      await refreshTemplateList(context);
      await loadNewTemplate(context);
      context.hasExplicitTemplate = false;
      context.commitTrackedSelectValue(context.modalityEl);
    } catch (error) {
      context.revertTrackedSelectValue(context.modalityEl, previousModality);
      try {
        await context.refreshSchema();
        await refreshTemplateList(context, { silent: true });
      } catch {}
      context.showAlert('danger', context.escapeHtml(error.message));
    }
  });

  context.schemaEl.addEventListener('change', async () => {
    const previousSchemaVersion = context.getTrackedSelectValue(context.schemaEl);
    if (context.hasUnsavedChanges() && !confirm('You have unsaved changes. Switch schema version and discard them?')) {
      context.revertTrackedSelectValue(context.schemaEl, previousSchemaVersion);
      return;
    }
    try {
      context.btnDownload.disabled = true;
      context.btnSave.disabled = true;
      await refreshTemplateList(context);
      await loadNewTemplate(context);
      context.hasExplicitTemplate = false;
      context.commitTrackedSelectValue(context.schemaEl);
    } catch (error) {
      context.revertTrackedSelectValue(context.schemaEl, previousSchemaVersion);
      try {
        await context.refreshSchema();
        await refreshTemplateList(context, { silent: true });
      } catch {}
      context.showAlert('danger', context.escapeHtml(error.message));
    }
  });

  context.btnCreateOpen.addEventListener('click', () => {
    context.focusCreateSourcePanel();
  });

  if (context.templateSourceSectionEl) {
    context.templateSourceSectionEl.addEventListener('shown.bs.collapse', () => {
      context.btnCreateOpen?.setAttribute('aria-expanded', 'true');
    });
    context.templateSourceSectionEl.addEventListener('hidden.bs.collapse', () => {
      context.btnCreateOpen?.setAttribute('aria-expanded', 'false');
    });
  }

  context.btnNew.addEventListener('click', async () => {
    if (context.hasUnsavedChanges() && !confirm('You have unsaved changes. Create a new blank template and discard them?')) {
      return;
    }

    const previousEditorState = context.captureEditorState();
    try {
      await loadNewTemplate(context);
      context.hasExplicitTemplate = true;
      context.focusCreateSourcePanel();
    } catch (error) {
      context.restoreEditorState(previousEditorState);
      context.showAlert('danger', context.escapeHtml(error.message));
    }
  });

  context.projectTemplateSelectEl.addEventListener('change', async () => {
    const previousEditorState = context.captureEditorState();
    if (context.projectTemplateSelectEl.value) {
      context.globalTemplateSelectEl.value = '';
      try {
        await loadSelectedTemplate(context);
      } catch (error) {
        context.restoreEditorState(previousEditorState);
        context.showAlert('danger', context.escapeHtml(error.message));
      }
    }
    context.updateLoadButtonState();
  });

  context.globalTemplateSelectEl.addEventListener('change', async () => {
    const previousEditorState = context.captureEditorState();
    if (context.globalTemplateSelectEl.value) {
      context.projectTemplateSelectEl.value = '';
      try {
        await loadSelectedTemplate(context);
      } catch (error) {
        context.restoreEditorState(previousEditorState);
        context.showAlert('danger', context.escapeHtml(error.message));
      }
    }
    context.updateLoadButtonState();
  });

  context.btnValidate.addEventListener('click', async () => {
    try {
      await validateCurrent(context);
    } catch (error) {
      context.showAlert('danger', context.escapeHtml(error.message));
    }
  });

  context.btnSave.addEventListener('click', async () => {
    try {
      await saveCurrent(context);
    } catch (error) {
      context.showAlert('danger', context.escapeHtml(error.message));
    }
  });

  context.btnDownload.addEventListener('click', async () => {
    try {
      await downloadCurrent(context);
    } catch (error) {
      context.showAlert('danger', context.escapeHtml(error.message));
    }
  });

  if (context.btnDelete) {
    context.btnDelete.addEventListener('click', async () => {
      try {
        await deleteCurrentTemplate(context);
      } catch (error) {
        context.showAlert('danger', context.escapeHtml(error.message));
      }
    });
  }

  window.addEventListener('prism-project-changed', async () => {
    const previousProjectPath = context.editorProjectContextPath;
    context.invalidateProjectContextRequests();
    const nextProjectPath = context.getCurrentProjectPath();
    try {
      await refreshTemplateList(context, { silent: true });
      context.handleProjectContextChange(previousProjectPath, nextProjectPath);
    } catch (error) {
      context.showAlert('danger', context.escapeHtml(error.message));
    }
  });
}

export async function initializeTemplateEditorSourceWorkflow(context) {
  await context.refreshSchema();
  await refreshTemplateList(context);
  context.projectTemplateSelectEl.value = '';
  context.globalTemplateSelectEl.value = '';
  context.updateLoadButtonState();
  await loadNewTemplate(context);
}