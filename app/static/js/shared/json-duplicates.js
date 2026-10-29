/**
 * JSON.parse silently keeps the last of two equal keys. Return the first key
 * that appears twice in one object of `text`, or null (also for invalid JSON:
 * JSON.parse reports that itself).
 */
export function findDuplicateKey(text) {
    const colon = /\s*:/y;
    const stack = []; // one Set of keys per open object, null for an array
    const stringAt = i => {
        let j = i + 1;
        while (j < text.length && text[j] !== '"') j += text[j] === '\\' ? 2 : 1;
        return [j, text.slice(i, j + 1)];
    };
    for (let i = 0; i < text.length; i++) {
        const c = text[i];
        if (c === '{') stack.push(new Set());
        else if (c === '[') stack.push(null);
        else if (c === '}' || c === ']') stack.pop();
        else if (c === '"') {
            const [end, raw] = stringAt(i);
            i = end;
            const keys = stack[stack.length - 1];
            colon.lastIndex = i + 1;
            if (keys && colon.test(text)) {
                let key;
                try { key = JSON.parse(raw); } catch { return null; }
                if (keys.has(key)) return key;
                keys.add(key);
            }
        }
    }
    return null;
}
