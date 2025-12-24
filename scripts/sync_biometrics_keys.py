import json
import os

library_dir = "/Volumes/Evo/software/psycho-validator/library/biometrics"
files = [f for f in os.listdir(library_dir) if f.endswith(".json")]

# Use cmj as template
with open(os.path.join(library_dir, "biometrics-cmj.json"), 'r') as f:
    template = json.load(f)

template_keys = set(template.keys())
template_study_keys = set(template["Study"].keys())
template_tech_keys = set(template["Technical"].keys())

for filename in files:
    if filename == "biometrics-cmj.json": continue
    
    filepath = os.path.join(library_dir, filename)
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    changed = False
    
    # Check top level
    for k in template_keys:
        if k not in data:
            if k in ["Technical", "Study", "I18n", "Metadata", "Scoring", "Normative"]:
                data[k] = template[k].copy()
                changed = True
            # DO NOT copy measurement keys (like pre_cmj_1) to other tasks!
            
    # Check Study
    for k in template_study_keys:
        if k not in data["Study"]:
            data["Study"][k] = ""
            changed = True
            
    # Check Technical
    for k in template_tech_keys:
        if k not in data["Technical"]:
            data["Technical"][k] = ""
            changed = True
            
    if changed:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Synchronized keys for {filename}")
    else:
        print(f"ℹ️ {filename} is already synchronized")
