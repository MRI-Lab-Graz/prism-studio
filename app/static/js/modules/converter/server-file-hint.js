// A native file input cannot display a server path, so the survey converter shows it in the hint line.
export function serverFileHintText(path) {
    return `Server file: ${path}`;
}
