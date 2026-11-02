/**
 * Session order of a content project, edited next to the review table.
 * The backend numbers the responses (`number`) and validates and saves every name
 * (src.session_order); this only lays the review rows out as cells and maps a typed
 * name to the request body.
 */

/** One cell per numbered response, with the name recorded for it ('' when none). */
export function orderGrid(rows, order) {
    return rows
        .filter((row) => row.number !== null && row.number !== undefined)
        .map((row) => ({
            participant: row.participant,
            number: row.number,
            name: order?.[row.participant]?.[row.number] ?? '',
        }));
}

/** A blank name removes the entry; anything else is sent as typed (the backend checks it). */
export function orderPayload(participant, number, typed) {
    const name = String(typed ?? '');
    return name.trim()
        ? { participant, number, session: name }
        : { participant, number, clear: true };
}
