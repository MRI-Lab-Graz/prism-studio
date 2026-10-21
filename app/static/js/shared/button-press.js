/**
 * Chromium and Firefox (Linux) focus a button on mousedown, which blurs the
 * field being edited. If that field's change/blur handler re-renders and shifts
 * the button before mouseup, the browser drops the click and the user has to
 * click twice. macOS WebKit never focuses buttons, so match it everywhere.
 * Keyboard focus and click handlers are unaffected.
 */
export function installButtonPressGuard(doc = document) {
    doc.addEventListener('mousedown', (event) => {
        if (event.target.closest('button, .btn')) event.preventDefault();
    });
}
