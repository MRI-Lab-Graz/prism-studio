import json
import os

library_dir = "/Volumes/Evo/software/psycho-validator/library/biometrics"
files = [f for f in os.listdir(library_dir) if f.endswith(".json")]

for filename in files:
    filepath = os.path.join(library_dir, filename)
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    changed = False
    
    # Find the self-assessment key (usually ends in _sa)
    sa_keys = [k for k in data.keys() if k.endswith("_sa")]
    
    # Find keys that have AllowedValues but are NOT sa keys
    misplaced_keys = []
    for k, v in data.items():
        if isinstance(v, dict) and not k.endswith("_sa") and v.get("AllowedValues") == ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]:
            misplaced_keys.append(k)
    
    if misplaced_keys and sa_keys:
        for m_key in misplaced_keys:
            # Find the best matching SA key (e.g. post_cmj_2 -> post_cmj_sa)
            prefix = "_".join(m_key.split("_")[:2]) # e.g. post_cmj
            matching_sa = [sa for sa in sa_keys if sa.startswith(prefix)]
            
            if matching_sa:
                sa_key = matching_sa[0]
                print(f"Fixing {filename}: Moving AllowedValues from {m_key} to {sa_key}")
                
                # Move AllowedValues and Levels
                data[sa_key]["AllowedValues"] = data[m_key]["AllowedValues"]
                data[sa_key]["Levels"] = data[m_key].get("Levels", {})
                
                # Clear from misplaced key
                data[m_key]["AllowedValues"] = []
                data[m_key]["Levels"] = {}
                
                # Also fix DataType if it was string but should be float
                # (Measurements are usually float)
                if data[m_key].get("DataType") == "string":
                    data[m_key]["DataType"] = "float"
                
                changed = True
            else:
                print(f"Warning in {filename}: Misplaced AllowedValues in {m_key} but no matching SA key found.")

    if changed:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✅ Updated {filename}")
    else:
        print(f"ℹ️ No changes needed for {filename}")
