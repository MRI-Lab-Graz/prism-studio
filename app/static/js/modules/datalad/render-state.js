/**
 * What the DataLad page shows for a state from GET /api/projects/datalad/state (or null: no project open).
 * Pure: the backend decides `next_step`; this only turns it into a title, a text and buttons.
 * Studio enables DataLad and saves; sending, getting the latest and getting data are Worldline Desktop's job.
 */

const SAVE = { id: 'save', label: 'Save' };
const MORE = [
    { id: 'doctor', label: 'Check this computer' },
    { id: 'settings', label: 'Your name and email (Settings)' },
];

function view(title, text, primary, notice = null) {
    return { title, text, primary, secondary: [], more: MORE.map((a) => ({ ...a })), notice };
}

function stepView(state) {
    const unsaved = Number(state.unsaved_count) || 0;
    switch (state.next_step) {
    case 'install_datalad':
        return view('DataLad is not installed', 'This computer needs DataLad and git-annex before a project can keep snapshots.',
            { id: 'doctor', label: 'Check this computer' },
            { text: 'DataLad was not found on this computer.', kind: 'danger' });
    case 'enable':
        if (state.enable_kind === 'finish') {
            return view('DataLad is not finished', `${Number(state.nested_unregistered) || 0} subject datasets are not registered yet: finish enabling.`,
                { id: 'enable', label: 'Finish enabling DataLad' });
        }
        return view('Keep snapshots of this project', 'DataLad saves snapshots of the project so you can go back to any saved state.',
            { id: 'enable', label: 'Enable DataLad' });
    case 'put_on_server':  // no server yet: Save must stay possible; sharing is Worldline Desktop's job
        return view('Not on a server yet', 'Your snapshots stay on this computer. To share them with your team, use Worldline Desktop.', { ...SAVE });
    case 'save':
        return view('Unsaved changes', unsaved
            ? `${unsaved} unsaved change(s). Save a snapshot; sending it to a server is done in Worldline Desktop.`
            : 'Save a snapshot; sending it to a server is done in Worldline Desktop.', { ...SAVE });
    default:
        return view('Everything is saved', 'Sending your saves to a server, getting what others saved and getting data are done in Worldline Desktop.', null);
    }
}

export function renderState(state) {
    if (!state || !state.next_step) {
        return view('No project open', 'Open a project to enable DataLad or save a snapshot.', null);
    }
    return stepView(state);
}
