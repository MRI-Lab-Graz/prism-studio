import tkinter.ttk as ttk

def apply_prism_theme(root):
    """
    Applies the custom 'Prism' theme to the application.
    Returns the color palette used.
    """
    style = ttk.Style(root)
    
    # Define our custom color palette (Web-Interface Style: Light/Clean)
    colors = {
        "bg": "#f8f9fa",          # Light grey background (Bootstrap body-bg)
        "fg": "#212529",          # Dark text (Bootstrap body-color)
        "accent": "#0d6efd",      # Primary Blue
        "button": "#0d6efd",      # Primary Blue buttons
        "button_hover": "#0b5ed7",
        "secondary": "#ffffff",   # White background for cards/panels
        "border": "#dee2e6",      # Light grey border
        "input_bg": "#ffffff",    # White input fields
        "success": "#198754",     # Success Green
        "error": "#dc3545",       # Danger Red
        "warning": "#ffc107"      # Warning Yellow
    }

    # Create the 'prism' theme based on 'clam'
    # We use 'clam' as a base because it allows for extensive customization
    if "prism" not in style.theme_names():
        style.theme_create("prism", parent="clam", settings={
            ".": {
                "configure": {
                    "background": colors["bg"],
                    "foreground": colors["fg"],
                    "font": ("Segoe UI", 10),
                    "bordercolor": colors["border"],
                    "lightcolor": colors["border"],
                    "darkcolor": colors["border"],
                }
            },
            "TFrame": {
                "configure": {"background": colors["bg"]}
            },
            "TNotebook": {
                "configure": {
                    "background": colors["bg"],
                    "borderwidth": 0,
                    "tabmargins": [0, 10, 0, 0]
                }
            },
            "TNotebook.Tab": {
                "configure": {
                    "padding": [20, 10],
                    "font": ("Segoe UI", 11),
                    "background": "#e9ecef", # Light grey for inactive tabs
                    "foreground": "#6c757d", # Muted text
                    "borderwidth": 0,
                    "focuscolor": colors["bg"]
                },
                "map": {
                    "background": [("selected", colors["secondary"])], # White for active
                    "foreground": [("selected", colors["fg"])],        # Dark text for active
                    "font": [("selected", ("Segoe UI", 11, "bold"))]
                }
            },
            "TButton": {
                "configure": {
                    "font": ("Segoe UI", 10, "bold"),
                    "background": colors["button"],
                    "foreground": "white",
                    "borderwidth": 0,
                    "focuscolor": colors["bg"], # Remove focus ring
                    "padding": [15, 8]
                },
                "map": {
                    "background": [("active", colors["button_hover"]), ("disabled", "#6c757d")]
                }
            },
            "Secondary.TButton": {
                "configure": {
                    "background": "#e9ecef",
                    "foreground": colors["fg"],
                    "borderwidth": 0,
                },
                "map": {
                    "background": [("active", "#dde0e3")]
                }
            },
            "TEntry": {
                "configure": {
                    "fieldbackground": colors["input_bg"],
                    "foreground": colors["fg"],
                    "padding": 5,
                    "relief": "solid",
                    "borderwidth": 1,
                    "bordercolor": colors["border"],
                    "insertcolor": colors["fg"] # Cursor color
                }
            },
            "Treeview": {
                "configure": {
                    "background": colors["input_bg"],
                    "fieldbackground": colors["input_bg"],
                    "foreground": colors["fg"],
                    "rowheight": 35,
                    "borderwidth": 0,
                    "font": ("Segoe UI", 10)
                },
                "map": {
                    "background": [("selected", "#e7f1ff")], # Very light blue selection
                    "foreground": [("selected", colors["fg"])]
                }
            },
            "Treeview.Heading": {
                "configure": {
                    "font": ("Segoe UI", 10, "bold"),
                    "background": "#f1f3f5",
                    "foreground": colors["fg"],
                    "relief": "flat",
                    "padding": [10, 8]
                }
            },
            "TLabelframe": {
                "configure": {
                    "background": colors["secondary"],
                    "borderwidth": 1,
                    "relief": "solid",
                    "bordercolor": colors["border"]
                }
            },
            "TLabelframe.Label": {
                "configure": {
                    "background": colors["secondary"],
                    "foreground": colors["fg"],
                    "font": ("Segoe UI", 11, "bold")
                }
            },
            # Custom styles that don't map directly to standard widgets
            "Header.TLabel": {
                "configure": {
                    "font": ("Segoe UI", 28, "bold"),
                    "foreground": colors["fg"],
                    "background": colors["bg"]
                }
            },
            "SubHeader.TLabel": {
                "configure": {
                    "font": ("Segoe UI", 12),
                    "foreground": "#6c757d",
                    "background": colors["bg"]
                }
            },
            "Section.TLabel": {
                "configure": {
                    "font": ("Segoe UI", 14, "bold"),
                    "foreground": colors["fg"],
                    "background": colors["secondary"]
                }
            },
            "List.TFrame": {
                "configure": {"background": colors["input_bg"]}
            },
            "List.TLabel": {
                "configure": {
                    "background": colors["input_bg"],
                    "foreground": colors["fg"]
                }
            },
            "List.TCheckbutton": {
                "configure": {
                    "background": colors["input_bg"],
                    "foreground": colors["fg"]
                }
            },
            "Card.TFrame": {
                "configure": {
                    "background": colors["secondary"],
                    "relief": "solid",
                    "borderwidth": 1,
                    "bordercolor": colors["border"]
                }
            }
        })

    style.theme_use("prism")
    return colors
