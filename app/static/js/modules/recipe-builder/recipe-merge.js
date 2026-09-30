/**
 * Assemble the recipe JSON from what the builder edits, starting from the recipe
 * as it was loaded, so nothing the builder does not own is lost on save
 * (top-level Psychometrics / Usage / References, Transforms.Derived, Survey
 * Authors / Version / ..., and so on).
 *
 * The builder owns: RecipeVersion/Kind, the info block's task key and
 * Name/Description/Citation, Transforms.Invert, Scores and VersionedScores.
 */

/** Text shown in a metadata field for a stored value (a localized value becomes one string). */
export function metadataFieldText(value) {
    if (typeof value === 'string') return value.trim();
    if (value && typeof value === 'object') {
        const entries = Object.entries(value).filter(([, text]) => typeof text === 'string' && text.trim());
        const english = entries.find(([lang]) => lang.toLowerCase() === 'en');
        const chosen = english || entries[0];
        return chosen ? chosen[1].trim() : '';
    }
    return '';
}

function applyMetadataField(info, key, typedText) {
    const stored = info[key];
    // A localized stored value stays as it is unless the user changed the text.
    if (stored && typeof stored === 'object' && typedText === metadataFieldText(stored)) return;
    if (typedText) info[key] = typedText;
    else delete info[key];
}

export function buildRecipe({
    loaded,
    modality,
    infoKey,
    taskKey,
    task,
    metadata,
    invertTransform,
    scores,
    versionedScores,
}) {
    const recipe = loaded ? structuredClone(loaded) : {};
    recipe.RecipeVersion = recipe.RecipeVersion || '1.0';
    recipe.Kind = modality;

    const info = recipe[infoKey] && typeof recipe[infoKey] === 'object' ? recipe[infoKey] : {};
    info[taskKey] = task;
    applyMetadataField(info, 'Name', metadata.name);
    applyMetadataField(info, 'Description', metadata.description);
    applyMetadataField(info, 'Citation', metadata.citation);
    recipe[infoKey] = info;

    const transforms = recipe.Transforms && typeof recipe.Transforms === 'object' ? recipe.Transforms : {};
    if (invertTransform) transforms.Invert = invertTransform;
    else delete transforms.Invert;
    if (Object.keys(transforms).length > 0) recipe.Transforms = transforms;
    else delete recipe.Transforms;

    if (scores && scores.length > 0) recipe.Scores = scores;
    else delete recipe.Scores;

    if (versionedScores && Object.keys(versionedScores).length > 0) recipe.VersionedScores = versionedScores;
    else delete recipe.VersionedScores;

    return recipe;
}
