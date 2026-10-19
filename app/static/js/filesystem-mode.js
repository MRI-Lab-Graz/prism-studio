(function () {
    // One picker: the in-app browser lists the machine PRISM Studio runs on
    // (the same machine for a local install), so no native dialog or
    // local/server mode is needed.
    function open(mode, options) {
        if (!(window.PrismFolderBrowser && typeof window.PrismFolderBrowser.open === 'function')) {
            return Promise.resolve('');
        }
        return window.PrismFolderBrowser.open(Object.assign({}, options || {}, { mode }));
    }

    const pickFolder = (options) => open('folder', options);
    const pickFile = (options) => open('file', options);

    // No in-app "save as" dialog exists (the folder browser modal only picks
    // existing folders/files), so: pick a folder, then ask for a filename.
    async function browseSaveFile(options = {}) {
        const folder = await pickFolder({
            title: options.title || 'Select Destination Folder',
            confirmLabel: 'Choose Folder',
            startPath: options.startPath || ''
        });
        if (!folder) return '';
        const name = window.prompt('File name:', options.defaultName || 'new-file.json');
        if (!name) return '';
        return `${folder.replace(/[\\/]+$/, '')}/${name}`;
    }

    window.PrismPathPicker = {
        browseFolder: pickFolder,
        browseFile: pickFile,
        browseSaveFile,
        pickServerFolder: pickFolder,
        pickServerFile: pickFile,
    };
})();
