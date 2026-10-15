/**
 * Read a recipe JSON file picked in the Recipe Builder and say which modality
 * and task it is for. Whether the recipe is valid and has a template is decided
 * by the save endpoint (src/recipe_builder.py: save_recipe_to_project), not here.
 */

const TASK_KEYS = { survey: ['Survey', 'TaskName'], biometrics: ['Biometrics', 'BiometricName'] };

export function parseRecipeFile(text, selectedModality) {
    let recipe;
    try {
        recipe = JSON.parse(text);
    } catch (error) {
        throw new Error('File is not valid JSON: ' + error.message);
    }
    if (!recipe || typeof recipe !== 'object' || Array.isArray(recipe)) {
        throw new Error('File is not a recipe (expected a JSON object).');
    }

    const kind = String(recipe.Kind || '').trim().toLowerCase();
    const modality = kind || selectedModality;
    const [infoKey, taskKey] = TASK_KEYS[modality] || [];
    if (!infoKey) throw new Error('Unsupported recipe Kind: ' + modality);

    const task = String((recipe[infoKey] || {})[taskKey] || '').trim();
    if (!task) throw new Error('Recipe must have ' + infoKey + '.' + taskKey + '.');

    return { recipe, modality, task };
}
