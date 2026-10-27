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
        proposeNewKind: root.dataset.proposeNewKindUrl,
        newKindForm: root.dataset.newKindFormUrl,
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
    const templateSelect = document.getElementById("spec-template");
    const sectionsBox = document.getElementById("spec-sections");
    const shareButtons = document.getElementById("spec-share-buttons");
    const useButton = document.getElementById("spec-use");
    let catalog = { modalities: [], project_open: false };
    let projectSpecimens = [];  // sample types this project added itself
    let foundMetrics = [];  // unknown metrics of the open project, each with its modality
    let foundSearched = [];  // the kinds of data whose columns were searched
    let foundColumn = null;  // the "Found in your data" column the form was filled from
    const exampleCells = new Map();  // step 2: field -> the example cell beside that entry, refilled when another template is chosen
    let answers = [];  // step 2: one {entry, read()} per entry of the chosen kind of data
    let download = null;  // {name, type, text}: what "Download" saves
    let lastKind = "";  // the last kind of data chosen in step 1, the closest kind for "Nothing fits"

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

    // Columns found in the data belong to the kind of data they were read for; only the chosen kind's are shown.
    function renderUnknown() {
        const kind = currentKind();
        const searched = (kind && foundSearched.indexOf(kind.name) !== -1);
        document.getElementById("spec-m-project").hidden = !catalog.project_open || !searched;
        const metrics = foundMetrics.filter(function (metric) { return kind && metric.modality === kind.name; });
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
            row.appendChild(button("Add to this project", "btn-primary", function () { addValues("biosample", found.field, [found.value]); }));
            valuesUnknownBox.appendChild(row);
        });
    }

    function renderLocalValues(items) {
        valuesLocalBox.replaceChildren();
        shareValues.replaceChildren();
        const kinds = items.filter(function (item) { return item.status === "local"; }).map(function (item) { return item.modality; });
        Array.from(new Set(kinds)).forEach(function (kind) {
            shareValues.appendChild(button("Share additions (" + kindLabel(kind) + ")…", "btn-outline-primary", function () {
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
            row.appendChild(el("span", "small text-muted", kindLabel(item.modality)));
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
        foundMetrics = data.unknown_metrics;
        foundSearched = data.metric_modalities;
        renderUnknown();
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

    // The share dialog: what is sent, the link to the prefilled form (`url`, or none) and what "Download" saves.
    function showDialog(copy, shown, context, problems, url, pasteNote, saved) {
        document.getElementById("spec-propose-title").textContent = copy.title;
        document.getElementById("spec-propose-text").textContent = copy.text;
        document.getElementById("spec-propose-json").textContent = shown;
        document.getElementById("spec-propose-context").textContent = context || "";
        document.getElementById("spec-propose-context-box").hidden = !context;
        const problemBox = document.getElementById("spec-propose-problems");
        problemBox.textContent = problems.join("; ");
        problemBox.classList.toggle("d-none", !problems.length);
        const open = document.getElementById("spec-propose-open");
        open.classList.toggle("d-none", !url || problems.length > 0);
        open.textContent = copy.open || "Open the prefilled form on GitHub";
        if (url) open.href = url;
        document.getElementById("spec-propose-download").textContent = "Download " + saved.name;
        document.getElementById("spec-propose-paste").classList.toggle("d-none", !pasteNote);
        download = saved;
        dialog.showModal();
    }

    async function propose(body, url, kind) {
        clearMessage();
        const { ok, data } = await call(url || urls.propose, body);
        if (!ok) { say(data.error || "Could not build the proposal", "danger"); return; }
        if (data.skipped.length) {
            say("Left out, they are covered by official terms: " + data.skipped.join(", "), "info");
        }
        const text = JSON.stringify(data.document, null, 2);  // the document that is sent (proposal format v2)
        showDialog(shareCopy[kind || "measurement"], text, data.context, data.problems, data.issue_url, !data.issue_url,
            { name: "proposal.json", type: "application/json", text: text + "\n" });
    }

    shareAll.addEventListener("click", function () { propose({ all: true }); });

    function kindLabel(name) {
        const kind = catalog.modalities.find(function (entry) { return entry.name === name; });
        return kind ? kind.label : name;
    }

    function currentKind() {
        return catalog.modalities.find(function (kind) { return kind.name === kindSelect.value; });
    }

    // A native <option> holds only text, so the icons are emoji standing in for the converter's icons.
    const KIND_ICONS = { survey: "📋", biometrics: "⚖️", biosample: "🧪", physio: "💓", environment: "🌍", events: "⏱️" };
    const kindIcon = function (name) { return (KIND_ICONS[name] || "📄") + " "; };

    function option(text, value, kind) {
        const node = el("option", "", text);
        node.value = value;
        if (kind) node.dataset.kind = kind;
        return node;
    }

    // The "i" next to a label: the schema's own description as a tooltip (a button, so the keyboard reaches it).
    function infoIcon(text, subject) {
        const node = el("button", "btn btn-link btn-sm p-0 ms-1 text-muted align-baseline");
        node.type = "button";
        node.title = text;
        node.setAttribute("aria-label", "About " + subject + ": " + text);
        node.appendChild(el("i", "fas fa-circle-info"));
        if (window.bootstrap) new window.bootstrap.Tooltip(node);
        return node;
    }

    // One collapsible section, drawn like the sections of the project page; closed at first.
    const SECTION_ICONS = {
        Study: "fa-book", Technical: "fa-gear", I18n: "fa-language", Scoring: "fa-calculator", Normative: "fa-chart-line",
        Recording: "fa-wave-square", TriggerAnnotations: "fa-bolt", Acquisition: "fa-sliders", Processing: "fa-filter",
        Privacy: "fa-user-shield", Provenance: "fa-database",
    };

    function sectionFold(name, section, body, count) {
        const bodyId = "spec-section-" + sectionsBox.children.length;
        const wrap = el("div", "mb-2");
        wrap.dataset.section = name;
        const toggle = el("button", "btn btn-sm btn-outline-secondary w-100 text-start sm-section-toggle");
        toggle.type = "button";
        toggle.dataset.bsToggle = "collapse";
        toggle.dataset.bsTarget = "#" + bodyId;
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-controls", bodyId);
        const title = el("span", "sm-section-toggle__title");
        title.append(el("i", "fas " + (SECTION_ICONS[name] || "fa-list") + " me-1"), document.createTextNode(" " + section.title));
        const titleline = el("span", "sm-section-toggle__titleline");
        titleline.append(title, el("span", "sm-section-toggle__badge badge rounded-pill bg-secondary", count + (count === 1 ? " entry" : " entries")));
        toggle.append(titleline, el("span", "sm-section-toggle__summary", section.summary));
        const card = el("div", "card card-body border-0 bg-light mt-1");
        card.appendChild(body);
        const collapse = el("div", "collapse");
        collapse.id = bodyId;
        collapse.appendChild(card);
        wrap.append(toggle, collapse);
        return wrap;
    }

    // items grouped by the section of their field ("Technical.SpecimenType" -> "Technical"), in order.
    function bySection(items, fieldOf) {
        const groups = new Map();
        items.forEach(function (item) {
            const section = fieldOf(item).split(".")[0];
            if (!groups.has(section)) groups.set(section, []);
            groups.get(section).push(item);
        });
        return groups;
    }

    function fillExamples(entries) {
        entries.forEach(function (entry) {
            if (!exampleCells.has(entry.field)) return;  // a section with nothing to propose is not shown
            exampleCells.get(entry.field).replaceChildren(
                el("div", "small mb-0 text-muted spec-example-label", entry.label),
                el("div", entry.example === null ? "text-muted fst-italic" : "", entry.example === null ? "no example yet" : entry.example),
            );
        });
    }

    // Step 2: one fold per section, one row per entry with the example on the left and the user's own entry on the right.
    function renderSections(data, listed) {
        sectionsBox.replaceChildren();
        exampleCells.clear();
        const shown = data.entries.filter(function (entry) { return data.sections[entry.field.split(".")[0]].proposable; });
        answers = shown.map(function (entry, index) { return proposalEntry(entry, index, listed.indexOf(entry.field) !== -1); });
        bySection(answers, function (answer) { return answer.entry.field; }).forEach(function (group, section) {
            const body = el("div", "pb-2");
            group.forEach(function (answer) {
                const left = el("div", "col-md-6");
                const right = el("div", "col-md-6");
                right.appendChild(answer.row);
                exampleCells.set(answer.entry.field, left);
                const pair = el("div", "row g-3 mb-2");
                pair.append(left, right);
                body.appendChild(pair);
            });
            sectionsBox.appendChild(sectionFold(section, data.sections[section], body, group.length));
        });
        fillExamples(data.entries);
    }

    // One entry of the user's proposal: a pull-down for a list (values, "Missing: add a value…", "Unknown"), a text box otherwise.
    function proposalEntry(entry, index, listed) {
        const row = el("div", "mb-2");
        const id = "spec-entry-" + index;
        const label = el("label", "form-label small mb-0", entry.label);
        label.htmlFor = id;
        const heading = el("div", "d-flex align-items-start");
        heading.appendChild(label);
        if (entry.description) heading.appendChild(infoIcon(entry.description, entry.label));
        row.appendChild(heading);
        const missing = el("input", "form-control form-control-sm mt-1");
        missing.type = "text";
        missing.autocomplete = "off";
        missing.hidden = true;
        missing.setAttribute("aria-label", "New value for " + entry.label);
        missing.addEventListener("input", showActions);
        if (entry.values) {
            const select = el("select", "form-select form-select-sm");
            select.id = id;
            choose(select);
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
                    return { value: kind === "unknown" ? "Unknown" : select.value };
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
        unknown.setAttribute("aria-label", "Unknown: " + entry.label);
        const unknownLabel = el("label", "form-check-label", "Unknown");
        unknownLabel.htmlFor = unknown.id;
        unknown.addEventListener("change", function () { text.disabled = unknown.checked; });
        unknownBox.append(unknown, unknownLabel);
        row.append(text, unknownBox);
        return { entry: entry, row: row, read: function () { return { value: unknown.checked ? "Unknown" : text.value.trim() }; } };
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

    // What sharing would send, said in words: the "Missing" values are proposed, every other filled entry is only context.
    function showSummary(lists) {
        const summary = document.getElementById("spec-summary");
        const context = answers.filter(function (answer) { return answer.read().value; })
            .map(function (answer) { return answer.entry.label; });
        const typing = answers.find(function (answer) { return answer.read().missing === ""; });
        if (!lists.length) {
            summary.textContent = typing ? "Type your new value for " + typing.entry.label + "."
                : "Nothing to propose yet: pick “Missing: add a value…” on the list where your value is not offered.";
            return;
        }
        summary.replaceChildren(
            el("strong", "", "You propose: " + lists.map(function (item) { return item.entry.label + ": " + item.value; }).join("; ") + "."),
            document.createTextNode(" " + (context.length ? "Goes along only as context (not proposed): " + context.join(", ") + "." : "Nothing else goes along.")),
        );
    }

    function showActions() {
        const lists = missingLists();
        showSummary(lists);
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
        const chosen = kindSelect.value;
        const query = "?modality=" + encodeURIComponent(chosen) + (template ? "&template=" + encodeURIComponent(template) : "");
        const { ok, data } = await call(urls.example + query);
        if (kindSelect.value !== chosen || (template && templateSelect.value !== template)) return null;  // an answer for an earlier choice
        if (!ok) { say(data.error || "Could not load the example", "danger"); return null; }
        if (template) fillExamples(data.entries);  // another template of the same kind of data; the first one is drawn by renderSections
        document.getElementById("spec-no-example").hidden = Boolean(data.template);
        return data;
    }

    async function chooseKind() {
        clearMessage();
        const kind = currentKind();
        if (foundColumn) m.name.value = "";  // a column picked under another kind must not follow into this one
        forgetFound();
        renderUnknown();
        if (kind) lastKind = kind.name;
        if (kindSelect.value === "new-kind") nk.closest.value = lastKind;
        document.getElementById("spec-new-kind").hidden = kindSelect.value !== "new-kind";
        step2.hidden = true;
        metricPanel.hidden = !(kind && kind.metrics);
        answers = [];
        sectionsBox.replaceChildren();
        m.group.replaceChildren();  // nothing of the previous kind of data stays chosen
        m["form-group"].replaceChildren();
        m.pick.replaceChildren();
        m.detail.textContent = "";
        showActions();
        if (!kind) return;
        const data = await loadExample();
        if (!data) return;
        const listed = kind.lists.map(function (list) { return list.field; });
        templateSelect.replaceChildren();
        data.templates.forEach(function (name) { templateSelect.appendChild(option(name, name)); });
        templateSelect.value = data.template || "";
        document.getElementById("spec-template-box").hidden = data.templates.length < 2;
        renderSections(data, listed);
        step2.hidden = !answers.length;
        if (kind.metrics) fillPick();
    }


    kindSelect.addEventListener("change", chooseKind);
    templateSelect.addEventListener("change", function () { loadExample(templateSelect.value); });
    useButton.addEventListener("click", async function () {
        for (const item of missingLists()) {
            if (!(await addValues(kindSelect.value, item.entry.field, [item.value]))) return;
        }
    });

    const m = {};
    ["pick", "group", "group-box", "detail", "form-group", "form-group-box", "yes", "form", "name", "aliases", "description", "units", "units-other", "specimen", "specimen-box", "levels", "levels-box", "cf", "cf-box", "share", "use", "use-hint", "project", "local"]
        .forEach(function (key) { m[key] = document.getElementById("spec-m-" + key); });

    function choose(select) {
        const node = option("Choose…", "");
        node.disabled = true;
        select.appendChild(node);
    }

    function fillSpecimens() {
        const keep = m.specimen.value;
        m.specimen.replaceChildren();
        choose(m.specimen);
        (catalog.specimens || []).concat(projectSpecimens).forEach(function (name) { m.specimen.appendChild(option(name, name)); });
        m.specimen.value = keep;
        if (m.specimen.selectedIndex < 0) m.specimen.selectedIndex = 0;
    }

    // The sample type chosen in step 2: {value} for one of the list, {missing} for a typed one, or {} (none or "Unknown").
    function chosenSpecimen() {
        const answer = answers.find(function (a) { return a.entry.field === "Technical.SpecimenType"; });
        const read = answer ? answer.read() : {};
        return read.value === "Unknown" ? {} : read;
    }

    // Fill a pull-down with new options, keeping what was chosen if it is still offered.
    function refill(select, nodes) {
        const keep = select.value;
        select.replaceChildren(...nodes);
        select.value = keep;
        if (select.selectedIndex < 0) select.selectedIndex = 0;
    }

    // The groups of the chosen kind of data: the pull-down above the measurements and the optional group of a new one.
    function fillGroups(kind) {
        const placeholder = option("Choose…", "");
        placeholder.disabled = true;
        const names = kind.groups.map(function (name) { return option(name, name); });
        refill(m.group, [placeholder, ...names, option("Not in the list: add a measurement…", "missing")]);
        refill(m["form-group"], [option("Not sure", ""), ...kind.groups.map(function (name) { return option(name, name); })]);
    }

    // Step 3: the official measurements (of the chosen group and sample type, if any), then "Missing".
    function fillPick() {
        const kind = currentKind();
        const twoLevel = kind.specimen_level !== false;  // a kind like environment has no sample type: unit or levels instead
        m["specimen-box"].hidden = !twoLevel;
        m["levels-box"].hidden = twoLevel;
        m["cf-box"].hidden = twoLevel;
        const grouped = kind.groups.length > 0;
        m["group-box"].hidden = !grouped;
        m["form-group-box"].hidden = !grouped;
        if (grouped) fillGroups(kind);
        const group = grouped ? m.group.value : "";
        const waiting = grouped && (!group || group === "missing");  // no group chosen yet, or "not in the list"
        m.pick.disabled = waiting;
        const keep = m.pick.value;
        const specimen = chosenSpecimen().value;
        m.pick.replaceChildren();
        choose(m.pick);
        (kind.metrics || []).filter(function (metric) {
            return (!grouped || metric.group === group) && (!specimen || metric.specimens.indexOf(specimen) !== -1);
        }).forEach(function (metric) {
            m.pick.appendChild(option(metric.label + (metric.units ? " (" + metric.units + ")" : ""), metric.id));
        });
        if (!(grouped && !group)) m.pick.appendChild(option("Missing: add a measurement…", "missing"));
        m.pick.value = group === "missing" ? "missing" : keep;
        if (m.pick.selectedIndex < 0) m.pick.selectedIndex = 0;
        showPick();
    }

    function prefillForm() {
        if (m.group.value && m.group.value !== "missing") m["form-group"].value = m.group.value;  // the group chosen above
        const chosen = chosenSpecimen();
        const specimen = chosen.value || chosen.missing || "";
        if (specimen && !Array.from(m.specimen.options).some(function (o) { return o.value === specimen; })) {
            m.specimen.appendChild(option(specimen, specimen));  // a sample type typed in step 2
        }
        m.specimen.value = specimen;
    }

    function forgetFound() {
        foundColumn = null;
        m.use.classList.add("d-none");
        m["use-hint"].classList.add("d-none");
    }

    // After the choice: its ID and unit (or level codes), which the short option text leaves out.
    function showDetail() {
        const metric = (currentKind().metrics || []).find(function (item) { return item.id === m.pick.value; });
        m.detail.textContent = metric ? [metric.id, metric.units || Object.keys(metric.levels || {}).join(" / ")].filter(Boolean).join(" · ") : "";
    }

    function showPick() {
        showDetail();
        m.yes.hidden = !m.pick.value || m.pick.value === "missing";
        m.form.hidden = m.pick.value !== "missing";
        if (m.pick.value !== "missing") forgetFound();
    }

    function pickFound(metric) {
        foundColumn = metric;
        m.pick.value = "missing";
        showPick();
        m.name.value = metric.column;
        const known = Array.from(m.units.options).some(function (o) { return o.value && o.value === metric.units; });
        m.units.value = known ? metric.units : (metric.units ? "other" : "");
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
        choose(m.units);
        (catalog.units || []).forEach(function (unit) { m.units.appendChild(option(unit, unit)); });
        m.units.appendChild(option("Other…", "other"));
        m.units.selectedIndex = 0;
        fillSpecimens();
        m.local.hidden = !catalog.project_open;
    }

    m.name.addEventListener("input", forgetFound);
    m.pick.addEventListener("change", function () {
        showPick();
        if (m.pick.value === "missing") prefillForm();
    });
    m.group.addEventListener("change", function () {
        m.pick.value = "";  // a measurement of the previous group no longer applies
        fillPick();
        if (m.pick.value === "missing") prefillForm();
    });
    sectionsBox.addEventListener("input", showActions);  // free-text entries and "Unknown" ticks change the summary too
    sectionsBox.addEventListener("change", function () {
        if (!currentKind() || !currentKind().metrics) return;
        fillPick();
        if (m.pick.value === "missing") prefillForm();  // the open form follows the sample type chosen in step 2
    });
    m.units.addEventListener("change", function () { m["units-other"].hidden = m.units.value !== "other"; });
    // "CODE=LABEL" lines as {code: label}; a line without "=" is sent as a code with an empty label, the backend refuses it
    function readLevels() {
        const levels = {};
        m.levels.value.split("\n").map(function (l) { return l.trim(); }).filter(Boolean).forEach(function (line) {
            const at = line.indexOf("=");
            levels[at < 0 ? line : line.slice(0, at).trim()] = at < 0 ? "" : line.slice(at + 1).trim();
        });
        return Object.keys(levels).length ? levels : null;
    }
    m.share.addEventListener("click", function () {
        const oneLevel = currentKind().specimen_level === false;
        propose({
            levels: oneLevel ? readLevels() : null, cf_standard_name: oneLevel ? m.cf.value.trim() || null : null,
            name: m.name.value, description: m.description.value,
            units: (m.units.value === "other" ? m["units-other"].value : m.units.value) || null, specimen: oneLevel ? null : m.specimen.value,
            aliases: m.aliases.value.split(","), modality: kindSelect.value, group: m["form-group"].value || null,
            entries: contextFor(null).entries, not_sure: notSure.checked, closest: kindSelect.value,
        }, urls.proposeMetric, "measurement");
    });
    m.use.addEventListener("click", function () {
        if (foundColumn) add(foundColumn, m.name.value.trim());
    });

    const nk = {};
    ["description", "sample", "file", "name", "closest", "share"].forEach(function (key) { nk[key] = document.getElementById("spec-nk-" + key); });
    const newKindCopy = {
        title: "Share a new kind of data with the PRISM community",
        text: "Nothing is sent from this page. The first button opens a prefilled form on GitHub in a new tab. "
            + "Paste your sample into its \"Sample file\" field there (it is not in the link), then submit it.",
    };
    const newKindTooLong = {  // the description does not fit in a link: the button opens the blank form
        title: newKindCopy.title,
        text: "Nothing is sent from this page. Your description is too long to go into the link, so the first button opens "
            + "the empty form on GitHub in a new tab. Paste the description, the closest kind of data and the sample "
            + "from the download into their fields of the form.",
        open: "Open the form on GitHub",
    };

    nk.file.addEventListener("change", async function () {
        const file = nk.file.files[0];
        if (!file) return;
        if (file.size > 200 * 1024) {  // the backend decides the real limit; this only avoids reading a huge file
            say("This file is larger than 200 KB. Use a shorter sample.", "warning");
            nk.file.value = "";
            return;
        }
        clearMessage();
        nk.sample.value = await file.text();
    });
    nk.share.addEventListener("click", async function () {
        clearMessage();
        const body = { description: nk.description.value, sample: nk.sample.value, closest: nk.closest.value || null, name: nk.name.value.trim() || null };
        const { ok, data } = await call(urls.proposeNewKind, body);
        if (!ok) { say(data.error || "Could not build the proposal", "danger"); return; }
        const copy = data.note ? newKindTooLong : newKindCopy;
        showDialog(copy, data.text, null, data.problems, data.issue_url || urls.newKindForm, false,
            { name: "new-kind-of-data.txt", type: "text/plain", text: data.text });
    });

    document.getElementById("spec-propose-close").addEventListener("click", function () { dialog.close(); });
    document.getElementById("spec-propose-download").addEventListener("click", function () {
        if (!download) return;
        const blob = new Blob([download.text], { type: download.type });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = download.name;
        link.click();
        URL.revokeObjectURL(link.href);
    });

    (async function start() {
        const { ok, data } = await call(urls.catalog);
        if (!ok) { say(data.error || "Could not load the specification", "danger"); return; }
        catalog = data;
        const nothingFits = kindSelect.lastElementChild;
        catalog.modalities.forEach(function (kind) {
            kindSelect.insertBefore(option(kindIcon(kind.name) + kind.label, kind.name), nothingFits);
            nk.closest.appendChild(option(kindIcon(kind.name) + kind.label, kind.name));
        });
        startMetric();
        document.getElementById("spec-values-project").hidden = !catalog.project_open;
        refresh();
    }());
}());
