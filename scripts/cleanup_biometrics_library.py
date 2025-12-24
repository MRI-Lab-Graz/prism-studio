import json
import os

library_dir = "/Volumes/Evo/software/psycho-validator/library/biometrics"
files = [f for f in os.listdir(library_dir) if f.endswith(".json")]

RESERVED = {
    "Technical",
    "Study",
    "Metadata",
    "I18n",
    "LimeSurvey",
    "Scoring",
    "Normative",
}

for filename in files:
    filepath = os.path.join(library_dir, filename)
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    task = filename[len("biometrics-"):-5] # e.g. cmj
    
    new_data = {}
    # Keep reserved keys
    for k in RESERVED:
        if k in data:
            new_data[k] = data[k]
            
    # Keep keys that belong to this task or have full metadata
    for k, v in data.items():
        if k in RESERVED: continue
        
        # If it's an empty dict, it's definitely a misplaced key from my bad sync
        if v == {}:
            print(f"Removing empty key {k} from {filename}")
            continue
            
        # If it doesn't have DataType, it's likely invalid
        if isinstance(v, dict) and "DataType" not in v:
            print(f"Removing invalid key {k} from {filename}")
            continue
            
        new_data[k] = v
        
    with open(filepath, 'w') as f:
        json.dump(new_data, f, indent=2)
    print(f"✅ Cleaned {filename}")
