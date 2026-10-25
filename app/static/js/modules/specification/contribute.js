// The Propose changes page: step 1 the kind of data, step 2 an accepted example beside the user's proposal.
// Presentation only: every action is a call to /api/spec/..., which runs the same functions as `prism_tools.py spec ...`. Project data (column names,
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
        proposeMetric: root.dataset.proposeMetricUrl,
        example: root.dataset.exampleUrl,
    };
    const unknownBox = document.getElementById("spec-m-found");
    const localBox = document.getElementById("spec-local");
    const message = document.getElementById("spec-message");
    const dialog = document.getElementById("spec-propose-dialog");
    const shareAll = document.getElementById("spec-share-all");
    const valuesUnknownBox = document.getElementById("spec-values-unknown");
    const valuesLocalBox = document.getElementById("spec-values-local");
    const shareValues = document.getElementById("spec-share-values");
    const kindSelect = document.getElementById("spec-kind");
    const notSure = document.getElementById("spec-not-sure");
    const step2 = document.getElementById("spec-step2");
    const metricPanel = document.getElementById("spec-panel-metric");
    const exampleBox = document.getElementById("spec-example");
    const templateSelect = document.getElementById("spec-template");
    const proposalBox = document.getElementById("spec-proposal");
    const shareButtons = document.getElementById("spec-share-buttons");
    const useButton = document.getElementById("spec-use");
    let catalog = { modalities: [], project_open: false };
    let projectSpecimens = [];  // sample types this project added itself
    let foundColumn = null;  // the "Found in your data" column the form was filled from
    let answers = [];  // step 2: one {entry, read()} per entry of the chosen kind of data
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
            unknownBox.appendChild(el("p", "text-muted small mb-0", "Nothing: every measurement in your data is known."));
            return;
        }
        metrics.forEach(function (metric) {
            const row = el("div", "d-flex flex-wrap align-items-center gap-2 border-bottom py-2");
            row.appendChild(button(metric.column, "btn-outline-primary", function () { pickFound(metric); }));
            const detail = [metric.specimen, metric.units].filter(Boolean).join(", ");
            if (detail) row.appendChild(el("span", "text-muted small", detail));
            if (metric.similar.length) {
                row.appendChild(el("span", "small", "Similar official terms: " + metric.similar.join(", ")));
            }
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
            row.appendChild(button("Add to this project", "btn-primary", function () { addValues(found.modality, found.field, [found.value]); }));
            valuesUnknownBox.appendChild(row);
        });
    }

    function renderLocalValues(items) {
        valuesLocalBox.replaceChildren();
        shareValues.replaceChildren();
        const kinds = items.filter(function (item) { return item.status === "local"; }).map(function (item) { return item.modality; });
        Array.from(new Set(kinds)).forEach(function (kind) {
            shareValues.appendChild(button("Share additions (" + kind + ")…", "btn-outline-primary", function () {
                propose({ patch: true, modality: kind }, undefined, "choice");
            }));
        });
        if (!items.length) {
            valuesLocalBox.appendChild(el("p", "text-muted small mb-0", "None yet."));
            return;
        }
        const badge = { "local": "bg-success", "now-official": "bg-info", "invalid": "bg-warning text-dark" };
        items.forEach(function (item) {
            const row = el("div", "d-flex flex-wrap align-items-center gap-2 border-bottom py-2");
            row.appendChild(el("span", "badge " + (badge[item.status] || "bg-secondary"), item.status));
            row.appendChild(el("span", "small text-muted", item.modality));
            row.appendChild(el("code", "", item.id || item.path));
            if (item.problem) row.appendChild(el("span", "small text-danger", item.problem));
            if (item.status === "now-official") {
                row.appendChild(el("span", "small text-muted", "Now official: edit " + item.path + " to remove it."));
            }
            if (item.field && item.value) {
                row.appendChild(button("Remove", "btn-outline-danger", function () { removeValue(item.modality, item.field, item.value); }));
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
        projectSpecimens = data.items.filter(function (item) {
            return item.layer === 2 && item.status === "local" && item.field === "Technical.SpecimenType";
        }).map(function (item) { return item.value; });
        fillSpecimens();
        renderLocal(data.items.filter(function (item) { return item.layer === 3; }));
        renderUnknownValues(data.unknown_values);
        renderLocalValues(data.items.filter(function (item) { return item.layer === 2; }));
    }

    async function add(metric, label) {
        clearMessage();
        const body = { data_file: metric.data_file, column: metric.column };
        if (label) body.label = label;
        const { ok, data } = await call(urls.add, body);
        if (!ok) { say(data.error || "Could not add the measurement", "danger"); return; }
        say("Added to this project. Validate again to see it used.", "success");
        forgetFound();
        refresh();
    }

    async function addValues(modality, field, values) {
        clearMessage();
        const { ok, data } = await call(urls.addValues, { modality: modality, field: field, values: values });
        if (!ok) { say(data.error || "Could not add the value", "danger"); return false; }
        say(data.skipped.length ? "Already official: nothing to add." : "Added to this project. Validate again to see it used.", data.skipped.length ? "info" : "success");
        refresh();
        return true;
    }

    async function removeValue(modality, field, value) {
        if (!window.confirm("Remove " + value + " from the additions to " + field + " in this project?")) return;
        clearMessage();
        const { ok, data } = await call(urls.removeValues, { modality: modality, field: field, values: [value] });
        if (!ok) { say(data.error || "Could not remove it", "danger"); return; }
        say("Removed.", "success");
        refresh();
    }

    async function remove(id) {
        if (!window.confirm("Remove the local measurement " + id + " from this project?")) return;
        clearMessage();
        const { ok, data } = await call(urls.remove, { id: id });
        if (!ok) { say(data.error || "Could not remove it", "danger"); return; }
        say("Removed.", "success");
        refresh();
    }

    const shareCopy = {
        measurement: {
            title: "Share a measurement with the PRISM community",
            text: "Nothing is sent from this page. The first button opens a prefilled form on GitHub in a new tab; you submit it there. The maintainers may choose a different ID or name, and your column name stays an alias, so your files keep working.",
        },
        choice: {
            title: "Share a choice with the PRISM community",
            text: "Nothing is sent from this page. The first button opens a prefilled form on GitHub in a new tab; you submit it there. A maintainer reviews the new choice and may adjust it.",
        },
    };

    async function propose(body, url, kind) {
        clearMessage();
        const { ok, data } = await call(url || urls.propose, body);
        if (!ok) { say(data.error || "Could not build the proposal", "danger"); return; }
        const copy = shareCopy[kind || "measurement"];
        document.getElementById("spec-propose-title").textContent = copy.title;
        document.getElementById("spec-propose-text").textContent = copy.text;
        currentProposal = data.document;  // the document that is sent (proposal format v2)
        document.getElementById("spec-propose-json").textContent = JSON.stringify(data.document, null, 2);
        document.getElementById("spec-propose-context").textContent = data.context || "";
        document.getElementById("spec-propose-context-box").hidden = !data.context;
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

    function currentKind() {
        return catalog.modalities.find(function (kind) { return kind.name === kindSelect.value; });
    }

    function option(text, value, kind) {
        const node = el("option", "", text);
        node.value = value;
        if (kind) node.dataset.kind = kind;
        return node;
    }

    function renderExample(entries) {
        exampleBox.replaceChildren();
        entries.forEach(function (entry) {
            exampleBox.appendChild(el("dt", "small text-muted fw-normal", entry.label));
            exampleBox.appendChild(el("dd", entry.example === null ? "text-muted fst-italic" : "", entry.example === null ? "no example yet" : entry.example));
        });
    }

    // One entry of the user's proposal: a pull-down for a list (values, "Missing: add a value…", "Unknown"), a text box otherwise.
    function proposalEntry(entry, index, listed) {
        const row = el("div", "mb-2");
        const id = "spec-entry-" + index;
        const label = el("label", "form-label small mb-0", entry.label);
        label.htmlFor = id;
        row.appendChild(label);
        const missing = el("input", "form-control form-control-sm mt-1");
        missing.type = "text";
        missing.autocomplete = "off";
        missing.hidden = true;
        missing.setAttribute("aria-label", "New value for " + entry.label);
        missing.addEventListener("input", showActions);
        if (entry.values) {
            const select = el("select", "form-select form-select-sm");
            select.id = id;
            const choose = option("Choose…", "");
            choose.disabled = true;
            select.appendChild(choose);
            entry.values.forEach(function (value) { select.appendChild(option(value, value)); });
            if (listed) select.appendChild(option("Missing: add a value…", "", "missing"));  // only lists PRISM can extend
            select.appendChild(option("Unknown", "", "unknown"));
            select.selectedIndex = 0;
            select.addEventListener("change", function () {
                missing.hidden = select.selectedOptions[0].dataset.kind !== "missing";
                showActions();
            });
            row.append(select, missing);
            return {
                entry: entry, row: row, read: function () {
                    const kind = select.selectedOptions[0].dataset.kind;
                    if (kind === "missing") return { missing: missing.value.trim() };
                    return { value: kind === "unknown" ? "unknown" : select.value };
                },
            };
        }
        const text = el("input", "form-control form-control-sm");
        text.type = "text";
        text.id = id;
        text.autocomplete = "off";
        const unknownBox = el("div", "form-check form-check-inline small mt-1");
        const unknown = el("input", "form-check-input");
        unknown.type = "checkbox";
        unknown.id = id + "-unknown";
        const unknownLabel = el("label", "form-check-label", "Unknown");
        unknownLabel.htmlFor = unknown.id;
        unknown.addEventListener("change", function () { text.disabled = unknown.checked; });
        unknownBox.append(unknown, unknownLabel);
        row.append(text, unknownBox);
        return { entry: entry, row: row, read: function () { return { value: unknown.checked ? "unknown" : text.value.trim() }; } };
    }

    function missingLists() {
        return answers.map(function (answer) { return { entry: answer.entry, value: answer.read().missing }; })
            .filter(function (item) { return item.value; });
    }

    // The context for the maintainer: every filled or "Unknown" entry, and the other lists' new values (shared on their own).
    function contextFor(shared) {
        const entries = {};
        answers.forEach(function (answer) {
            const read = answer.read();
            if (read.value) entries[answer.entry.field] = read.value;
            else if (read.missing && answer.entry !== shared) entries[answer.entry.field] = read.missing + " (also proposed)";
        });
        return { entries: entries, not_sure: notSure.checked, closest: kindSelect.value };
    }

    function showActions() {
        const lists = missingLists();
        shareButtons.replaceChildren();
        lists.forEach(function (item) {
            const text = lists.length === 1 ? "Share with the PRISM community…" : "Share the new " + item.entry.label + "…";
            shareButtons.appendChild(button(text, "btn-primary", function () {
                propose(Object.assign({ modality: kindSelect.value, field: item.entry.field, values: [item.value] }, contextFor(item.entry)),
                    urls.proposeValues, "choice");
            }));
        });
        useButton.classList.toggle("d-none", !lists.length || !catalog.project_open);
    }

    async function loadExample(template) {
        const query = "?modality=" + encodeURIComponent(kindSelect.value) + (template ? "&template=" + encodeURIComponent(template) : "");
        const { ok, data } = await call(urls.example + query);
        if (!ok) { say(data.error || "Could not load the example", "danger"); return null; }
        renderExample(data.entries);
        document.getElementById("spec-no-example").hidden = Boolean(data.template);
        return data;
    }

    async function chooseKind() {
        clearMessage();
        const kind = currentKind();
        document.getElementById("spec-bids-note").hidden = !kind || kind.kind !== "bids";
        document.getElementById("spec-new-kind").hidden = kindSelect.value !== "new-kind";
        step2.hidden = true;
        metricPanel.hidden = !(kind && kind.metrics);
        answers = [];
        proposalBox.replaceChildren();
        showActions();
        if (!kind || kind.kind !== "prism") return;
        if (kind.metrics) showKnown();
        const chosen = kind.name;
        const data = await loadExample();
        if (!data || kindSelect.value !== chosen) return;
        const listed = kind.lists.map(function (list) { return list.field; });
        templateSelect.replaceChildren();
        data.templates.forEach(function (name) { templateSelect.appendChild(option(name, name)); });
        templateSelect.value = data.template || "";
        document.getElementById("spec-template-box").hidden = data.templates.length < 2;
        answers = data.entries.map(function (entry, index) { return proposalEntry(entry, index, listed.indexOf(entry.field) !== -1); });
        answers.forEach(function (answer) { proposalBox.appendChild(answer.row); });
        step2.hidden = !answers.length;
    }

    kindSelect.addEventListener("change", chooseKind);
    templateSelect.addEventListener("change", function () { loadExample(templateSelect.value); });
    useButton.addEventListener("click", async function () {
        for (const item of missingLists()) {
            if (!(await addValues(kindSelect.value, item.entry.field, [item.value]))) return;
        }
    });

    const m = {};
    ["known", "listed", "yes", "form", "name", "aliases", "description", "units", "units-other", "specimen", "share", "use", "use-hint", "project", "local"]
        .forEach(function (key) { m[key] = document.getElementById("spec-m-" + key); });

    function fillSpecimens() {
        const keep = m.specimen.value;
        m.specimen.replaceChildren();
        (catalog.specimens || []).concat(projectSpecimens).forEach(function (name) {
            const option = el("option", "", name);
            option.value = name;
            m.specimen.appendChild(option);
        });
        if (keep) m.specimen.value = keep;
    }

    function showKnown() {
        const kind = currentKind();
        m.known.textContent = kind && kind.metrics ? kind.metrics.map(function (x) { return x.label; }).join(", ") : "";
    }

    function forgetFound() {
        foundColumn = null;
        m.use.classList.add("d-none");
        m["use-hint"].classList.add("d-none");
    }

    function showListed() {
        m.yes.hidden = m.listed.value !== "yes";
        m.form.hidden = m.listed.value !== "no";
        if (m.listed.value === "yes") forgetFound();
    }

    function pickFound(metric) {
        foundColumn = metric;
        m.listed.value = "no";
        showListed();
        m.name.value = metric.column;
        const known = Array.from(m.units.options).some(function (o) { return o.value === metric.units; });
        m.units.value = known ? metric.units : "";
        m["units-other"].value = metric.units && !known ? metric.units : "";
        if (metric.specimen && Array.from(m.specimen.options).some(function (o) { return o.value === metric.specimen; })) {
            m.specimen.value = metric.specimen;
        } else {
            m.specimen.selectedIndex = 0;
        }
        m.units.dispatchEvent(new Event("change"));
        // ponytail: a hand-typed measurement can only be shared; "Use in my open project" needs a data column, so it shows only after one was picked
        m.use.classList.toggle("d-none", !catalog.project_open);
        m["use-hint"].classList.toggle("d-none", !catalog.project_open);
    }

    function startMetric() {
        m.units.replaceChildren();
        (catalog.units || []).concat(["Other…"]).forEach(function (unit, index, all) {
            const option = el("option", "", unit);
            option.value = index === all.length - 1 ? "" : unit;
            m.units.appendChild(option);
        });
        fillSpecimens();
        m.project.hidden = !catalog.project_open;
        m.local.hidden = !catalog.project_open;
    }

    m.name.addEventListener("input", forgetFound);
    m.listed.addEventListener("change", showListed);
    m.units.addEventListener("change", function () { m["units-other"].hidden = m.units.value !== ""; });
    m.share.addEventListener("click", function () {
        propose({
            name: m.name.value, description: m.description.value,
            units: m.units.value || m["units-other"].value, specimen: m.specimen.value,
            aliases: m.aliases.value.split(","), modality: kindSelect.value,
            entries: contextFor(null).entries, not_sure: notSure.checked, closest: kindSelect.value,
        }, urls.proposeMetric, "measurement");
    });
    m.use.addEventListener("click", function () {
        if (foundColumn) add(foundColumn, m.name.value.trim());
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
        const nothingFits = kindSelect.lastElementChild;
        catalog.modalities.forEach(function (kind) { kindSelect.insertBefore(option(kind.label, kind.name), nothingFits); });
        startMetric();
        document.getElementById("spec-values-project").hidden = !catalog.project_open;
        refresh();
    }());
}());
