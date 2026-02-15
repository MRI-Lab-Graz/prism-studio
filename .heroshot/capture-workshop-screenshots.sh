#!/bin/bash

cat << 'EOF'
⚠️  DEPRECATED SCRIPT

This script was created for an older version of Heroshot that used JSON config files.

Heroshot v0.13+ uses an INTERACTIVE VISUAL EDITOR instead.

📚 How to Use Heroshot v0.13+:

1. Start PRISM Studio:
   python prism-studio.py

2. Launch Heroshot visual editor:
   cd .heroshot
   npx heroshot

3. Configure screenshots interactively in the browser that opens

4. After configuration, run `npx heroshot` to regenerate

📖 See .heroshot/HEROSHOT_SETUP.md for complete instructions
EOF

exit 1
