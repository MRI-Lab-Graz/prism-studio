// The colours live in studio-theme.css (.converter-log-<type>), so the WCAG enhanced view can change them.
const LOG_TYPES = new Set(['info', 'success', 'warning', 'error', 'step']);

function createConverterLogLine(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const rawMessage = String(message ?? '');
    const commandMatch = rawMessage.match(/(\bcmd=)(.+)$/);
    const line = document.createElement('span');
    line.className = `converter-log-${LOG_TYPES.has(type) ? type : 'info'}`;

    if (!commandMatch || typeof commandMatch.index !== 'number') {
        line.textContent = `[${timestamp}] ${rawMessage}`;
        return line;
    }

    const prefix = rawMessage.slice(0, commandMatch.index) + commandMatch[1];
    line.appendChild(document.createTextNode(`[${timestamp}] ${prefix}`));

    const commandSpan = document.createElement('span');
    commandSpan.className = 'backend-command-text';
    commandSpan.textContent = commandMatch[2];
    line.appendChild(commandSpan);
    return line;
}

export function appendConverterLogLine(message, type = 'info', logElement, fallbackLogElement = null) {
    const targetLog = logElement || fallbackLogElement;
    if (!targetLog) {
        return;
    }

    const line = createConverterLogLine(message, type);
    targetLog.appendChild(line);
    targetLog.appendChild(document.createTextNode('\n'));
    targetLog.scrollTop = targetLog.scrollHeight;
}

export function appendConverterLogBatch(entries, defaultType = 'info', logElement, fallbackLogElement = null) {
    if (!Array.isArray(entries) || entries.length === 0) {
        return;
    }

    const targetLog = logElement || fallbackLogElement;
    if (!targetLog) {
        return;
    }

    const fragment = document.createDocumentFragment();
    entries.forEach((entry) => {
        const message = entry && typeof entry === 'object' ? entry.message : entry;
        const level = entry && typeof entry === 'object'
            ? (entry.type || entry.level || defaultType)
            : defaultType;
        fragment.appendChild(createConverterLogLine(message, level));
        fragment.appendChild(document.createTextNode('\n'));
    });

    targetLog.appendChild(fragment);
    targetLog.scrollTop = targetLog.scrollHeight;
}