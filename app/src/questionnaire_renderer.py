"""
Render a PRISM survey template as a Word (.docx) questionnaire document.

Requires python-docx (optional dependency).
"""
from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Optional


def _get_localized(value, lang: str) -> str:
    """Extract localized text, falling back to any available language."""
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if lang in value:
            return str(value[lang])
        for v in value.values():
            if isinstance(v, str) and v.strip():
                return v
    return str(value) if value else ""


def _item_keys(template: dict) -> list[str]:
    """Return sorted item keys from template (excluding Study/Technical metadata)."""
    skip = {
        "Study", "Technical", "Scoring", "LimeSurvey",
        "MatrixGrouping", "TemplateVersion",
    }
    keys = []
    for k, v in template.items():
        if k in skip or not isinstance(v, dict):
            continue
        if "Description" not in v:
            continue
        keys.append(k)
    keys.sort()
    return keys


def _detect_question_type(item: dict) -> str:
    """Detect question rendering type from item properties."""
    ls_type = (item.get("LimeSurvey") or {}).get("questionType", "")
    if ls_type in ("!", ):
        return "dropdown"
    if ls_type in ("N", "K"):
        return "numerical"
    if ls_type in ("S",):
        return "short-text"
    if ls_type in ("T", "U"):
        return "long-text"
    if ls_type in ("D",):
        return "date"
    if ls_type in ("*", "X"):
        return "hidden"

    input_type = item.get("InputType", "")
    if input_type == "slider":
        return "slider"
    if input_type == "dropdown":
        return "dropdown"
    if input_type == "numerical":
        return "numerical"
    if input_type == "calculated":
        return "hidden"
    if input_type == "text":
        tc = item.get("TextConfig") or {}
        return "long-text" if tc.get("multiline") else "short-text"

    # Check variant scale
    for vs in item.get("VariantScales") or []:
        st = (vs or {}).get("ScaleType", "")
        if st in ("vas", "visual-analogue"):
            return "slider"

    levels = item.get("Levels")
    if levels and isinstance(levels, dict) and len(levels) > 0:
        return "dropdown" if len(levels) > 10 else "radio"

    return "short-text"


def _get_levels(item: dict, variant_id: Optional[str] = None) -> dict:
    """Get levels for an item, respecting variant-specific scales."""
    if variant_id:
        for vs in item.get("VariantScales") or []:
            if (vs or {}).get("VariantID") == variant_id:
                lvls = vs.get("Levels")
                if lvls and isinstance(lvls, dict) and len(lvls) > 0:
                    return lvls
    return item.get("Levels") or {}


