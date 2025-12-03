import PyInstaller.__main__
import os
import sys
import shutil
import subprocess

# Clean previous builds
if os.path.exists('build'):
    shutil.rmtree('build')
if os.path.exists('dist'):
    shutil.rmtree('dist')

# --- Icon Generation (macOS only) ---
icon_file = None
if sys.platform == 'darwin':
    print("🎨 Generating macOS icon...")
    try:
        source_png = "static/img/MRI_Lab_Logo.png"
        iconset_dir = "PrismValidator.iconset"
        if os.path.exists(iconset_dir):
            shutil.rmtree(iconset_dir)
        os.makedirs(iconset_dir)

        # Generate required sizes
        sizes = [16, 32, 64, 128, 256, 512, 1024]
        for size in sizes:
            # Normal resolution
            subprocess.run(['sips', '-z', str(size), str(size), source_png, 
                          '--out', f"{iconset_dir}/icon_{size}x{size}.png"], 
                          check=True, capture_output=True)
            # Retina resolution (2x)
            subprocess.run(['sips', '-z', str(size*2), str(size*2), source_png, 
                          '--out', f"{iconset_dir}/icon_{size}x{size}@2x.png"], 
                          check=True, capture_output=True)

        # Convert to icns
        subprocess.run(['iconutil', '-c', 'icns', iconset_dir], check=True)
        icon_file = "PrismValidator.icns"
        print(f"✅ Generated {icon_file}")
        
        # Cleanup
        shutil.rmtree(iconset_dir)
    except Exception as e:
        print(f"⚠️ Failed to generate icon: {e}")

# Define data to include
# Format: "source:dest"
# On Windows use ; as separator, on Unix use :
sep = ';' if os.name == 'nt' else ':'

datas = [
    f"templates{sep}templates",
    f"static{sep}static",
    f"schemas{sep}schemas",
    f"src{sep}src",
    f"survey_library{sep}survey_library"
]

# Run PyInstaller
args = [
    'prism-validator-web.py',
    '--name=PrismValidator',
    '--windowed',  # No console window
    '--onedir',    # Directory based
    '--clean',
    '--noconfirm',
    # Add Info.plist keys to fix "prohibited" sign and improve integration
    '--osx-bundle-identifier=at.ac.uni-graz.mri.prism-validator',
    # Explicitly include hidden imports that PyInstaller might miss
    '--hidden-import=jsonschema',
    '--hidden-import=xml.etree.ElementTree',
    '--hidden-import=pkg_resources.extern',
]

if icon_file:
    args.append(f'--icon={icon_file}')

for data in datas:
    args.append(f'--add-data={data}')

print("Building with args:", args)

PyInstaller.__main__.run(args)

# --- Post-Build Fixes (macOS only) ---
if sys.platform == 'darwin':
    app_path = "dist/PrismValidator.app"
    print("🔧 Applying macOS post-build fixes...")
    
    # 1. Update Info.plist with LSMinimumSystemVersion
    try:
        print("📝 Updating Info.plist...")
        plist_path = os.path.join(app_path, "Contents", "Info.plist")
        subprocess.run(['plutil', '-replace', 'LSMinimumSystemVersion', '-string', '10.13', plist_path], check=True)
    except Exception as e:
        print(f"⚠️ Updating Info.plist failed: {e}")

    # 2. Force ad-hoc code signing
    try:
        print("🔏 Signing app bundle...")
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', app_path], check=True)
    except Exception as e:
        print(f"⚠️ Signing failed: {e}")

    # 3. Remove quarantine attribute (fixes "App is damaged" or prohibited sign in some cases)
    try:
        print("🛡️ Removing quarantine attribute...")
        subprocess.run(['xattr', '-cr', app_path], check=True)
    except Exception as e:
        print(f"⚠️ Removing quarantine failed: {e}")

print("Build complete. Check dist/PrismValidator")
