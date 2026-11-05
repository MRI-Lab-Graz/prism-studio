/**
 * What the DataLad page shows for a state from GET /api/projects/datalad/state (or null: no project open).
 * Pure: the backend decides `next_step`; this only turns it into a title, a text and buttons.
 */

const OPEN = { id: 'open-from-server', label: 'Open from server...' };
const SAVE = { id: 'save', label: 'Save' };
const SYNC = { id: 'sync', label: 'Sync now' };
const MORE = [
    { id: 'get-latest', label: 'Get latest' },
    { id: 'get-data', label: 'Get data...' },
    { id: 'doctor', label: 'Check this computer' },
    { id: 'settings', label: 'Your name and email (Settings)' },
];

export function sendAnywayLabel(count) {
    return `Send anyway, I understand this dataset has ${count} errors`;
}

function view(title, text, primary, secondary = [], notice = null) {
    return { title, text, primary, secondary, more: MORE.map((a) => ({ ...a })), notice };
}

function stepView(state) {
    const unsaved = Number(state.unsaved_count) || 0;
    switch (state.next_step) {
    case 'install_datalad':
        return view('DataLad is not installed', 'This computer needs DataLad and git-annex before a project can keep snapshots.',
            { id: 'doctor', label: 'Check this computer' }, [],
            { text: 'DataLad was not found on this computer.', kind: 'danger' });
    case 'enable':
        return view('Keep snapshots of this project', 'DataLad saves snapshots of the project so you can share it with your team and go back to any saved state.',
            { id: 'enable', label: 'Enable DataLad' }, [{ ...OPEN }]);
    case 'put_on_server': {
        const others = (state.other_servers || []).map((name) => ({ id: 'sync', label: `Sync now with "${name}"`, sibling: name }));
        return view('Not on a server yet', 'Your snapshots stay on this computer. Put the project on the lab server to share it with your team.',
            { id: 'put-on-server', label: 'Put on server...' }, [{ ...SAVE }, ...others]);
    }
    case 'save':
        return view('Unsaved changes', unsaved
            ? `${unsaved} unsaved change(s). Save a snapshot, then sync it with the server.`
            : 'Save a snapshot, then sync it with the server.', { ...SAVE }, [{ ...SYNC }]);
    default:
        return view('Everything is saved', 'Sync gets what others have saved on the server and sends your saved changes.', { ...SYNC });
    }
}

export function renderState(state) {
    if (!state || !state.next_step) {
        return view('No project open', 'Open a project, or get a team project from the lab server.', { ...OPEN });
    }
    const result = stepView(state);
    if (state.valid === false) {
        const count = Number(state.error_count) || 0;
        result.notice = { text: `This dataset has ${count} validation error(s). Only a valid dataset is sent, unless you choose to send it anyway.`, kind: 'warning' };
        result.secondary.push({ id: 'send-anyway', label: sendAnywayLabel(count) });
    } else if (state.server && state.server.reachable === false) {
        result.notice = { text: 'The server could not be reached. You can keep working and saving; sync when the server is back.', kind: 'info' };
    }
    return result;
}
