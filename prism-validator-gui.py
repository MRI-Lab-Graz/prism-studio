import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
try:
    from ttkthemes import ThemedTk
except ImportError:
    ThemedTk = None
import threading
import sys
import os
import json
import io
from contextlib import redirect_stdout
from pathlib import Path

# Ensure we can import core validator logic from src
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    BASE_DIR = Path(sys._MEIPASS)
else:
    # Running in a normal Python environment
    BASE_DIR = Path(__file__).resolve().parent

SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from runner import validate_dataset
    from schema_manager import get_available_schema_versions
    from limesurvey_exporter import generate_lss
    from reporting import print_dataset_summary, print_validation_results
    from theme import apply_prism_theme
except ImportError as e:
    # Fallback for development if modules aren't found
    print(f"Warning: Could not import some modules: {e}")
    validate_dataset = None
    get_available_schema_versions = lambda x: ["stable"]
    generate_lss = None
    print_dataset_summary = None
    print_validation_results = None
    apply_prism_theme = None

class PrismValidatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Prism Validator")
        self.root.geometry("1200x800")
        
        style = ttk.Style()
        
        # Check if we want to use our custom theme or an external one
        # For now, let's default to our custom "Prism" theme if available
        if apply_prism_theme:
            self.colors = apply_prism_theme(root)
        elif style.theme_use() == "scidgreen":
             # ScidGreen Theme Adaptation
            self.colors = {
                "bg": style.lookup("TFrame", "background"),
                "fg": "black",
                "accent": "#2e7d32",      # Green
                "button": style.lookup("TButton", "background"),
                "button_hover": "#d0d0d0",
                "secondary": "#e0e0e0",   
                "border": "#a0a0a0",
                "input_bg": "white",    
                "success": "#28a745",
                "error": "#dc3545",
                "warning": "#ffc107"
            }
            # Custom styles for ScidGreen
            style.configure("Header.TLabel", font=("Segoe UI", 24, "bold"))
            style.configure("SubHeader.TLabel", font=("Segoe UI", 11), foreground="#666666")
            style.configure("Section.TLabel", font=("Segoe UI", 14, "bold"), foreground=self.colors["accent"])
            style.configure("List.TFrame", background=self.colors["input_bg"])
            style.configure("List.TLabel", background=self.colors["input_bg"])
            style.configure("List.TCheckbutton", background=self.colors["input_bg"])
            
        else:
            # Fallback to default theme if custom theme fails
            self.colors = {
                "bg": "#f0f0f0",
                "fg": "black",
                "accent": "blue",
                "button": "#e0e0e0",
                "button_hover": "#d0d0d0",
                "secondary": "#e0e0e0",
                "border": "#a0a0a0",
                "input_bg": "white",
                "success": "green",
                "error": "red",
                "warning": "orange"
            }

        # Labelframe
        style.configure("TLabelframe", background=self.colors["bg"], borderwidth=1, relief="solid", bordercolor=self.colors["border"])
        style.configure("TLabelframe.Label", background=self.colors["bg"], foreground=self.colors["accent"], font=("Segoe UI", 11, "bold"))

        # List Styles (for Survey Questions)
        style.configure("List.TFrame", background=self.colors["input_bg"])
        style.configure("List.TLabel", background=self.colors["input_bg"], foreground="#8e8e93")
        style.configure("List.TCheckbutton", background=self.colors["input_bg"], foreground=self.colors["fg"])

        # --- Layout ---
        
        # Main Container
        main_container = ttk.Frame(root)
        main_container.pack(fill="both", expand=True)

        # Sidebar (Left) - Branding & Navigation could go here, but we'll stick to top header for now
        
        # Header
        header_frame = ttk.Frame(main_container, padding="30 20 30 10")
        header_frame.pack(fill="x")
        
        # Logo/Title
        title_frame = ttk.Frame(header_frame)
        title_frame.pack(side="left")
        
        # Load Logo
        try:
            logo_path = BASE_DIR / "static" / "img" / "MRI_Lab_Logo.png"
            if logo_path.exists():
                pil_image = Image.open(logo_path)
                # Resize to height 60, keeping aspect ratio
                h_size = 60
                w_size = int((float(pil_image.size[0]) * float(h_size)) / float(pil_image.size[1]))
                pil_image = pil_image.resize((w_size, h_size), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(pil_image)
                
                logo_label = ttk.Label(title_frame, image=self.logo_img)
                logo_label.pack(side="left", padx=(0, 20))
        except Exception as e:
            print(f"Failed to load logo: {e}")

        text_frame = ttk.Frame(title_frame)
        text_frame.pack(side="left")
        ttk.Label(text_frame, text="Prism Validator", style="Header.TLabel").pack(anchor="w")
        ttk.Label(text_frame, text="Psychological Dataset Validation & Tools", style="SubHeader.TLabel").pack(anchor="w")
        
        # Lab Info
        lab_frame = ttk.Frame(header_frame)
        lab_frame.pack(side="right")
        ttk.Label(lab_frame, text="MRI-Lab Graz", font=("Segoe UI", 12, "bold"), foreground=self.colors["accent"]).pack(anchor="e")
        ttk.Label(lab_frame, text="Karl Koschutnig", font=("Segoe UI", 9), foreground="#8e8e93").pack(anchor="e")

        # Separator
        ttk.Separator(main_container, orient="horizontal").pack(fill="x", padx=30, pady=10)

        # Content Area
        content_frame = ttk.Frame(main_container, padding="30 10")
        content_frame.pack(fill="both", expand=True)

        # Tabs
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill="both", expand=True)

        # Tab 1: Validator
        self.validator_tab = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(self.validator_tab, text="Dataset Validator")
        self.setup_validator_tab()

        # Tab 2: Survey Tools
        self.survey_tab = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(self.survey_tab, text="Survey Tools")
        self.setup_survey_tab()

    def setup_validator_tab(self):
        # Configuration Section
        config_frame = ttk.LabelFrame(self.validator_tab, text="  Configuration  ", padding="20")
        config_frame.pack(fill="x", pady=(0, 20))
        
        # Grid layout for config
        config_frame.columnconfigure(1, weight=1)
        
        # Dataset Path
        ttk.Label(config_frame, text="Dataset Path:").grid(row=0, column=0, sticky="w", pady=10)
        self.path_var = tk.StringVar()
        entry_frame = ttk.Frame(config_frame) # Wrapper for custom border look
        entry_frame.grid(row=0, column=1, sticky="ew", padx=10)
        
        self.path_entry = ttk.Entry(entry_frame, textvariable=self.path_var)
        self.path_entry.pack(fill="x", ipady=5) # Taller entry
        
        ttk.Button(config_frame, text="Browse Folder", style="Secondary.TButton", command=self.browse_dataset).grid(row=0, column=2, padx=5)

        # Options Row
        options_frame = ttk.Frame(config_frame)
        options_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(15, 0))
        
        # Schema
        ttk.Label(options_frame, text="Schema Version:").pack(side="left", padx=(0, 10))
        self.schema_var = tk.StringVar(value="stable")
        try:
            schema_dir = BASE_DIR / "schemas"
            versions = get_available_schema_versions(str(schema_dir))
        except:
            versions = ["stable"]
        
        self.schema_combo = ttk.Combobox(options_frame, textvariable=self.schema_var, values=versions, state="readonly", width=15, font=("Segoe UI", 10))
        self.schema_combo.pack(side="left", padx=(0, 30))
        
        # BIDS Checkbox
        self.bids_var = tk.BooleanVar(value=False)
        self.bids_check = ttk.Checkbutton(options_frame, text="Run BIDS Validator (Standard)", variable=self.bids_var)
        self.bids_check.pack(side="left")

        # Action Button
        self.run_btn = ttk.Button(self.validator_tab, text="Validate Dataset", command=self.start_validation)
        self.run_btn.pack(pady=10, ipadx=20, ipady=5)

        # Results Area
        results_frame = ttk.LabelFrame(self.validator_tab, text="  Validation Results  ", padding="15")
        results_frame.pack(fill="both", expand=True)
        
        self.results_text = tk.Text(results_frame, wrap="word", font=("Consolas", 11), bg=self.colors["input_bg"], fg=self.colors["fg"], relief="flat", highlightthickness=1, highlightbackground=self.colors["border"])
        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Configure tags
        self.results_text.tag_config("ERROR", foreground=self.colors["error"])
        self.results_text.tag_config("WARNING", foreground=self.colors["warning"])
        self.results_text.tag_config("INFO", foreground=self.colors["accent"])
        self.results_text.tag_config("SUCCESS", foreground=self.colors["success"])
        self.results_text.tag_config("BOLD", font=("Consolas", 11, "bold"))

    def setup_survey_tab(self):
        # Library Path
        lib_frame = ttk.LabelFrame(self.survey_tab, text="  Survey Library  ", padding="20")
        lib_frame.pack(fill="x", pady=(0, 20))
        
        lib_frame.columnconfigure(1, weight=1)
        
        ttk.Label(lib_frame, text="Library Path:").grid(row=0, column=0, sticky="w", pady=5)
        self.lib_path_var = tk.StringVar(value=str(BASE_DIR / "survey_library"))
        
        entry_frame = ttk.Frame(lib_frame)
        entry_frame.grid(row=0, column=1, sticky="ew", padx=10)
        self.lib_path_entry = ttk.Entry(entry_frame, textvariable=self.lib_path_var)
        self.lib_path_entry.pack(fill="x", ipady=5)
        
        btn_frame = ttk.Frame(lib_frame)
        btn_frame.grid(row=0, column=2)
        ttk.Button(btn_frame, text="Browse...", style="Secondary.TButton", command=self.browse_library).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Load Files", command=self.load_library_files).pack(side="left", padx=5)

        # Split Pane
        paned_window = ttk.PanedWindow(self.survey_tab, orient="horizontal")
        paned_window.pack(fill="both", expand=True)

        # Left Pane: Survey Files
        left_frame = ttk.LabelFrame(paned_window, text="  Available Questionnaires  ", padding="10")
        paned_window.add(left_frame, weight=1)
        
        columns = ("filename", "questions")
        self.survey_tree = ttk.Treeview(left_frame, columns=columns, show="headings", selectmode="browse")
        
        self.survey_tree.heading("filename", text="Filename")
        self.survey_tree.heading("questions", text="Items")
        
        self.survey_tree.column("filename", width=250)
        self.survey_tree.column("questions", width=60, anchor="center")
        
        scrollbar_left = ttk.Scrollbar(left_frame, orient="vertical", command=self.survey_tree.yview)
        self.survey_tree.configure(yscrollcommand=scrollbar_left.set)
        
        self.survey_tree.pack(side="left", fill="both", expand=True)
        scrollbar_left.pack(side="right", fill="y")
        
        self.survey_tree.bind("<<TreeviewSelect>>", self.on_survey_select)

        # Right Pane: Questions
        right_frame = ttk.LabelFrame(paned_window, text="  Select Questions  ", padding="10")
        paned_window.add(right_frame, weight=2)

        # Toolbar
        q_toolbar = ttk.Frame(right_frame)
        q_toolbar.pack(fill="x", pady=(0, 10))
        
        ttk.Button(q_toolbar, text="Select All", style="Secondary.TButton", command=self.select_all_questions).pack(side="left", padx=(0, 5))
        ttk.Button(q_toolbar, text="Deselect All", style="Secondary.TButton", command=self.deselect_all_questions).pack(side="left")
        
        self.matrix_var = tk.BooleanVar(value=False)
        self.matrix_check = ttk.Checkbutton(q_toolbar, text="Group as Matrix", variable=self.matrix_var, command=self.on_matrix_change)
        self.matrix_check.pack(side="right")

        # Questions Treeview
        list_container = ttk.Frame(right_frame)
        list_container.pack(fill="both", expand=True)

        columns = ("checked", "id", "description", "scale")
        self.q_tree = ttk.Treeview(list_container, columns=columns, show="headings", selectmode="browse")
        
        self.q_tree.heading("checked", text="✔")
        self.q_tree.heading("id", text="ID")
        self.q_tree.heading("description", text="Question")
        self.q_tree.heading("scale", text="Scale/Options")

        self.q_tree.column("checked", width=40, anchor="center", stretch=False)
        self.q_tree.column("id", width=100, anchor="w")
        self.q_tree.column("description", width=400, anchor="w")
        self.q_tree.column("scale", width=200, anchor="w")

        q_scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.q_tree.yview)
        self.q_tree.configure(yscrollcommand=q_scrollbar.set)

        self.q_tree.pack(side="left", fill="both", expand=True)
        q_scrollbar.pack(side="right", fill="y")

        self.q_tree.bind("<ButtonRelease-1>", self.on_question_click)

        # Export Button
        action_frame = ttk.Frame(self.survey_tab, padding="0 20 0 0")
        action_frame.pack(fill="x")
        
        ttk.Button(action_frame, text="Export Selected to LimeSurvey (.lss)", command=self.export_lss).pack(side="right", ipadx=20, ipady=5)

        # Data storage
        self.survey_data = {} 
        self.selected_questions = {} 
        self.current_survey_filename = None

    # --- Validator Methods ---
    def browse_dataset(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_var.set(folder)

    def start_validation(self):
        dataset_path = self.path_var.get()
        if not dataset_path or not os.path.exists(dataset_path):
            messagebox.showerror("Error", "Please select a valid dataset folder.")
            return

        self.run_btn.config(state="disabled")
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, "Running validation...\n")
        
        thread = threading.Thread(target=self.run_validation_thread, args=(dataset_path,))
        thread.daemon = True
        thread.start()

    def run_validation_thread(self, dataset_path):
        try:
            schema_version = self.schema_var.get()
            run_bids = self.bids_var.get()
            
            if validate_dataset:
                issues, stats = validate_dataset(
                    dataset_path, 
                    verbose=True, 
                    schema_version=schema_version,
                    run_bids=run_bids
                )
                report_text = self.build_cli_like_report(dataset_path, issues, stats)
                self.root.after(0, lambda: self.display_results(report_text))
            else:
                self.root.after(0, lambda: self.display_error("Validator module not loaded"))
        except Exception as e:
            self.root.after(0, lambda: self.display_error(str(e)))

    def build_cli_like_report(self, dataset_path, issues, stats):
        """Mirror the terminal validator output (including surveys and stats)."""
        if print_dataset_summary and print_validation_results:
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                # Match CLI order: summary then validation results
                print_dataset_summary(dataset_path, stats)
                print_validation_results(issues, show_bids_warnings=True)
            return buffer.getvalue()

        # Fallback minimal report
        lines = ["Validation Results", ""]
        lines.append(f"Subjects: {len(stats.subjects)} | Sessions: {len(stats.sessions)} | Tasks: {len(stats.tasks)}")
        error_count = sum(1 for i in issues if i[0] == "ERROR")
        warning_count = sum(1 for i in issues if i[0] == "WARNING")
        lines.append(f"Errors: {error_count} | Warnings: {warning_count}")
        lines.append("")
        for issue in issues:
            level, msg = issue[0], issue[1]
            path = issue[2] if len(issue) > 2 else ""
            line = f"[{level}] {msg}"
            if path:
                line += f"\n    File: {path}"
            lines.append(line)
            lines.append("")
        return "\n".join(lines)

    def display_results(self, report_text):
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, report_text)
        self.run_btn.config(state="normal")

    def display_error(self, error_msg):
        self.results_text.insert(tk.END, f"\n❌ Critical Error: {error_msg}\n", "ERROR")
        self.run_btn.config(state="normal")

    # --- Survey Methods ---
    def browse_library(self):
        folder = filedialog.askdirectory()
        if folder:
            self.lib_path_var.set(folder)
            self.load_library_files()

    def load_library_files(self):
        path = self.lib_path_var.get()
        if not os.path.exists(path):
            messagebox.showerror("Error", "Library path does not exist")
            return

        # Clear existing
        for item in self.survey_tree.get_children():
            self.survey_tree.delete(item)
        self.survey_data = {}
        self.selected_questions = {}
        self.clear_questions_pane()

        try:
            files = []
            for f in os.listdir(path):
                if f.endswith(".json") and not f.startswith("."):
                    full_path = os.path.join(path, f)
                    try:
                        with open(full_path, "r") as jf:
                            data = json.load(jf)
                            desc = data.get("Study", {}).get("Description", "") or data.get("TaskName", "")
                            
                            # Extract questions
                            questions = []
                            if "Questions" in data and isinstance(data["Questions"], dict):
                                for k, v in data["Questions"].items():
                                    q_desc = v.get("Description", "") if isinstance(v, dict) else ""
                                    q_levels = v.get("Levels") if isinstance(v, dict) else None
                                    q_choices = v.get("Options") if isinstance(v, dict) else None
                                    q_unit = (v.get("Unit") or v.get("Units")) if isinstance(v, dict) else None
                                    questions.append({"id": k, "description": q_desc, "levels": q_levels, "choices": q_choices, "unit": q_unit})
                            else:
                                reserved = ["Technical", "Study", "Metadata", "Categories", "TaskName", "Name", "BIDSVersion", "Description", "URL", "License", "Authors", "Acknowledgements", "References", "Funding"]
                                for k, v in data.items():
                                    if k not in reserved:
                                        q_desc = v.get("Description", "") if isinstance(v, dict) else ""
                                        q_levels = v.get("Levels") if isinstance(v, dict) else None
                                        q_choices = v.get("Options") if isinstance(v, dict) else None
                                        q_unit = (v.get("Unit") or v.get("Units")) if isinstance(v, dict) else None
                                        questions.append({"id": k, "description": q_desc, "levels": q_levels, "choices": q_choices, "unit": q_unit})
                            
                            self.survey_data[f] = {
                                "path": full_path,
                                "questions": questions,
                                "description": desc
                            }
                            
                            # Initialize selection state (all selected by default)
                            self.selected_questions[f] = {
                                "questions": {q["id"]: tk.BooleanVar(value=True) for q in questions},
                                "matrix": tk.BooleanVar(value=False)
                            }
                            
                            files.append((f, len(questions)))
                    except:
                        continue
            
            # Sort and insert
            files.sort(key=lambda x: x[0])
            for f in files:
                self.survey_tree.insert("", "end", values=(f[0], f[1]), tags=(f[0],)) # Store filename in tags
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load library: {e}")

    def on_survey_select(self, event):
        selected_items = self.survey_tree.selection()
        if not selected_items:
            return
        
        # Get filename from tags
        filename = self.survey_tree.item(selected_items[0], "tags")[0]
        self.current_survey_filename = filename
        self.show_questions_for_survey(filename)

    def show_questions_for_survey(self, filename):
        self.clear_questions_pane()
        
        if filename not in self.survey_data:
            return

        data = self.survey_data[filename]
        state = self.selected_questions[filename]
        
        # Update Matrix Checkbox
        self.matrix_var.set(state["matrix"].get())

        def format_scale(levels, choices, unit):
            # Convert available scale/choice information into a compact string for display.
            parts = []
            if isinstance(levels, dict):
                try:
                    sorted_keys = sorted(levels.keys(), key=lambda k: float(k))
                except Exception:
                    sorted_keys = sorted(levels.keys())
                entries = [f"{k}: {levels[k]}" for k in sorted_keys]
                parts.append("Scale " + " | ".join(entries))
            elif isinstance(levels, list):
                entries = [str(item) for item in levels]
                parts.append("Scale " + " | ".join(entries))
            if choices:
                if isinstance(choices, dict):
                    entries = [f"{k}: {choices[k]}" for k in choices]
                    parts.append("Options " + " | ".join(entries))
                elif isinstance(choices, list):
                    parts.append("Options " + " | ".join(str(c) for c in choices))
            if unit:
                parts.append(f"Unit: {unit}")
            return " | ".join(parts)
        
        # Populate Questions
        for q in data["questions"]:
            q_id = q["id"]
            q_desc = q["description"]
            q_scale = format_scale(q.get("levels"), q.get("choices"), q.get("unit"))
            
            is_checked = state["questions"][q_id].get()
            check_mark = "☒" if is_checked else "☐"
            
            self.q_tree.insert("", "end", values=(check_mark, q_id, q_desc, q_scale), tags=(q_id,))

    def clear_questions_pane(self):
        for item in self.q_tree.get_children():
            self.q_tree.delete(item)

    def on_question_click(self, event):
        region = self.q_tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.q_tree.identify_column(event.x)
            item_id = self.q_tree.identify_row(event.y)
            
            if not item_id:
                return

            # If clicked on the checkbox column (column #1 which is "checked")
            if column == "#1":
                self.toggle_question(item_id)

    def toggle_question(self, item_id):
        if not self.current_survey_filename:
            return
            
        values = self.q_tree.item(item_id, "values")
        q_id = values[1] # ID is in the second column
        
        current_state = self.selected_questions[self.current_survey_filename]["questions"][q_id].get()
        new_state = not current_state
        self.selected_questions[self.current_survey_filename]["questions"][q_id].set(new_state)
        
        # Update UI
        check_mark = "☒" if new_state else "☐"
        self.q_tree.item(item_id, values=(check_mark, values[1], values[2], values[3]))

    def on_matrix_change(self):
        if self.current_survey_filename:
            self.selected_questions[self.current_survey_filename]["matrix"].set(self.matrix_var.get())

    def select_all_questions(self):
        if self.current_survey_filename:
            for var in self.selected_questions[self.current_survey_filename]["questions"].values():
                var.set(True)
            self.refresh_question_list()

    def deselect_all_questions(self):
        if self.current_survey_filename:
            for var in self.selected_questions[self.current_survey_filename]["questions"].values():
                var.set(False)
            self.refresh_question_list()

    def refresh_question_list(self):
        if self.current_survey_filename:
            self.show_questions_for_survey(self.current_survey_filename)

    def export_lss(self):
        # Collect all selected files and their selected questions
        export_list = []
        
        for filename, state in self.selected_questions.items():
            # Check if any question is selected
            selected_q_ids = [qid for qid, var in state["questions"].items() if var.get()]
            
            if selected_q_ids:
                export_list.append({
                    "path": self.survey_data[filename]["path"],
                    "include": selected_q_ids,
                    "matrix": state["matrix"].get()
                })

        if not export_list:
            messagebox.showwarning("Warning", "Please select at least one question from one survey to export.")
            return

        save_path = filedialog.asksaveasfilename(defaultextension=".lss", filetypes=[("LimeSurvey Structure", "*.lss")])
        if not save_path:
            return

        try:
            if generate_lss:
                generate_lss(export_list, save_path)
                messagebox.showinfo("Success", f"Exported {len(export_list)} surveys to:\n{save_path}")
            else:
                messagebox.showerror("Error", "LSS Exporter module not loaded")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

if __name__ == "__main__":
    # We don't need ThemedTk if we are using our own theme
    root = tk.Tk()
    app = PrismValidatorGUI(root)
    root.mainloop()
