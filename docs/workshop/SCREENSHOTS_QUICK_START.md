:orphan:

# 📸 Quick Start: Workshop Screenshots

The workshop uses **Heroshot**, an interactive visual screenshot tool. Unlike config-file tools, Heroshot lets you point-and-click to configure screenshots.

## First Time Setup (5-10 minutes)

### Step 1: Start PRISM Studio

```bash
source .venv/bin/activate  # macOS/Linux
# or .venv\Scripts\activate.bat on Windows

./prism-studio.py
```

Leave this running.

### Step 2: Launch Heroshot

In a new terminal:

```bash
cd .heroshot
npx heroshot
```

A browser opens with Heroshot's visual editor.

### Step 3: Configure Screenshots Interactively

For each PRISM interface you want to capture:

1. **Enter URL** in Heroshot (e.g., `http://127.0.0.1:5001/converter`)
2. **Click elements** on the page to select what to screenshot
3. **Style** (optional): Add borders, padding, annotations
4. **Save** - Screenshot definition is saved
5. **Next interface** - Repeat for validator, recipes, templates, etc.

### Step 4: Generate Screenshots

After configuration, Heroshot automatically captures all defined screenshots.

Output location: `heroshots/` directory

## After Initial Setup

To regenerate screenshots (e.g., after PRISM updates):

```bash
cd .heroshot
npx heroshot  # Regenerates all configured screenshots
```

## What You'll Get

18 screenshots covering all major PRISM interfaces:
- ✓ Home, Projects, Converter, Validator
- ✓ File Management, Recipe Scorer, Template Editor
- ✓ Specifications Reference, Survey Library
- ✓ **Both light and dark themes** for each

## Using Screenshots

Screenshots are automatically referenced in workshop exercises. For example:
- Exercise 1 includes converter interface screenshots
- Other exercises have similar visual guides

To add custom screenshots, edit `.heroshot/config.json` then re-run the capture script.

## Troubleshooting

**Script won't run?**
1. Make sure `.venv` is activated: `source .venv/bin/activate`
2. Have Node.js installed: https://nodejs.org/
3. See `.heroshot/HEROSHOT_SETUP.md` for full troubleshooting guide

**Screenshots are blank?**
- PRISM Studio may not have loaded the page properly
- Check `.heroshot/HEROSHOT_SETUP.md` → Troubleshooting

**Want to update screenshots later?**
- Just re-run the same command anytime
- They'll overwrite the previous version

## Learn More

- `.heroshot/README.md` - Overview
- `.heroshot/HEROSHOT_SETUP.md` - Complete guide
- `examples/workshop/README.md` - Workshop overview

---

**Next:** Run the capture command above, then open a workshop exercise!
