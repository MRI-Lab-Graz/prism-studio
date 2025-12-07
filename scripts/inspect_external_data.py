import pandas as pd
import os

data_dir = "/Volumes/Evo/data/cp02"
csv_file = os.path.join(data_dir, "TrueCrime_MRI_281125.csv")
xlsx_file = os.path.join(data_dir, "Variablen_TrueCrime_MRI_281125.xlsx")

print(f"--- Inspecting {csv_file} ---")
try:
    df_csv = pd.read_csv(csv_file, sep=None, engine="python")  # Auto-detect separator
    print("Columns:", df_csv.columns.tolist())
    print("\nFirst 3 rows:")
    print(df_csv.head(3))
    if "mri_code" in df_csv.columns:
        print("\n'mri_code' column found.")
    else:
        print("\nWARNING: 'mri_code' column NOT found.")
except Exception as e:
    print(f"Error reading CSV: {e}")

print(f"\n--- Inspecting {xlsx_file} ---")
try:
    import openpyxl

    wb = openpyxl.load_workbook(xlsx_file, read_only=True)
    ws = wb.active
    print("First 5 rows (using openpyxl):")
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i >= 5:
            break
        print(row)
except Exception as e:
    print(f"Error reading Excel with openpyxl: {e}")
