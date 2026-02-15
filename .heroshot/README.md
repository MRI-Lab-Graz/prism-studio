# 📸 Heroshot - Workshop Screenshot Automation

This directory contains the Heroshot configuration and helper scripts for capturing screenshots of the PRISM Studio web interface for workshop exercises.

## Contents

```
.heroshot/
├── README.md                           # This file - Quick overview
├── HEROSHOT_SETUP.md                   # Complete setup and troubleshooting guide
├── config.json                         # Heroshot screenshot definitions (18 captures)
├── capture-workshop-screenshots.sh     # macOS/Linux automated capture script
├── capture-workshop-screenshots.bat    # Windows automated capture script
└── session.enc                         # Encrypted browser session (auto-managed)
```

## 🚀 Quick Start

### First Time: Interactive Setup

Heroshot uses a **visual editor** to configure screenshots:

1. **Start PRISM Studio:**
   ```bash
   python prism-studio.py
   ```

2. **Launch Heroshot editor:**
   ```bash
   cd .heroshot
   npx heroshot
   ```

3. **Configure screenshots visually:**
   - Browser opens with Heroshot UI
   - Navigate to PRISM pages (converter, validator, etc.)
   - Click elements to select
   - Add styling/annotations
   - Save configuration

### After Configuration: One-Command Regeneration

Once configured, regenerate all screenshots:

```bash
cd .heroshot
npx heroshot
```

Screenshots automatically update in `heroshots/` directory.

### Verify Output

```bash
ls -la docs/_static/screenshots/prism-studio-*.png
```

You should see 18 files (9 interfaces × 2 themes).

## 📚 Using Screenshots in Workshop

Add to exercise instructions:

```markdown
![PRISM Studio Converter](../../../docs/_static/screenshots/prism-studio-converter-light.png)
*Figure: Data converter interface showing WHO-5 survey mapping*
```

## 📖 For Detailed Information

See [HEROSHOT_SETUP.md](./HEROSHOT_SETUP.md) for:
- Full prerequisites and setup
- Multiple capture options (script, GitHub Actions, manual)
- Customizing config.json
- Troubleshooting guide
- Adding new screenshots
- CI/CD automation

## 📋 Captured Interfaces

All 9 major PRISM Studio interfaces (light + dark themes each):

1. **Home** - Dashboard
2. **Projects** - Project management
3. **Converter** - Raw to BIDS conversion
4. **Validator** - Error detection
5. **File Management** - File browser
6. **Recipe Scorer** - Automated scoring
7. **Template Editor** - Metadata templates
8. **Specifications** - BIDS/PRISM reference
9. **Survey Library** - Survey templates

## 🔒 Safe to Commit

This folder is safe to commit:
- `config.json` contains no secrets
- `session.enc` is encrypted with AES-256-GCM
- Screenshot output goes to `docs/_static/screenshots/`

## ⚙️ CI/CD: GitHub Actions

Push a version tag to auto-capture screenshots:

```bash
git tag v0.x.y
git push origin v0.x.y
```

Workflow file: `.github/workflows/update-screenshots.yml`

## 🙋 Need Help?

1. **Script not working?** See [HEROSHOT_SETUP.md - Troubleshooting](./HEROSHOT_SETUP.md#troubleshooting)
2. **Want to customize?** Edit `config.json` then rerun capture
3. **Adding new interface?** See [HEROSHOT_SETUP.md - Adding New Screenshots](./HEROSHOT_SETUP.md#adding-new-screenshots)

## 📖 Learn More

- [Heroshot docs](https://heroshot.sh/docs)
- [PRISM Workshop documentation](../docs/workshop/)
- [Workshop README](../docs/workshop/README.md)