def render_questionnaire_docx(
    template: dict,
    language: str = "en",
    variant_id: Optional[str] = None,
) -> io.BytesIO:
    """
    Render a PRISM survey template as a Word document.

    Returns a BytesIO containing the .docx file.
    """
    try:
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        raise ImportError(
            "python-docx is required for Word export. "
            "Install it with: pip install python-docx"
        )

    doc = Document()

    # -- Page margins
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

    study = template.get("Study") or {}

    # -- Title
    title_text = _get_localized(study.get("OriginalName"), language)
    short_name = study.get("ShortName", "")
    if title_text:
        title_para = doc.add_heading(level=1)
        run = title_para.add_run(title_text)
        run.font.size = Pt(18)
        run.font.color.rgb = RGBColor(0x1F, 0x23, 0x28)
        if short_name:
            run2 = title_para.add_run(f"  ({short_name})")
            run2.font.size = Pt(12)
            run2.font.color.rgb = RGBColor(0x6C, 0x75, 0x7D)

    # -- Byline (authors, year)
    meta_parts = []
    authors = study.get("Authors")
    if authors:
        if isinstance(authors, list):
            meta_parts.append(", ".join(str(a) for a in authors))
        else:
            meta_parts.append(str(authors))
    year = study.get("Year")
    if year:
        meta_parts.append(str(year))
    if meta_parts:
        byline = doc.add_paragraph()
        run = byline.add_run(" — ".join(meta_parts))
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x6C, 0x75, 0x7D)

    if variant_id:
        vp = doc.add_paragraph()
        run = vp.add_run(f"Variant: {variant_id}")
        run.font.size = Pt(9)
        run.bold = True
        run.font.color.rgb = RGBColor(0x0D, 0x6E, 0xFD)

    # -- Instructions
    instructions = _get_localized(study.get("Instructions"), language)
    if instructions:
        doc.add_paragraph()  # spacer
        instr_para = doc.add_paragraph()
        run_label = instr_para.add_run("Instructions: ")
        run_label.bold = True
        run_label.font.size = Pt(10)
        run_text = instr_para.add_run(instructions)
        run_text.font.size = Pt(10)
        # Add a visual separator
        sep = doc.add_paragraph()
        sep_run = sep.add_run("─" * 60)
        sep_run.font.size = Pt(8)
        sep_run.font.color.rgb = RGBColor(0xDE, 0xE2, 0xE6)

    # -- Items
    item_keys = _item_keys(template)
    question_num = 0

    for key in item_keys:
        item = template[key]
        q_type = _detect_question_type(item)
        if q_type == "hidden":
            continue

        # Skip items not in active variant
        applicable = item.get("ApplicableVersions")
        if variant_id and isinstance(applicable, list) and len(applicable) > 0:
            if variant_id not in applicable:
                continue

        question_num += 1
        levels = _get_levels(item, variant_id)

        # Question header: number + code + description
        q_para = doc.add_paragraph()
        q_para.space_before = Pt(8)
        q_para.space_after = Pt(2)

        num_run = q_para.add_run(f"{question_num}. ")
        num_run.bold = True
        num_run.font.size = Pt(11)
        num_run.font.color.rgb = RGBColor(0x1F, 0x8B, 0x5C)

        code_run = q_para.add_run(f"[{key}]  ")
        code_run.font.size = Pt(8)
        code_run.font.color.rgb = RGBColor(0x6C, 0x75, 0x7D)

        desc_text = _get_localized(item.get("Description"), language)
        desc_run = q_para.add_run(desc_text or "(no description)")
        desc_run.font.size = Pt(11)

        # Badges
        if item.get("Reversed"):
            badge = q_para.add_run("  [R]")
            badge.font.size = Pt(8)
            badge.font.color.rgb = RGBColor(0xFF, 0xC1, 0x07)
            badge.bold = True

        # Item-level instructions
        item_instr = _get_localized(item.get("Instructions"), language)
        if item_instr:
            ip = doc.add_paragraph()
            ip.space_before = Pt(0)
            ip.space_after = Pt(2)
            ir = ip.add_run(f"  {item_instr}")
            ir.font.size = Pt(9)
            ir.italic = True
            ir.font.color.rgb = RGBColor(0x6C, 0x75, 0x7D)

        # -- Response rendering
        if q_type == "radio" and levels:
            sorted_keys = sorted(levels.keys(), key=lambda x: _safe_num(x))
            for lk in sorted_keys:
                lv_text = _get_localized(levels[lk], language)
                rp = doc.add_paragraph(style="List Bullet")
                rp.space_before = Pt(0)
                rp.space_after = Pt(0)
                rp.paragraph_format.left_indent = Inches(0.4)
                run_circle = rp.add_run("○  ")
                run_circle.font.size = Pt(11)
                run_code = rp.add_run(f"{lk}: ")
                run_code.font.size = Pt(9)
                run_code.font.color.rgb = RGBColor(0x6C, 0x75, 0x7D)
                run_label = rp.add_run(lv_text)
                run_label.font.size = Pt(10)

        elif q_type == "dropdown" and levels:
            sorted_keys = sorted(levels.keys(), key=lambda x: _safe_num(x))
            dp = doc.add_paragraph()
            dp.space_before = Pt(2)
            dp.paragraph_format.left_indent = Inches(0.4)
            dr = dp.add_run("▼ [ ")
            dr.font.size = Pt(10)
            opts = []
            for lk in sorted_keys[:5]:
                opts.append(_get_localized(levels[lk], language))
            dr2 = dp.add_run(" | ".join(opts))
            dr2.font.size = Pt(9)
            dr2.font.color.rgb = RGBColor(0x6C, 0x75, 0x7D)
            if len(sorted_keys) > 5:
                dr3 = dp.add_run(f" ... +{len(sorted_keys) - 5} more")
                dr3.font.size = Pt(8)
                dr3.font.color.rgb = RGBColor(0x99, 0x99, 0x99)
            dr4 = dp.add_run(" ]")
            dr4.font.size = Pt(10)

        elif q_type == "numerical":
            np = doc.add_paragraph()
            np.paragraph_format.left_indent = Inches(0.4)
            np.space_before = Pt(2)
            nr = np.add_run("[________]")
            nr.font.size = Pt(10)
            parts = []
            if item.get("MinValue") is not None:
                parts.append(f"Min: {item['MinValue']}")
            if item.get("MaxValue") is not None:
                parts.append(f"Max: {item['MaxValue']}")
            if item.get("Unit"):
                parts.append(item["Unit"])
            if parts:
                hint = np.add_run(f"  ({', '.join(parts)})")
                hint.font.size = Pt(8)
                hint.font.color.rgb = RGBColor(0x6C, 0x75, 0x7D)

        elif q_type == "slider":
            sc = item.get("SliderConfig") or {}
            min_v = sc.get("min", item.get("MinValue", 0))
            max_v = sc.get("max", item.get("MaxValue", 100))
            sp = doc.add_paragraph()
            sp.paragraph_format.left_indent = Inches(0.4)
            sp.space_before = Pt(2)
            sr = sp.add_run(f"{min_v}  |")
            sr.font.size = Pt(9)
            bar = sp.add_run("━" * 30)
            bar.font.size = Pt(9)
            bar.font.color.rgb = RGBColor(0x1F, 0x8B, 0x5C)
            sr2 = sp.add_run(f"|  {max_v}")
            sr2.font.size = Pt(9)

        elif q_type == "long-text":
            tp = doc.add_paragraph()
            tp.paragraph_format.left_indent = Inches(0.4)
            tp.space_before = Pt(2)
            for _ in range(3):
                tr = tp.add_run("_" * 70 + "\n")
                tr.font.size = Pt(9)
                tr.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)

        elif q_type == "date":
            dp = doc.add_paragraph()
            dp.paragraph_format.left_indent = Inches(0.4)
            dp.space_before = Pt(2)
            dr = dp.add_run("[____ / ____ / ________]  (DD / MM / YYYY)")
            dr.font.size = Pt(10)
            dr.font.color.rgb = RGBColor(0x6C, 0x75, 0x7D)

        else:  # short-text
            tp = doc.add_paragraph()
            tp.paragraph_format.left_indent = Inches(0.4)
            tp.space_before = Pt(2)
            tr = tp.add_run("_" * 50)
            tr.font.size = Pt(10)
            tr.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)

    # -- Footer
    doc.add_paragraph()
    sep = doc.add_paragraph()
    sep_run = sep.add_run("─" * 60)
    sep_run.font.size = Pt(8)
    sep_run.font.color.rgb = RGBColor(0xDE, 0xE2, 0xE6)

    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = footer.add_run(
        f"Generated by PRISM Studio — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    fr.font.size = Pt(8)
    fr.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    if question_num > 0:
        count_para = doc.add_paragraph()
        count_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cr = count_para.add_run(f"{question_num} items")
        cr.font.size = Pt(8)
        cr.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

    # -- Write to buffer
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def _safe_num(val):
    """Sort key that handles numeric and string level codes."""
    try:
        return (0, float(val))
    except (ValueError, TypeError):
        return (1, str(val))
