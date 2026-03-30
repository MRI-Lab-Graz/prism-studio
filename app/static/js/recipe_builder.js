/**
 * Recipe Builder – interactive recipe authoring UI.  v2
 *
 * State:
 *   state.allItems        – all item IDs from selected template (string[])
 *   state.inverted        – Set of items that are reverse-coded (global, across all scales)
 *   state.invertMin/Max   – inversion scale range
 *   state.selectedItems   – Set of items checked in pool (multi-select)
 *   state.currentVariation– "" for default, or a VersionedScores key
 *   state.scales          – { [variation]: Scale[] }
 *
 * Scale: { id, name, method, description, items: string[] }
 *
 * Items are EXCLUSIVE per variation: once placed in any scale of the
 * current variation they disappear from the pool.  Removing a chip
 * returns the item to the pool.
 */

'use strict';

function _escHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

document.addEventListener('DOMContentLoaded', function () {

    const root = document.getElementById('recipeBuilderRoot');
    if (!root) return;

    // ── Element refs ──────────────────────────────────────────────────────
    const surveyPicker       = document.getElementById('rbSurveyPicker');
    const includeGlobalToggle= document.getElementById('rbIncludeGlobal');
    const variationRow       = document.getElementById('rbVariationRow');
    const variationSelect    = document.getElementById('rbVariationSelect');
    const addVariationBtn    = document.getElementById('rbAddVariationBtn');
    const removeVariationBtn = document.getElementById('rbRemoveVariationBtn');
    const inversionBox        = document.getElementById('rbInversionBox');
    const invertScaleDisplay = document.getElementById('rbScaleRangeDisplay');
    const invertSearch       = document.getElementById('rbInvertSearch');
    const invertClearBtn     = document.getElementById('rbInvertClearBtn');
    const invertItemList     = document.getElementById('rbInvertItemList');
    const invertedCountBadge = document.getElementById('rbInvertedCount');
    const builderArea        = document.getElementById('rbBuilderArea');
    const itemList           = document.getElementById('rbItemList');
    const itemCount          = document.getElementById('rbItemCount');
    const itemSearch         = document.getElementById('rbItemSearch');
    const selectionHint      = document.getElementById('rbSelectionHint');
    const selectAllBtn       = document.getElementById('rbSelectAllBtn');
    const scaleCanvas        = document.getElementById('rbScaleCanvas');
    const addScaleBtn        = document.getElementById('rbAddScaleBtn');
    const saveBtn            = document.getElementById('rbSaveBtn');
    const previewBtn         = document.getElementById('rbPreviewBtn');
    const statusEl           = document.getElementById('rbStatus');
    const emptyState         = document.getElementById('rbEmptyState');

    const jsonModal          = new bootstrap.Modal(document.getElementById('rbJsonModal'));
    const jsonPreview        = document.getElementById('rbJsonPreview');
    const copyJsonBtn        = document.getElementById('rbCopyJsonBtn');

    const variationModal     = new bootstrap.Modal(document.getElementById('rbVariationModal'));
    const variationNameInput = document.getElementById('rbVariationName');
    const variationConfirmBtn= document.getElementById('rbVariationConfirmBtn');

    const scaleNameModal     = new bootstrap.Modal(document.getElementById('rbScaleNameModal'));
    const scaleNameInput     = document.getElementById('rbScaleNameInput');
    const scaleNameConfirm   = document.getElementById('rbScaleNameConfirmBtn');

    // ── State ─────────────────────────────────────────────────────────────
    let projectPath  = (window.currentProjectPath || root.dataset.currentProjectPath || '').trim();
    let selectedTask = '';

    const state = {
        allItems:         [],           // string[]
        inverted:         new Set(),    // globally reverse-coded item IDs
        invertMin:        1,
        invertMax:        7,
        scaleRanges:      {},           // { [variantId]: {min, max} } — auto-detected from template
        itemRanges:       {},           // { itemId: { "": {min,max}, variantId: {min,max} } }
        selectedItems:    new Set(),    // items checked in the item pool
        activeScaleId:    null,         // id of the currently focused scale card (or null)
        currentVariation: '',
        scales:           { '': [] },   // { [variation]: Scale[] }
    };

    let _idCounter = 0;
    function newId() { return ++_idCounter; }

    // ── Helpers ───────────────────────────────────────────────────────────
    function resolveProjectPath() {
        if (typeof window.resolveCurrentProjectPath === 'function') {
            const p = window.resolveCurrentProjectPath();
            if (p) return p;
        }
        return projectPath;
    }

    function showStatus(msg, type = 'success') {
        statusEl.innerHTML = `<div class="alert alert-${type} py-1 px-2 small">${msg}</div>`;
        if (type === 'success') setTimeout(() => { statusEl.innerHTML = ''; }, 4000);
    }

    /** Items assigned to any scale in the current variation. */
    function assignedItems() {
        const s = new Set();
        (state.scales[state.currentVariation] || []).forEach(sc => sc.items.forEach(it => s.add(it)));
        return s;
    }

    /** Items available in the pool, optionally filtered.
     *  When a scale is active, items already in that scale are hidden.
     *  If no scale is active, all items are shown. */
    function poolItems(filter) {
        const lc = (filter || '').toLowerCase();
        const activeScale = state.activeScaleId != null
            ? currentScales().find(s => s.id === state.activeScaleId)
            : null;
        const excluded = activeScale ? new Set(activeScale.items) : new Set();
        return state.allItems.filter(it => !excluded.has(it) && (!lc || it.toLowerCase().includes(lc)));
    }

    function currentScales() {
        const v = state.currentVariation;
        if (!state.scales[v]) state.scales[v] = [];
        return state.scales[v];
    }

    function showBuilderArea(visible) {
        if (visible) {
            builderArea.style.removeProperty('display');
            inversionBox.style.removeProperty('display');
            variationRow.style.removeProperty('display');
            emptyState.style.display = 'none';
        } else {
            builderArea.style.setProperty('display', 'none', 'important');
            inversionBox.style.display = 'none';
            variationRow.style.setProperty('display', 'none', 'important');
            emptyState.style.display = '';
        }
    }

    // ── Survey picker ─────────────────────────────────────────────────────
    function loadSurveyList() {
        const path = resolveProjectPath();
        if (!path) return;
        const includeGlobal = includeGlobalToggle && includeGlobalToggle.checked ? '&include_global=1' : '';
        fetch('/api/recipe-builder/surveys?dataset_path=' + encodeURIComponent(path) + includeGlobal)
            .then(r => r.json())
            .then(data => {
                const surveys = data.surveys || [];
                surveyPicker.innerHTML = '';
                if (surveys.length === 0) {
                    const opt = document.createElement('option');
                    opt.value    = '';
                    opt.textContent = '— no survey templates found in project library —';
                    opt.disabled = true;
                    opt.selected = true;
                    surveyPicker.appendChild(opt);
                } else {
                    const placeholder = document.createElement('option');
                    placeholder.value       = '';
                    placeholder.textContent = '— select a survey template —';
                    surveyPicker.appendChild(placeholder);
                    // Group by source if mixed
                    const hasOfficial = surveys.some(s => s.source === 'official');
                    const hasProject  = surveys.some(s => s.source === 'project');
                    if (hasOfficial && hasProject) {
                        const projGroup = document.createElement('optgroup');
                        projGroup.label = 'Project library';
                        const offGroup  = document.createElement('optgroup');
                        offGroup.label  = 'Official library';
                        surveys.forEach(s => {
                            const opt = document.createElement('option');
                            opt.value       = s.task;
                            opt.textContent = s.task + '  (' + s.file + ')';
                            (s.source === 'official' ? offGroup : projGroup).appendChild(opt);
                        });
                        if (projGroup.children.length) surveyPicker.appendChild(projGroup);
                        if (offGroup.children.length)  surveyPicker.appendChild(offGroup);
                    } else {
                        surveys.forEach(s => {
                            const opt = document.createElement('option');
                            opt.value       = s.task;
                            opt.textContent = s.task + '  (' + s.file + ')';
                            surveyPicker.appendChild(opt);
                        });
                    }
                }
                // Do NOT auto-load — user must explicitly pick a template
            })
            .catch(() => {
                surveyPicker.innerHTML = '<option value="" disabled selected>— failed to load templates —</option>';
            });
    }

    surveyPicker.addEventListener('change', function () {
        selectedTask = this.value;
        if (!selectedTask) { showBuilderArea(false); return; }
        loadItemsAndRecipe(selectedTask);
    });

    includeGlobalToggle && includeGlobalToggle.addEventListener('change', () => {
        loadSurveyList();
        showBuilderArea(false);
    });

    function loadItemsAndRecipe(task) {
        const path = resolveProjectPath();
        const includeGlobal = includeGlobalToggle && includeGlobalToggle.checked ? '&include_global=1' : '';

        // Immediately clear the builder to avoid stale state showing briefly
        showBuilderArea(false);
        scaleCanvas.innerHTML = '';
        itemList.innerHTML    = '';

        Promise.all([
            fetch('/api/recipe-builder/items?task=' + encodeURIComponent(task) +
                  '&dataset_path=' + encodeURIComponent(path) + includeGlobal).then(r => r.json()),
            fetch('/api/recipe-builder/load?task=' + encodeURIComponent(task) +
                  '&dataset_path=' + encodeURIComponent(path)).then(r => r.json()),
        ]).then(([itemsData, recipeData]) => {
            // Full state reset
            state.allItems         = itemsData.items || [];
            state.inverted         = new Set();
            state.scaleRanges      = itemsData.scale_ranges || {};
            state.itemRanges       = itemsData.item_ranges  || {};
            state.selectedItems    = new Set();
            state.activeScaleId    = null;
            state.currentVariation = '';
            state.scales           = { '': [] };
            _applyScaleForVariation('');

            // Clear metadata fields
            document.getElementById('rbMetaName').value     = '';
            document.getElementById('rbMetaDesc').value     = '';
            document.getElementById('rbMetaCitation').value = '';
            document.getElementById('rbMetaDoi').value      = '';

            // Import recipe BEFORE any rendering
            if (recipeData.recipe) {
                importRecipe(recipeData.recipe);
                showStatus('<i class="fas fa-file-import me-1"></i>Existing recipe loaded.', 'info');
            } else {
                statusEl.innerHTML = '';
            }

            // Now render with fully populated state
            resetVariationSelect();
            renderInversionBox();
            renderItemList();
            renderScaleCanvas();
            showBuilderArea(true);
        }).catch(() => showStatus('Failed to load survey data.', 'danger'));
    }

    // ── Import existing recipe ────────────────────────────────────────────
    function importRecipe(recipe) {
        const s = recipe.Survey || {};
        document.getElementById('rbMetaName').value     = s.Name        || '';
        document.getElementById('rbMetaDesc').value     = s.Description || '';
        document.getElementById('rbMetaCitation').value = s.Citation    || '';
        document.getElementById('rbMetaDoi').value      = s.DOI         || '';

        const inv = (recipe.Transforms || {}).Invert || {};
        // Scale range is auto-detected from the template — ignore recipe's stored Scale
        (inv.Items || []).forEach(it => state.inverted.add(it));

        state.scales[''] = (recipe.Scores || []).map(scoreToScale);

        const vs = recipe.VersionedScores || {};
        Object.entries(vs).forEach(([key, scores]) => {
            state.scales[key] = scores.map(scoreToScale);
        });
    }

    function scoreToScale(score) {
        return {
            id:          newId(),
            name:        score.Name        || '',
            method:      score.Method      || 'mean',
            description: score.Description || '',
            items:       score.Items       || [],
        };
    }

    function scaleToScore(scale) {
        const score = { Name: scale.name, Method: scale.method, Items: scale.items };
        if (scale.description) score.Description = scale.description;
        return score;
    }

    // ── Variation dropdown ────────────────────────────────────────────────
    function resetVariationSelect() {
        variationSelect.innerHTML = '';
        addVariationOption('', 'default');
        Object.keys(state.scales).filter(k => k !== '').forEach(k => addVariationOption(k, k));
        // Update DOM only, no re-render (caller will render after this)
        state.currentVariation = '';
        variationSelect.value  = '';
        removeVariationBtn.style.display = 'none';
    }

    function addVariationOption(key, label) {
        const opt       = document.createElement('option');
        opt.value       = key;
        opt.textContent = label;
        variationSelect.appendChild(opt);
    }

    function setActiveVariation(key) {
        state.currentVariation  = key;
        state.activeScaleId     = null;
        if (!state.scales[key]) state.scales[key] = [];
        variationSelect.value   = key;
        removeVariationBtn.style.display = key !== '' ? '' : 'none';
        state.selectedItems.clear();
        _applyScaleForVariation(key);
        renderInversionBox();
        renderItemList();
        renderScaleCanvas();
    }

    variationSelect.addEventListener('change', function () {
        setActiveVariation(this.value);
    });

    addVariationBtn.addEventListener('click', () => {
        variationNameInput.value = '';
        variationNameInput.classList.remove('is-invalid');
        variationModal.show();
        setTimeout(() => variationNameInput.focus(), 300);
    });

    variationConfirmBtn.addEventListener('click', () => {
        const name = variationNameInput.value.trim();
        if (!name || state.scales[name] !== undefined) {
            variationNameInput.classList.add('is-invalid');
            return;
        }
        state.scales[name] = [];
        addVariationOption(name, name);
        variationModal.hide();
        setActiveVariation(name);
    });

    document.getElementById('rbVariationModal').addEventListener('keydown', e => {
        if (e.key === 'Enter') variationConfirmBtn.click();
    });

    removeVariationBtn.addEventListener('click', () => {
        const key = state.currentVariation;
        if (!key) return;
        if (!confirm('Remove variation "' + key + '"?')) return;
        delete state.scales[key];
        const opt = variationSelect.querySelector('option[value="' + CSS.escape(key) + '"]');
        if (opt) opt.remove();
        setActiveVariation('');
    });

    // ── Inversion box ─────────────────────────────────────────────────────
    function renderInversionBox() {
        const filter = (invertSearch ? invertSearch.value : '').toLowerCase();
        const items  = state.allItems.filter(it => !filter || it.toLowerCase().includes(filter));
        invertItemList.innerHTML = '';
        items.forEach(item => {
            const label = document.createElement('label');
            label.className = 'rb-invert-item' + (state.inverted.has(item) ? ' is-inverted' : '');
            label.title = itemTitle(item);

            const cb  = document.createElement('input');
            cb.type    = 'checkbox';
            cb.checked = state.inverted.has(item);
            cb.addEventListener('change', () => {
                if (cb.checked) state.inverted.add(item); else state.inverted.delete(item);
                label.classList.toggle('is-inverted', cb.checked);
                label.title = itemTitle(item);
                updateInvertedBadge();
                renderScaleCanvas(); // refresh chip colours
            });

            const text       = document.createElement('span');
            text.textContent = item;
            label.append(cb, text);
            invertItemList.appendChild(label);
        });
        updateInvertedBadge();
    }

    // Tooltip for any item: shows range; if inverted, shows the mapping.
    function itemTitle(itemId) {
        const r = getItemRange(itemId);
        if (state.inverted.has(itemId)) return invertedTitle(itemId);
        if (!r) return '';
        return 'Range: ' + r.min + '–' + r.max;
    }

    function updateInvertedBadge() {
        if (invertedCountBadge) invertedCountBadge.textContent = state.inverted.size + ' inverted';
    }

    invertSearch  && invertSearch.addEventListener('input',  () => renderInversionBox());

    invertClearBtn.addEventListener('click', () => {
        state.inverted.clear();
        renderInversionBox();
        renderScaleCanvas();
    });

    function _updateScaleDisplay() {
        if (!invertScaleDisplay) return;
        // If items have varying ranges for this variation, show 'varies by item'
        const vid = state.currentVariation;
        const ranges = state.allItems.map(id => {
            const ir = state.itemRanges[id] || {};
            return ir[vid] || ir[''] || null;
        }).filter(Boolean);
        const unique = new Set(ranges.map(r => r.min + ',' + r.max));
        if (unique.size > 1) {
            invertScaleDisplay.textContent = 'varies by item';
        } else {
            invertScaleDisplay.textContent = state.invertMin + ' – ' + state.invertMax;
        }
    }

    // Return the range for a specific item under the active variation.
    function getItemRange(itemId) {
        const vid = state.currentVariation;
        const ir  = state.itemRanges[itemId] || {};
        return ir[vid] || ir[''] || null;
    }

    // Build an inversion preview title for an item (e.g. "Inverted (1–5): 1→5, 2→4, ...").
    function invertedTitle(itemId) {
        const r = getItemRange(itemId);
        if (!r) return 'Inverted';
        const {min, max} = r;
        const steps = max - min;
        if (steps >= 1 && steps <= 10 && Number.isInteger(min) && Number.isInteger(max)) {
            const parts = [];
            for (let i = min; i <= max; i++) parts.push(i + '→' + (min + max - i));
            return 'Inverted (' + min + '–' + max + '): ' + parts.join(', ');
        }
        return 'Inverted (' + min + '–' + max + '): ' + min + '+' + max + '−value';
    }

    function _applyScaleForVariation(key) {
        // Prefer exact variant match, then fall back to default (""), then hardcoded 1-7
        const sr = state.scaleRanges[key] || state.scaleRanges[''] || null;
        state.invertMin = sr ? sr.min : 1;
        state.invertMax = sr ? sr.max : 7;
        _updateScaleDisplay();
    }

    // ── Item pool ─────────────────────────────────────────────────────────
    function renderItemList() {
        const filter  = itemSearch ? itemSearch.value : '';
        const visible = poolItems(filter);

        // Remove selections that dropped out of the pool
        const poolSet = new Set(poolItems());
        state.selectedItems.forEach(it => { if (!poolSet.has(it)) state.selectedItems.delete(it); });

        itemCount.textContent = visible.length;
        itemList.innerHTML    = '';

        // Hint when no scale is active
        if (state.activeScaleId == null && currentScales().length > 0) {
            const hint = document.createElement('li');
            hint.className = 'text-muted small fst-italic px-1 py-2';
            hint.textContent = 'Click a scale to filter available items.';
            itemList.appendChild(hint);
        }

        visible.forEach(item => {
            const li        = document.createElement('li');
            li.className    = 'rb-item' + (state.selectedItems.has(item) ? ' rb-item--selected' : '');
            li.dataset.item = item;
            li.draggable    = true;

            const cb      = document.createElement('input');
            cb.type       = 'checkbox';
            cb.className  = 'rb-item-cb';
            cb.checked    = state.selectedItems.has(item);
            cb.addEventListener('change', e => {
                e.stopPropagation();
                if (cb.checked) state.selectedItems.add(item); else state.selectedItems.delete(item);
                li.classList.toggle('rb-item--selected', cb.checked);
                updateSelectionHint();
            });

            const name       = document.createElement('span');
            name.className   = 'rb-item-name';
            name.textContent = item;

            // Clicking the row toggles the checkbox
            li.addEventListener('click', e => {
                if (e.target === cb) return;
                cb.checked = !cb.checked;
                cb.dispatchEvent(new Event('change'));
            });

            // Drag: carry selected set, or this single item if not selected
            li.addEventListener('dragstart', e => {
                const items = state.selectedItems.has(item) ? [...state.selectedItems] : [item];
                e.dataTransfer.setData('application/rb-items', JSON.stringify(items));
                e.dataTransfer.setData('text/plain', item);
                e.dataTransfer.effectAllowed = 'move';
            });

            li.append(cb, name);
            itemList.appendChild(li);
        });

        updateSelectionHint();
    }

    function updateSelectionHint() {
        const n = state.selectedItems.size;
        if (selectionHint) selectionHint.textContent = n > 0 ? n + ' selected' : '';
    }

    itemSearch  && itemSearch.addEventListener('input', () => {
        state.selectedItems.clear();
        renderItemList();
    });

    selectAllBtn.addEventListener('click', () => {
        const filter  = itemSearch ? itemSearch.value : '';
        const visible = poolItems(filter);
        const allSel  = visible.every(it => state.selectedItems.has(it));
        if (allSel) {
            visible.forEach(it => state.selectedItems.delete(it));
        } else {
            visible.forEach(it => state.selectedItems.add(it));
        }
        renderItemList();
    });

    // ── Scale canvas ──────────────────────────────────────────────────────
    function renderScaleCanvas() {
        scaleCanvas.innerHTML = '';
        currentScales().forEach(scale => renderScaleCard(scale));
        initSortable();
    }

    function initSortable() {
        if (typeof Sortable === 'undefined') return;
        Sortable.create(scaleCanvas, {
            animation: 150,
            handle: '.rb-scale-drag-handle',
            onEnd: () => {
                const ids = [...scaleCanvas.querySelectorAll('.rb-scale-card')]
                    .map(c => parseInt(c.dataset.scaleId, 10));
                const scales    = currentScales();
                state.scales[state.currentVariation] = ids
                    .map(id => scales.find(s => s.id === id))
                    .filter(Boolean);
            },
        });
    }

    function renderScaleCard(scale) {
        const card      = document.createElement('div');
        card.className  = 'rb-scale-card mb-2';
        card.dataset.scaleId = scale.id;

        if (state.activeScaleId === scale.id) card.classList.add('rb-scale-card--active');

        // ── Full-width accordion-style header (entire bar is click target) ──
        const header   = document.createElement('div');
        header.className = 'rb-scale-header';
        header.title   = 'Click to select — item pool will show only items available for this scale';

        header.addEventListener('click', e => {
            if (e.target.closest('button')) return;   // only let the × button through
            const wasActive = state.activeScaleId === scale.id;
            state.activeScaleId = wasActive ? null : scale.id;
            scaleCanvas.querySelectorAll('.rb-scale-card').forEach(c => {
                c.classList.toggle('rb-scale-card--active', +c.dataset.scaleId === state.activeScaleId);
            });
            state.selectedItems.clear();
            renderItemList();
        });

        const dragHandle = document.createElement('span');
        dragHandle.className = 'rb-scale-drag-handle text-muted flex-shrink-0';
        dragHandle.style.cursor = 'grab';
        dragHandle.innerHTML = '<i class="fas fa-grip-vertical"></i>';

        // Name shown as plain text in header (editing moved to body)
        const nameLabel = document.createElement('span');
        nameLabel.className = 'rb-scale-name-label flex-grow-1 fw-semibold text-truncate';
        nameLabel.textContent = scale.name || 'unnamed scale';

        const chevron = document.createElement('span');
        chevron.className = 'rb-scale-chevron text-muted ms-auto me-1 flex-shrink-0';
        chevron.innerHTML = '<i class="fas fa-chevron-down fa-xs"></i>';

        const removeBtn      = document.createElement('button');
        removeBtn.className  = 'btn btn-sm btn-link text-danger p-0 flex-shrink-0';
        removeBtn.title      = 'Remove scale';
        removeBtn.innerHTML  = '<i class="fas fa-times"></i>';
        removeBtn.addEventListener('click', () => {
            const idx = currentScales().findIndex(s => s.id === scale.id);
            if (idx !== -1) currentScales().splice(idx, 1);
            if (state.activeScaleId === scale.id) state.activeScaleId = null;
            card.remove();
            renderItemList();
        });

        header.append(dragHandle, nameLabel, chevron, removeBtn);

        // ── Body ──
        const body      = document.createElement('div');
        body.className  = 'rb-scale-body';

        // Name input at top of body
        const nameRow = document.createElement('div');
        nameRow.className = 'rb-scale-name-row';
        const nameInput      = document.createElement('input');
        nameInput.type       = 'text';
        nameInput.className  = 'form-control form-control-sm rb-scale-name-input';
        nameInput.placeholder = 'scale_name';
        nameInput.value      = scale.name;
        nameInput.addEventListener('input', () => {
            scale.name = nameInput.value;
            nameLabel.textContent = nameInput.value || 'unnamed scale';
        });
        nameRow.appendChild(nameInput);

        // Method row
        const methodRow = document.createElement('div');
        methodRow.className = 'rb-scale-method-row';

        const methodLabel = document.createElement('span');
        methodLabel.className = 'text-muted small';
        methodLabel.textContent = 'Method:';

        const methodSelect   = document.createElement('select');
        methodSelect.className = 'form-select form-select-sm rb-scale-method';
        ['mean', 'sum', 'median', 'count'].forEach(m => {
            const opt   = document.createElement('option');
            opt.value   = m;
            opt.textContent = m;
            if (m === scale.method) opt.selected = true;
            methodSelect.appendChild(opt);
        });
        methodSelect.addEventListener('change', () => { scale.method = methodSelect.value; });
        methodRow.append(methodLabel, methodSelect);

        const dropZone  = document.createElement('div');
        dropZone.className = 'rb-scale-drop-zone';
        scale.items.forEach(item => appendChip(dropZone, scale, item));

        dropZone.addEventListener('dragover', e => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            dropZone.classList.add('drag-over');
        });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
        dropZone.addEventListener('drop', e => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            let items;
            try   { items = JSON.parse(e.dataTransfer.getData('application/rb-items')); }
            catch { const p = e.dataTransfer.getData('text/plain'); items = p ? [p] : []; }
            items.forEach(item => {
                if (!scale.items.includes(item)) {
                    scale.items.push(item);
                    appendChip(dropZone, scale, item);
                }
            });
            state.selectedItems.clear();
            renderItemList();
        });

        // "Add selected" button
        const addSelBtn     = document.createElement('button');
        addSelBtn.type      = 'button';
        addSelBtn.className = 'rb-add-selected-btn btn btn-sm btn-outline-primary w-100 mt-1';
        addSelBtn.innerHTML = '<i class="fas fa-plus me-1"></i>Add selected';
        addSelBtn.addEventListener('click', () => {
            const toAdd = [...state.selectedItems].filter(it => !scale.items.includes(it));
            toAdd.forEach(item => { scale.items.push(item); appendChip(dropZone, scale, item); });
            state.selectedItems.clear();
            renderItemList();
        });

        const descInput     = document.createElement('input');
        descInput.type      = 'text';
        descInput.className = 'form-control form-control-sm rb-scale-desc-input mt-1';
        descInput.placeholder = 'Scale description (optional)';
        descInput.value     = scale.description;
        descInput.addEventListener('input', () => { scale.description = descInput.value; });

        body.append(nameRow, methodRow, dropZone, addSelBtn, descInput);
        card.append(header, body);
        scaleCanvas.appendChild(card);
    }

    function appendChip(dropZone, scale, item) {
        const chip      = document.createElement('span');
        chip.className  = 'rb-chip' + (state.inverted.has(item) ? ' rb-chip--inverted' : '');

        const label       = document.createElement('span');
        label.textContent = item;
        if (state.inverted.has(item)) {
            label.title = invertedTitle(item);
            chip.title  = invertedTitle(item);
        }

        const removeBtn     = document.createElement('button');
        removeBtn.className = 'rb-chip-remove';
        removeBtn.innerHTML = '&times;';
        removeBtn.title     = 'Remove item';
        removeBtn.addEventListener('click', () => {
            const idx = scale.items.indexOf(item);
            if (idx !== -1) scale.items.splice(idx, 1);
            chip.remove();
            renderItemList(); // return item to pool
        });

        chip.append(label, removeBtn);
        dropZone.appendChild(chip);
    }

    addScaleBtn.addEventListener('click', () => {
        scaleNameInput.value = '';
        scaleNameInput.classList.remove('is-invalid');
        scaleNameModal.show();
        setTimeout(() => scaleNameInput.focus(), 300);
    });

    scaleNameConfirm.addEventListener('click', () => {
        const name = scaleNameInput.value.trim();
        if (!name) { scaleNameInput.classList.add('is-invalid'); return; }
        const scale = { id: newId(), name, method: 'mean', description: '', items: [] };
        currentScales().push(scale);
        renderScaleCard(scale);
        initSortable();
        scaleNameModal.hide();
    });

    document.getElementById('rbScaleNameModal').addEventListener('keydown', e => {
        if (e.key === 'Enter') scaleNameConfirm.click();
    });

    // ── Build recipe JSON ─────────────────────────────────────────────────
    function buildRecipeJSON() {
        const name = document.getElementById('rbMetaName').value.trim();
        const desc = document.getElementById('rbMetaDesc').value.trim();
        const cite = document.getElementById('rbMetaCitation').value.trim();
        const doi  = document.getElementById('rbMetaDoi').value.trim();

        const recipe = {
            RecipeVersion: '1.0',
            Kind:    'survey',
            Survey:  { TaskName: selectedTask },
        };
        if (name) recipe.Survey.Name        = name;
        if (desc) recipe.Survey.Description = desc;
        if (cite) recipe.Survey.Citation    = cite;
        if (doi)  recipe.Survey.DOI         = doi;

        if (state.inverted.size > 0) {
            // Global fallback scale (most common range across inverted items)
            const invertedArr = [...state.inverted];
            const vid = state.currentVariation;
            const itemScales = {};
            invertedArr.forEach(id => {
                const r = getItemRange(id);
                if (r) itemScales[id] = { min: r.min, max: r.max };
            });
            // Compute the most common range as the fallback Scale
            const freq = {};
            Object.values(itemScales).forEach(r => {
                const k = r.min + ',' + r.max;
                freq[k] = (freq[k] || 0) + 1;
            });
            let bestKey = Object.keys(freq).sort((a, b) => freq[b] - freq[a])[0];
            let globalScale;
            if (bestKey) {
                const [mn, mx] = bestKey.split(',').map(Number);
                globalScale = { min: mn, max: mx };
            } else {
                globalScale = { min: state.invertMin, max: state.invertMax };
            }
            // Only include ItemScales when ranges actually differ
            const uniqueRanges = new Set(Object.values(itemScales).map(r => r.min + ',' + r.max));
            const invert = {
                Scale: globalScale,
                Items: invertedArr,
            };
            if (uniqueRanges.size > 1) invert.ItemScales = itemScales;
            recipe.Transforms = { Invert: invert };
        }

        const defaultScales = state.scales[''] || [];
        if (defaultScales.length > 0) recipe.Scores = defaultScales.map(scaleToScore);

        const versionedKeys = Object.keys(state.scales).filter(k => k !== '' && (state.scales[k] || []).length > 0);
        if (versionedKeys.length > 0) {
            recipe.VersionedScores = {};
            versionedKeys.forEach(k => { recipe.VersionedScores[k] = state.scales[k].map(scaleToScore); });
        }

        return recipe;
    }

    // ── Preview ───────────────────────────────────────────────────────────
    previewBtn.addEventListener('click', () => {
        jsonPreview.textContent = JSON.stringify(buildRecipeJSON(), null, 2);
        jsonModal.show();
    });

    copyJsonBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(jsonPreview.textContent)
            .then(() => {
                copyJsonBtn.innerHTML = '<i class="fas fa-check me-1"></i>Copied!';
                setTimeout(() => { copyJsonBtn.innerHTML = '<i class="fas fa-copy me-1"></i>Copy'; }, 2000);
            })
            .catch(() => {});
    });

    // ── Save ──────────────────────────────────────────────────────────────
    saveBtn.addEventListener('click', () => {
        const path = resolveProjectPath();
        if (!path)         { showStatus('No project loaded.', 'warning');   return; }
        if (!selectedTask) { showStatus('No survey selected.', 'warning');  return; }

        const recipe = buildRecipeJSON();
        saveBtn.disabled = true;

        fetch('/api/recipe-builder/save', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ dataset_path: path, task: selectedTask, recipe }),
        })
        .then(r => r.json())
        .then(data => {
            if (data.error) showStatus('Error: ' + _escHtml(data.error), 'danger');
            else            showStatus('Saved to <code>' + _escHtml(data.path || '') + '</code>', 'success');
        })
        .catch(() => showStatus('Network error while saving.', 'danger'))
        .finally(() => { saveBtn.disabled = false; });
    });

    // ── Init ──────────────────────────────────────────────────────────────
    showBuilderArea(false);
    loadSurveyList();
});
