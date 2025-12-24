import json
import os

library_dir = "/Volumes/Evo/software/psycho-validator/library/survey"
files = [f for f in os.listdir(library_dir) if f.endswith(".json")]

# Use bdi as template if it exists, else first file
template_file = "survey-bdi.json" if "survey-bdi.json" in files else files[0]

with open(os.path.join(library_dir, template_file), 'r') as f:
    template = json.load(f)

template_keys = set(template.keys())
template_study_keys = set(template.get("Study", {}).keys())
template_tech_keys = set(template.get("Technical", {}).keys())

for filename in files:
    if filename == template_file: continue
    
    filepath = os.path.join(library_dir, filename)
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    changed = False
    
    # Check top level
    for k in template_keys:
        if k not in data and not k.startswith("item_"): # Don't copy items
            if k in ["Technical", "Study", "I18n", "Metadata", "Scoring", "Normative"]:
                data[k] = template[k].copy()
                # Reset specific values
                if k == "Study":
                    for sk in data[k]: data[k][sk] = ""
            else:
                # It's likely an item or something else, skip
                pass
            changed = True
            
    # Check Study
    if "Study" in data:
        for k in template_study_keys:
            if k not in data["Study"]:
                data["Study"][k] = ""
                changed = True
            
    # Check Technical
    if "Technical" in data:
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
