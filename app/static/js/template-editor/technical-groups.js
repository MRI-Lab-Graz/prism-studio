/**
 * A closed sub-group of the Technical section opens by itself when a field the schema requires is still
 * empty in it, so the user finds what the validation asks for (e.g. SoftwareVersion of a Pavlovia import).
 */
export function opensByDefault(group, required, values) {
    const empty = (name) => {
        const value = values && values[name];
        return value === undefined || value === null || value === '';
    };
    return Boolean(group.defaultOpen) || [...group.fields].some((name) => required.includes(name) && empty(name));
}
