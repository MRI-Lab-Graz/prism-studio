# Heroshot Screenshot Setup for PRISM Workshop

This guide explains how to set up and run Heroshot to capture screenshots for the workshop exercises.

## What is Heroshot?

Heroshot is an **interactive visual screenshot tool** that lets you point-and-click to define screenshots. It opens a browser with a visual editor where you select elements, style borders, add annotations, and configure screenshots - no manual JSON editing required. Once configured, you can regenerate all screenshots with one command.

## Quick Start

### Prerequisites

1. **Node.js 18+** installed (https://nodejs.org/)
2. **PRISM dependencies** installed: `pip install -r requirements.txt`
3. **Virtual environment** activated (`.venv/bin/activate` or `.venv\Scripts\activate.bat`)

### Capturing Workshop Screenshots

####Option 1: Interactive Visual Editor (First Time Setup)

**Step 1: Start PRISM Studio**
```bash
source .venv/bin/activate
python prism-studio.py
```

**Step 2: Launch Heroshot Visual Editor**
```bash
cd .heroshot
npx heroshot
```

This opens a browser with Heroshot's visual editor:
1. **Enter URL** - Navigate to PRISM Studio pages (e.g., `http://127.0.0.1:5001/converter`)
2. **Click elements** - Point and click to select what to screenshot
3. **Style** - Adjust padding, borders, add annotations (arrows, callouts)
4. **Save** - Screenshots save to `heroshots/`, config saves to `.heroshot/config.json`
5. **Repeat** - Configure all interfaces you need

**After initial setup:** Run `npx heroshot` to regenerate all screenshots headlessly

#### Option 2: GitHub Actions (Automated Cloud Capture)

Push a new version tag to trigger the workflow:

```bash
git tag v0.x.y
git push origin v0.x.y
```

Screenshots will be captured automatically in the cloud and committed to the repo.

#### Option 3: Manual Capture

If you prefer manual control:

1. **Start PRISM Studio:**
   ```bash
   source .venv/bin/activate
   python prism-studio.py
   ```
   Keep this running in a separate terminal. Wait for: `Running on http://127.0.0.1:5001`

2. **Capture screenshots:**
   ```bash
   cd .heroshot
   npx heroshot --config config.json --clean
   ```

3. **Output:**
   Screenshots are saved to: `docs/_static/screenshots/`

## Screenshot Definitions

The config.json captures these PRISM Studio interfaces in **both light and dark themes**:

### Exercise 0: Project Setup
- **prism-studio-projects** - Project creation/management interface

### Exercise 1: Raw Data Import
- **prism-studio-converter** - Data converter GUI for TSV/Excel conversion

### Exercise 2: Error Hunting
- **prism-studio-validator** - Validation results and error reporting

### Exercise 3: Participant Mapping
- **prism-studio-file-management** - File browser for viewing mapped files

### Exercise 4: Using Recipes
- **prism-studio-recipes** - Recipe scorer interface

### Exercise 5: Creating Templates
- **prism-studio-template-editor** - Metadata template creation tool

### Reference Materials
- **prism-studio-home** - Welcome/home page
- **prism-studio-specifications** - BIDS/PRISM specs reference
- **prism-studio-survey-library** - Official instrument library

## Using Screenshots in Workshop Instructions

### In Exercise INSTRUCTIONS.md files:

Add reference to screenshots like this:

```markdown
### Step 3: Open the Converter Tool

![PRISM Studio Converter Interface](../../docs/_static/screenshots/prism-studio-converter-light.png)

1. In PRISM Studio, click on **"Converter"**
2. You should see a screen similar to the image above
3. Select **"Survey Data Converter"**
```

### For Dark Theme Variants:

If supporting dark theme:

```markdown
**Light Theme:**
![Converter Light](../../docs/_static/screenshots/prism-studio-converter-light.png)

**Dark Theme:**
![Converter Dark](../../docs/_static/screenshots/prism-studio-converter-dark.png)
```

## Configuration Details

### config.json Structure

```json
{
  "baseUrl": "http://127.0.0.1:5001",        // PRISM Studio URL
  "outputDir": "../docs/_static/screenshots", // Where screenshots go
  "viewport": {
    "width": 1440,   // Screenshot width (must match docs)
    "height": 900    // Screenshot height
  },
  "captures": [
    {
      "name": "screenshot-id",           // Unique identifier
      "url": "/path",                    // URL path to capture
      "description": "What this shows",  // For documentation
      "theme": "light|dark",             // Theme variant
      "filename": "output-name.png",     // Output filename
      "waitFor": "selector"              // CSS selector to wait for
    }
  ]
}
```

## Troubleshooting

### Screenshots don't capture

**Problem:** Heroshot runs but creates empty/blank images

**Solutions:**
1. Ensure PRISM Studio is fully loaded (check http://127.0.0.1:5001 manually first)
2. Increase `delay` in config.json (try 2000-3000ms)
3. Check that selectors in `waitFor` exist on the page

### Heroshot can't connect

**Problem:** `Error: connect ECONNREFUSED`

**Solution:** Start PRISM Studio first:
```bash
source .venv/bin/activate
python prism-studio.py
# Wait for "Running on http://127.0.0.1:5001"
# Then run heroshot in another terminal
```

### Node/npm issues

**Problem:** `command not found: npx`

**Solution:**
```bash
# Install Node.js (macOS with Homebrew)
brew install node

# Or install Heroshot globally
npm install -g heroshot@0.13.1
```

## Advanced: Custom Screenshots

### Adding a new screenshot

1. Edit `.heroshot/config.json`
2. Add a new entry to the `captures` array:

```json
{
  "name": "my-new-screenshot",
  "url": "http://127.0.0.1:5001/my-tool",
  "description": "My tool interface",
  "theme": "light",
  "filename": "my-tool-light.png",
  "waitFor": ".my-tool-class"
}
```

3. Re-run Heroshot:
```bash
npx heroshot --config config.json --clean
```

### Waiting for page elements

Use `waitFor` to ensure the page is fully loaded before capturing:

```json
{
  "waitFor": ".converter-panel, [data-testid=converter-upload], .file-input"
  // Waits for ANY of these selectors to appear
}
```

## Updating Screenshots After UI Changes

If the PRISM Studio interface changes:

1. Update any outdated config.json selectors
2. Re-capture screenshots locally:
   ```bash
   npx heroshot --config .heroshot/config.json --clean
   ```
3. Commit updated screenshots:
   ```bash
   git add docs/_static/screenshots/
   git commit -m "chore(docs): update screenshots"
   git push
   ```

## GitHub Actions Integration

The workflow file `.github/workflows/heroshot.yml` automatically runs Heroshot when you push a version tag (`v*`).

It:
1. Builds the docs with Sphinx
2. Starts PRISM Studio
3. Runs Heroshot with the config
4. Commits updated screenshots
5. Stops to prevent infinite loops

To trigger manually:
```bash
gh workflow run heroshot.yml
```

## Best Practices

✅ **DO:**
- Capture in clean browser session (no cookies that affect UI state)
- Use consistent viewport sizes (1440x900)
- Wait for all page elements before capturing
- Name screenshots clearly (prism-studio-tool-theme)
- Commit screenshot updates when UI changes
- Use light theme for primary documentation

❌ **DON'T:**
- Capture with user data/personal information visible
- Use animated GIFs (use static PNG)
- Include system notifications or browser tabs
- Have inconsistent sizes across screenshots

## Accessing Screenshots in Docs

Screenshots are automatically available at:
```
docs/_static/screenshots/prism-studio-*.png
```

They're served by the Sphinx doc build and embedded via markdown image tags.

## See Also

- [Heroshot Documentation](https://heroshot.sh/)
- [Workshop README](../examples/workshop/README.md)
- [PRISM GitHub Signing Guide](../docs/GITHUB_SIGNING.md) - Contains Heroshot setup info
