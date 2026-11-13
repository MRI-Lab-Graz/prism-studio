/**
 * Item map dialog: shows the backend's guess (which survey column holds which template item)
 * and lets the user change it. No matching happens here; the suggest route decides, the save
 * route writes. Only UI state lives in this file.
 */

const used = (rows) => new Set(rows.map((row) => row.column).filter(Boolean));

/** The item's own column plus every column no other row uses. */
export function columnsFor(item, rows, columns) {
    const taken = used(rows.filter((row) => row.item !== item));
    return columns.filter((column) => !taken.has(column));
}

export function choicesToSend(rows) {
    return Object.fromEntries(rows.map((row) => [row.item, row.column || '']));
}

export function unmappedItems(rows) {
    return rows.filter((row) => !row.column).map((row) => row.item);
}

const WARN_WHY = new Set(['order', 'none']);

/**
 * `root` is a Bootstrap modal element with data-role="title" | "intro" | "task" | "rows" |
 * "unused" | "unmapped" | "status" | "cancel" | "save". `post(url, formData)` resolves to the JSON
 * answer and throws on an error answer. `open` resolves true after a save, false on cancel,
 * and null when no task of the file needs a map (nothing is shown).
 */
export function createItemMapDialog({ root, post }) {
    const part = (role) => root.querySelector(`[data-role="${role}"]`);
    const [title, taskSelect, rowsEl, unusedEl, unmappedEl, status, cancelBtn, saveBtn] =
        ['title', 'task', 'rows', 'unused', 'unmapped', 'status', 'cancel', 'save'].map(part);
    let state = null; // {file, projectPath, task, rows, columns}
    let settle = null;

    const form = (extra = {}) => {
        const data = new FormData();
        data.append('file', state.file);
        data.append('project_path', state.projectPath || '');
        for (const [key, value] of Object.entries(extra)) data.append(key, value);
        return data;
    };

    function render() {
        const { rows, columns } = state;
        title.textContent = `Match survey columns to template "${state.task}"`;
        rowsEl.replaceChildren(...rows.map((row) => {
            const line = document.createElement('div');
            line.className = 'input-group input-group-sm mb-1';
            const name = document.createElement('span');
            name.className = 'input-group-text font-monospace';
            name.textContent = row.item;
            const select = document.createElement('select');
            select.className = 'form-select';
            select.setAttribute('aria-label', `Column for ${row.item}`);
            const none = new Option('- none -', '');
            select.append(none, ...columnsFor(row.item, rows, columns).map((column) => new Option(column, column)));
            select.value = row.column || '';
            select.addEventListener('change', () => {
                row.column = select.value || null;
                row.why = row.column ? 'saved' : 'none';
                render();
            });
            const mark = document.createElement('span');
            mark.className = WARN_WHY.has(row.why) ? 'input-group-text bg-warning text-dark' : 'input-group-text';
            mark.textContent = row.why;
            line.append(name, select, mark);
            return line;
        }));
        const free = columnsFor(null, rows, columns);
        unusedEl.textContent = `Columns not used: ${free.length ? free.join(', ') : '(none)'}`;
        const left = unmappedItems(rows);
        unmappedEl.textContent = left.length ? `Left unmapped: ${left.join(', ')}` : '';
        unmappedEl.classList.toggle('d-none', left.length === 0);
    }

    async function loadTask(task) {
        const data = await post('/api/item-map/suggest', form({ task }));
        state.task = task;
        state.rows = data.rows;
        state.columns = data.columns;
        status.textContent = '';
        render();
    }

    const modal = () => window.bootstrap.Modal.getOrCreateInstance(root);
    const finish = (result) => {
        if (!settle) return;
        const done = settle;
        settle = null;
        done(result);
    };

    taskSelect.addEventListener('change', () => loadTask(taskSelect.value).catch((e) => { status.textContent = e.message; }));
    cancelBtn.addEventListener('click', () => modal().hide());
    root.addEventListener('hidden.bs.modal', () => finish(false));
    saveBtn.addEventListener('click', async () => {
        saveBtn.disabled = true;
        try {
            await post('/api/item-map', form({ task: state.task, choices: JSON.stringify(choicesToSend(state.rows)) }));
            finish(true);
            modal().hide();
        } catch (error) {
            status.textContent = error.message;
        } finally {
            saveBtn.disabled = false;
        }
    });

    return {
        async open(file, projectPath) {
            if (settle) return null; // already open: the first call keeps its promise
            state = { file, projectPath, task: '', rows: [], columns: [] };
            const { tasks } = await post('/api/item-map/suggest', form());
            if (!tasks || tasks.length === 0) return null;
            taskSelect.replaceChildren(...tasks.map((task) => new Option(task, task)));
            taskSelect.closest('[data-role="task-group"]')?.classList.toggle('d-none', tasks.length < 2);
            await loadTask(tasks[0]);
            return new Promise((resolve) => {
                settle = resolve;
                modal().show();
            });
        },
    };
}
