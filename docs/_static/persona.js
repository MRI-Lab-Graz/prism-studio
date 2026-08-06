// Tutorial persona picker: lets a reader pick one of three framing stories
// on TUTORIAL_BEGINNER.md, remembers the choice (localStorage), and shows
// the matching flavor note in each chapter page. Pure enhancement — every
// page works fully without it.
(function () {
    "use strict";

    var STORAGE_KEY = "prismPersona";
    var PERSONA_META = {
        student: { icon: "👩🏽‍🎓", label: "The enthusiastic student" },
        pi: { icon: "👨🏿‍🔬", label: "The skeptical PI" },
        future: { icon: "🧑🏻", label: "Future-you" }
    };

    function getSelectedPersona() {
        try {
            return window.localStorage.getItem(STORAGE_KEY);
        } catch (err) {
            return null;
        }
    }

    function setSelectedPersona(persona) {
        try {
            window.localStorage.setItem(STORAGE_KEY, persona);
        } catch (err) {
            // Private browsing / storage disabled — selection just won't persist.
        }
    }

    function applyPickerState(persona) {
        var cards = document.querySelectorAll(".prism-persona-card");
        if (!cards.length) return;
        cards.forEach(function (card) {
            var isSelected = card.getAttribute("data-persona") === persona;
            card.classList.toggle("is-selected", isSelected);
            card.setAttribute("aria-pressed", isSelected ? "true" : "false");
        });
        var hint = document.getElementById("prismPersonaHint");
        if (hint) {
            var meta = persona && PERSONA_META[persona];
            hint.textContent = meta
                ? "Selected: " + meta.icon + " " + meta.label + " — chapters ahead will speak to it. Click another card to switch."
                : "Pick one — chapters ahead will speak to it.";
        }
    }

    function applyNoteState(persona) {
        document.querySelectorAll("[data-persona-note]").forEach(function (group) {
            var empty = group.querySelector("[data-persona-empty]");
            var matched = false;
            group.querySelectorAll(".prism-persona-note-content").forEach(function (node) {
                var isMatch = node.getAttribute("data-persona") === persona;
                node.hidden = !isMatch;
                if (isMatch) matched = true;
            });
            if (empty) empty.hidden = matched;
        });
    }

    function refresh() {
        var persona = getSelectedPersona();
        applyPickerState(persona);
        applyNoteState(persona);
    }

    function selectFromCard(card) {
        var persona = card.getAttribute("data-persona");
        if (!persona) return;
        setSelectedPersona(persona);
        refresh();
    }

    function bindPicker() {
        document.querySelectorAll(".prism-persona-card").forEach(function (card) {
            card.addEventListener("click", function () {
                selectFromCard(card);
            });
            card.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
                    event.preventDefault();
                    selectFromCard(card);
                }
            });
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        bindPicker();
        refresh();
    });
})();
