// The Propose changes page: one choice of what is missing, then its panel. Presentation only: every action is a call to
// /api/spec/..., which runs the same functions as `prism_tools.py spec ...`. Project data (column names,
// paths, messages) is only ever written with textContent, never as HTML.
(function () {
    "use strict";

    const root = document.getElementById("spec-contribute");
    if (!root) return;
    const urls = {
        list: root.dataset.listUrl,
        add: root.dataset.addUrl,
        remove: root.dataset.removeUrl,
        addValues: root.dataset.addValuesUrl,
        removeValues: root.dataset.removeValuesUrl,
        propose: root.dataset.proposeUrl,
        catalog: root.dataset.catalogUrl,
        proposeValues: root.dataset.proposeValuesUrl,
    };
    const unknownBox = document.getElementById("spec-unknown");
    const localBox = document.getElementById("spec-local");
    const message = document.getElementById("spec-message");
    const dialog = document.getElementById("spec-propose-dialog");
    const shareAll = document.getElementById("spec-share-all");
    const valuesUnknownBox = document.getElementById("spec-values-unknown");
    const valuesLocalBox = document.getElementById("spec-values-local");
    const shareValues = document.getElementById("spec-share-values");
    const what = document.getElementById("spec-what");
    const panels = { values: document.getElementById("spec-panel-values"), metric: document.getElementById("spec-panel-metric") };
    const modalitySelect = document.getElementById("spec-v-modality");
    const listSelect = document.getElementById("spec-v-list");
    const allowedText = document.getElementById("spec-v-allowed");
    const mineBox = document.getElementById("spec-v-mine");
    const shareMine = document.getElementById("spec-v-share");
    const useMine = document.getElementById("spec-v-use");
    let catalog = { modalities: [], project_open: false };
    let mine = [];  // the choices collected on this page, not yet shared or used
    let currentProposal = null;

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    async function call(url, body) {
        const options = body === undefined ? {} : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        };
        const response = await fetch(url, options);
        let data = {};
        try { data = await response.json(); } catch (error) { data = { success: false, error: "Unexpected answer" }; }
        return { ok: response.ok && data.success !== false, data };
    }

    function say(text, kind) {
        message.className = "alert alert-" + kind;
        message.textContent = text;
    }

    function clearMessage() {
        message.className = "alert d-none";
        message.textContent = "";
    }

    function button(label, className, onClick) {
        const node = el("button", "btn btn-sm " + className, label);
        node.type = "button";
        node.addEventListener("click", onClick);
        return node;
    }

    function renderUnknown(metrics) {
        unknownBox.replaceChildren();
        if (!metrics.length) {
            unknownBox.appendChild(el("p", "text-muted small mb-0", "Nothing: every metric in your data is known."));
            return;
        }
        metrics.forEach(function (metric) {
            const row = el("div", "d-flex flex-wrap align-items-center gap-2 border-bottom py-2");
            row.appendChild(el("code", "", metric.column));
            const detail = [metric.specimen, metric.units].filter(Boolean).join(", ");
            if (detail) row.appendChild(el("span", "text-muted small", detail));
            if (metric.similar.length) {
                row.appendChild(el("span", "small", "Similar official terms: " + metric.similar.join(", ")));
            }
            const name = el("input", "form-control form-control-sm w-auto");
            name.type = "text";
            name.placeholder = "Name (optional)";
            name.setAttribute("aria-label", "Name for " + metric.column);
            row.appendChild(name);
            row.appendChild(button("Add to this project", "btn-primary", function () { add(metric, name.value.trim()); }));
            unknownBox.appendChild(row);
        });
    }

    function renderUnknownValues(values) {
        valuesUnknownBox.replaceChildren();
        if (!values.length) {
            valuesUnknownBox.appendChild(el("p", "text-muted small mb-0", "Nothing: every value in your data is allowed."));
            return;
        }
        values.forEach(function (found) {
            const row = el("div", "d-flex flex-wrap align-items-center gap-2 border-bottom py-2");
            row.appendChild(el("code", "", found.field));
            row.appendChild(el("code", "", found.value));
            row.appendChild(el("span", "text-muted small", found.sidecar.split(/[\\/]/).pop()));
            row.appendChild(button("Add to this project", "btn-primary", function () { addValues(found.field, [found.value]); }));
            valuesUnknownBox.appendChild(row);
        });
    }

    function renderLocalValues(items) {
        valuesLocalBox.replaceChildren();
        shareValues.classList.toggle("d-none", !items.some(function (item) { return item.status === "local"; }));
        if (!items.length) {
            valuesLocalBox.appendChild(el("p", "text-muted small mb-0", "None yet."));
            return;
        }
        const badge = { "local": "bg-success", "now-official": "bg-info", "invalid": "bg-warning text-dark" };
        items.forEach(function (item) {
            const row = el("div", "d-flex flex-wrap align-items-center gap-2 border-bottom py-2");
            row.appendChild(el("span", "badge " + (badge[item.status] || "bg-secondary"), item.status));
            row.appendChild(el("code", "", item.id || item.path));
            if (item.problem) row.appendChild(el("span", "small text-danger", item.problem));
            if (item.status === "now-official") {
                row.appendChild(el("span", "small text-muted", "Now official: edit " + item.path + " to remove it."));
            }
            if (item.field && item.value) {
                row.appendChild(button("Remove", "btn-outline-danger", function () { removeValue(item.field, item.value); }));
            }
            valuesLocalBox.appendChild(row);
        });
    }

    function renderLocal(items) {
        localBox.replaceChildren();
        shareAll.classList.toggle("d-none", !items.some(function (item) { return item.status === "local"; }));
        if (!items.length) {
            localBox.appendChild(el("p", "text-muted small mb-0", "None yet."));
            return;
        }
        const badge = { "local": "bg-success", "now-official": "bg-info", "invalid": "bg-warning text-dark" };
        items.forEach(function (item) {
            const row = el("div", "d-flex flex-wrap align-items-center gap-2 border-bottom py-2");
            row.appendChild(el("span", "badge " + (badge[item.status] || "bg-secondary"), item.status));
            row.appendChild(el("code", "", item.id || item.path));
            if (item.label && item.label !== item.id) row.appendChild(el("span", "small", item.label));
            if (item.problem) row.appendChild(el("span", "small text-danger", item.problem));
            if (item.status === "now-official") {
                row.appendChild(el("span", "small text-muted", "Now official: the official definition is used; you can remove this copy."));
            }
            if (item.status === "local") {
                row.appendChild(button("Share…", "btn-outline-primary", function () { propose({ id: item.id }); }));
            }
            if (item.id) {
                row.appendChild(button("Remove", "btn-outline-danger", function () { remove(item.id); }));
            }
            localBox.appendChild(row);
        });
    }

    async function refresh() {
        if (!catalog.project_open) return;
        const { ok, data } = await call(urls.list);
        if (!ok) {
            unknownBox.replaceChildren();
            localBox.replaceChildren();
            valuesUnknownBox.replaceChildren();
            valuesLocalBox.replaceChildren();
            say(data.error || "Could not read the project", "warning");
            return;
        }
        renderUnknown(data.unknown_metrics);
        renderLocal(data.items.filter(function (item) { return item.layer === 3; }));
        renderUnknownValues(data.unknown_values);
        renderLocalValues(data.items.filter(function (item) { return item.layer === 2; }));
    }

    async function add(metric, label) {
        clearMessage();
        const body = { data_file: metric.data_file, column: metric.column };
        if (label) body.label = label;
        const { ok, data } = await call(urls.add, body);
        if (!ok) { say(data.error || "Could not add the metric", "danger"); return; }
        say("Added to this project. Validate again to see it used.", "success");
        refresh();
    }

    async function addValues(field, values) {
        clearMessage();
        const { ok, data } = await call(urls.addValues, { field: field, values: values });
        if (!ok) { say(data.error || "Could not add the value", "danger"); return false; }
        say(data.skipped.length ? "Already official: nothing to add." : "Added to this project. Validate again to see it used.", data.skipped.length ? "info" : "success");
        refresh();
        return true;
    }

    async function removeValue(field, value) {
        if (!window.confirm("Remove " + value + " from the additions to " + field + " in this project?")) return;
        clearMessage();
        const { ok, data } = await call(urls.removeValues, { field: field, values: [value] });
        if (!ok) { say(data.error || "Could not remove it", "danger"); return; }
        say("Removed.", "success");
        refresh();
    }

    async function remove(id) {
        if (!window.confirm("Remove the local metric " + id + " from this project?")) return;
        clearMessage();
        const { ok, data } = await call(urls.remove, { id: id });
        if (!ok) { say(data.error || "Could not remove it", "danger"); return; }
        say("Removed.", "success");
        refresh();
    }

    async function propose(body, url) {
        clearMessage();
        const { ok, data } = await call(url || urls.propose, body);
        if (!ok) { say(data.error || "Could not build the proposal", "danger"); return; }
        currentProposal = data.document;  // the document that is sent (proposal format v2)
        document.getElementById("spec-propose-json").textContent = JSON.stringify(data.document, null, 2);
        if (data.skipped.length) {
            say("Left out, they are covered by official terms: " + data.skipped.join(", "), "info");
        }
        const problems = document.getElementById("spec-propose-problems");
        problems.textContent = data.problems.join("; ");
        problems.classList.toggle("d-none", !data.problems.length);
        const open = document.getElementById("spec-propose-open");
        open.classList.toggle("d-none", !data.issue_url || data.problems.length > 0);
        if (data.issue_url) open.href = data.issue_url;
        document.getElementById("spec-propose-paste").classList.toggle("d-none", Boolean(data.issue_url));
        dialog.showModal();
    }

    shareAll.addEventListener("click", function () { propose({ all: true }); });
    shareValues.addEventListener("click", function () { propose({ patch: true }); });

    function currentModality() {
        return catalog.modalities.find(function (m) { return m.name === modalitySelect.value; });
    }

    function currentList() {
        const modality = currentModality();
        return modality && modality.lists.find(function (l) { return l.field === listSelect.value; });
    }

    function renderMine() {
        mineBox.replaceChildren();
        mine.forEach(function (value) {
            const row = el("div", "d-flex flex-wrap align-items-center gap-2 border-bottom py-1");
            row.appendChild(el("code", "", value));
            row.appendChild(button("Remove", "btn-outline-danger", function () {
                mine = mine.filter(function (other) { return other !== value; });
                renderMine();
            }));
            mineBox.appendChild(row);
        });
        shareMine.classList.toggle("d-none", !mine.length);
        useMine.classList.toggle("d-none", !mine.length || !catalog.project_open);
    }

    function showList() {
        const list = currentList();
        allowedText.textContent = list ? list.values.join(", ") : "";
        mine = [];
        renderMine();
    }

    function showLists() {
        const modality = currentModality();
        listSelect.replaceChildren();
        (modality ? modality.lists : []).forEach(function (list) {
            const option = el("option", "", list.label);
            option.value = list.field;
            listSelect.appendChild(option);
        });
        showList();
    }

    modalitySelect.addEventListener("change", showLists);
    listSelect.addEventListener("change", showList);
    document.getElementById("spec-v-form").addEventListener("submit", function (event) {
        event.preventDefault();
        const input = document.getElementById("spec-v-input");
        const value = input.value.trim();
        const list = currentList();
        if (!value || !list) return;
        if (list.values.indexOf(value) !== -1) {
            say(value + " is already allowed in this list.", "info");
        } else {
            clearMessage();
            if (mine.indexOf(value) === -1) mine.push(value);
            renderMine();
        }
        input.value = "";
    });
    shareMine.addEventListener("click", function () {
        propose({ modality: modalitySelect.value, field: listSelect.value, values: mine }, urls.proposeValues);
    });
    useMine.addEventListener("click", async function () {
        if (await addValues(listSelect.value, mine)) { mine = []; renderMine(); }
    });

    what.addEventListener("change", function () {
        clearMessage();
        Object.keys(panels).forEach(function (key) { panels[key].hidden = what.value !== key; });
    });

    document.getElementById("spec-propose-close").addEventListener("click", function () { dialog.close(); });
    document.getElementById("spec-propose-download").addEventListener("click", function () {
        if (!currentProposal) return;
        const blob = new Blob([JSON.stringify(currentProposal, null, 2) + "\n"], { type: "application/json" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "proposal.json";
        link.click();
        URL.revokeObjectURL(link.href);
    });

    (async function start() {
        const { ok, data } = await call(urls.catalog);
        if (!ok) { say(data.error || "Could not load the specification", "danger"); return; }
        catalog = data;
        modalitySelect.replaceChildren();
        catalog.modalities.forEach(function (modality) {
            const option = el("option", "", modality.label);
            option.value = modality.name;
            modalitySelect.appendChild(option);
        });
        showLists();
        document.getElementById("spec-values-project").hidden = !catalog.project_open;
        refresh();
    }());
}());
