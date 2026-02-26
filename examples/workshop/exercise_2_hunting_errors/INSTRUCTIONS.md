# Exercise 2 — Error Hunting

**Time:** 20 min  
**Goal:** Find common import/validation failures fast and explain why they fail.

![Validation](../../../docs/_static/screenshots/prism-studio-exercise-2-validation-light.png)

## Input

- `bad_examples/` files in this folder

## Do this

1. Open **Converter** and load one bad file at a time.
2. Check preview + mapping behavior.
3. Run **Validate** and note top errors.
4. Pick one file, fix it in VS Code, re-import, re-validate.

## Hunt targets

- not really TSV
- duplicate participant rows
- impossible value for a scale
- empty file

## Done when

- You can explain at least 3 distinct error types.
- You fixed at least 1 bad file and saw fewer errors after re-validation.

## Next

Go to `../exercise_3_using_recipes/INSTRUCTIONS.md`.
