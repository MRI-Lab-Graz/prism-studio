"""Survey-derivatives computation.

This module implements the logic behind `prism_tools.py derivatives surveys` as a
reusable API, so both the CLI and the Web/GUI can call the same code.

It reads derivative *recipes* from the repository's `derivatives/surveys/*.json`
folder and writes outputs into the target dataset under:

- `derivatives/surveys/<recipe_id>/sub-*/ses-*/survey/*_desc-scores_beh.tsv` (format="prism")
- or `derivatives/survey_derivatives.tsv` (format="flat")

Additionally, it creates `derivatives/surveys/dataset_description.json` in the
output dataset (BIDS-derivatives style).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import csv
import json


@dataclass(frozen=True)
class SurveyDerivativesResult:
	processed_files: int
	written_files: int
	out_format: str
	out_root: Path
	flat_out_path: Path | None


def _ensure_dir(path: Path) -> Path:
	path.mkdir(parents=True, exist_ok=True)
	return path


def _read_json(path: Path) -> dict:
	with open(path, "r", encoding="utf-8") as f:
		return json.load(f)


def _write_json(path: Path, obj: dict) -> None:
	_ensure_dir(path.parent)
	with open(path, "w", encoding="utf-8") as f:
		json.dump(obj, f, indent=2, ensure_ascii=False)


def _read_tsv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
	with open(path, "r", encoding="utf-8", newline="") as f:
		reader = csv.DictReader(f, delimiter="\t")
		header = list(reader.fieldnames or [])
		rows = [dict(r) for r in reader]
	return header, rows


def _write_tsv_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
	_ensure_dir(path.parent)
	with open(path, "w", encoding="utf-8", newline="") as f:
		writer = csv.DictWriter(f, fieldnames=header, delimiter="\t", lineterminator="\n")
		writer.writeheader()
		for r in rows:
			writer.writerow({k: r.get(k, "") for k in header})


def _normalize_survey_key(raw: str) -> str:
	s = str(raw or "").strip().lower()
	if not s:
		return s
	for prefix in ("survey-", "task-"):
		if s.startswith(prefix):
			s = s[len(prefix) :]
	return s


def _extract_task_from_survey_filename(path: Path) -> str | None:
	stem = path.stem
	# Examples:
	# sub-001_ses-1_task-ads_beh.tsv
	# sub-001_ses-1_survey-ads_beh.tsv
	for token in stem.split("_"):
		if token.startswith("task-"):
			return _normalize_survey_key(token)
		if token.startswith("survey-"):
			return _normalize_survey_key(token)
	return None


def _infer_sub_ses_from_path(path: Path) -> tuple[str | None, str | None]:
	sub_id = None
	ses_id = None
	for part in path.parts:
		# Avoid treating the TSV filename (e.g. "sub-001_ses-1_task-ads_beh.tsv")
		# as a subject/session folder.
		if sub_id is None and part.startswith("sub-") and Path(part).suffix == "":
			sub_id = part
		if ses_id is None and part.startswith("ses-") and Path(part).suffix == "":
			ses_id = part
	return sub_id, ses_id


def _parse_numeric_cell(val: str | None) -> float | None:
	if val is None:
		return None
	s = str(val).strip()
	if not s or s.lower() == "n/a":
		return None
	try:
		return float(s)
	except ValueError:
		return None


def _format_numeric_cell(val: float | None) -> str:
	if val is None:
		return "n/a"
	if float(val).is_integer():
		return str(int(val))
	return str(val)


def _apply_survey_derivative_recipe_to_rows(
	recipe: dict, rows: list[dict[str, str]]
) -> tuple[list[str], list[dict[str, str]]]:
	transforms = recipe.get("Transforms", {}) or {}
	invert_cfg = transforms.get("Invert") or {}
	invert_items = set(invert_cfg.get("Items") or [])
	invert_scale = invert_cfg.get("Scale") or {}
	invert_min = invert_scale.get("min")
	invert_max = invert_scale.get("max")

	scores = recipe.get("Scores") or []
	out_header = [str(s.get("Name", "")).strip() for s in scores if str(s.get("Name", "")).strip()]
	out_rows: list[dict[str, str]] = []

	for row in rows:

		def _get_item_value(item_id: str) -> float | None:
			raw = row.get(item_id)
			v = _parse_numeric_cell(raw)
			if v is None:
				return None
			if item_id in invert_items and invert_min is not None and invert_max is not None:
				try:
					return float(invert_max) + float(invert_min) - float(v)
				except Exception:
					return v
			return v

		out: dict[str, str] = {}
		for score in scores:
			name = str(score.get("Name", "")).strip()
			if not name:
				continue
			method = str(score.get("Method", "sum")).strip().lower()
			items = [str(i).strip() for i in (score.get("Items") or []) if str(i).strip()]
			missing = str(score.get("Missing", "ignore")).strip().lower()

			values: list[float] = []
			any_missing = False
			for item_id in items:
				v = _get_item_value(item_id)
				if v is None:
					any_missing = True
				else:
					values.append(v)

			result: float | None
			if missing in {"require_all", "all", "strict"} and any_missing:
				result = None
			elif not values:
				result = None
			else:
				if method == "mean":
					result = sum(values) / float(len(values))
				else:
					result = sum(values)

			out[name] = _format_numeric_cell(result)

		out_rows.append(out)

	return out_header, out_rows


def _write_derivatives_dataset_description(*, out_root: Path) -> None:
	"""Create a BIDS-derivatives dataset_description.json under derivatives/surveys/."""

	desc_path = out_root / "dataset_description.json"
	if desc_path.exists():
		return

	obj = {
		"Name": "PRISM Survey Derivatives",
		"BIDSVersion": "1.8.0",
		"DatasetType": "derivative",
		"GeneratedBy": [
			{
				"Name": "prism-tools",
				"Description": "Survey derivative scoring (reverse coding, subscales)",
				"Version": "unknown",
				"CodeURL": "",
			}
		],
		"GeneratedOn": datetime.now().isoformat(timespec="seconds"),
	}

	_write_json(desc_path, obj)


def compute_survey_derivatives(
	*,
	prism_root: str | Path,
	repo_root: str | Path,
	survey: str | None = None,
	out_format: str = "prism",
	modality: str = "survey",
) -> SurveyDerivativesResult:
	"""Compute survey derivatives in a PRISM dataset.

	Args:
		prism_root: Target PRISM dataset root (must exist).
		repo_root: Repository root (used to locate recipe JSONs).
		survey: Optional comma-separated recipe ids to apply.
		out_format: "prism" or "flat".

	Raises:
		ValueError: For user errors (missing paths, unknown recipes, etc.).
		RuntimeError: For unexpected failures.
	"""

	prism_root = Path(prism_root).resolve()
	repo_root = Path(repo_root).resolve()

	if not prism_root.exists() or not prism_root.is_dir():
		raise ValueError(f"--prism is not a directory: {prism_root}")

	modality = str(modality or "survey").strip().lower()
	out_format = str(out_format or "csv").strip().lower()

	# For survey modality we expect file formats (csv, xlsx, sav, r).
	if modality == "survey":
		if out_format not in {"csv", "xlsx", "sav", "r"}:
			raise ValueError("For modality=survey --format must be one of: csv, xlsx, sav, r")
	else:
		# keep legacy behaviour for other modalities
		if out_format not in {"prism", "flat", "csv", "xlsx", "sav", "r"}:
			raise ValueError("--format must be one of: prism, flat, csv, xlsx, sav, r")

	recipes_dir = (repo_root / "derivatives" / "surveys").resolve()
	if not recipes_dir.exists() or not recipes_dir.is_dir():
		raise ValueError(f"Missing recipe folder: {recipes_dir}. Expected derivatives/surveys/*.json")

	recipe_paths = sorted(recipes_dir.glob("*.json"))
	if not recipe_paths:
		raise ValueError(f"No survey derivative recipes found in: {recipes_dir}")

	recipes: dict[str, dict] = {}
	for p in recipe_paths:
		try:
			recipe = _read_json(p)
		except Exception:
			continue
		recipe_id = _normalize_survey_key(p.stem)
		recipes[recipe_id] = {"path": p, "json": recipe}

	if not recipes:
		raise ValueError("No valid recipes could be loaded.")

	selected: set[str] | None = None
	if survey:
		parts = [p.strip() for p in str(survey).replace(";", ",").split(",")]
		parts = [_normalize_survey_key(p) for p in parts if p.strip()]
		selected = set([p for p in parts if p])
		unknown = sorted([s for s in selected if s not in recipes])
		if unknown:
			raise ValueError(
				"Unknown survey recipe names: "
				+ ", ".join(unknown)
				+ ". Available: "
				+ ", ".join(sorted(recipes.keys()))
			)

	# Scan dataset for survey TSV files
	tsv_files: list[Path] = []
	tsv_files.extend(prism_root.glob("sub-*/ses-*/survey/*.tsv"))
	tsv_files.extend(prism_root.glob("sub-*/survey/*.tsv"))
	tsv_files = sorted(set([p for p in tsv_files if p.is_file()]))
	if not tsv_files:
		raise ValueError(f"No survey TSV files found under: {prism_root}")

	out_root = prism_root / "derivatives" / "surveys"
	processed_files = 0
	written_files = 0

	flat_out_path: Path | None = None

	# If modality=survey we will write one flat file per survey (recipe)
	for recipe_id, rec in sorted(recipes.items()):
		if selected is not None and recipe_id not in selected:
			continue

		recipe = rec["json"]
		survey_task = _normalize_survey_key((recipe.get("Survey", {}) or {}).get("TaskName") or recipe_id)

		matching = [p for p in tsv_files if _extract_task_from_survey_filename(p) == survey_task]
		if not matching:
			continue

		if modality == "survey":
			# Accumulate scores across all matching participant TSVs for this survey
			rows_accum: list[dict[str, object]] = []
			for in_path in matching:
				processed_files += 1
				sub_id, ses_id = _infer_sub_ses_from_path(in_path)
				if not sub_id:
					continue
				if not ses_id:
					ses_id = "ses-1"

				in_header, in_rows = _read_tsv_rows(in_path)
				if not in_header or not in_rows:
					continue

				out_header, out_rows = _apply_survey_derivative_recipe_to_rows(recipe, in_rows)
				if not out_header:
					continue

				for row_index, score_row in enumerate(out_rows):
					merged = {"participant_id": sub_id, "session": ses_id}
					for col in out_header:
						merged[col] = score_row.get(col, "n/a")
					rows_accum.append(merged)

			if not rows_accum:
				continue

			# Write a single file for this survey
			_ensure_dir(out_root)
			try:
				import pandas as pd
			except Exception:
				raise RuntimeError("pandas is required to write flat survey outputs (install pandas)")

			df = pd.DataFrame(rows_accum)
			# Ensure column order: participant_id, session, then score columns
			cols = [c for c in (['participant_id', 'session'] + [c for c in out_header]) if c in df.columns]
			df = df.loc[:, cols]

			out_fname = None
			if out_format == 'csv':
				out_fname = out_root / f"{recipe_id}.csv"
				df.to_csv(out_fname, index=False)
			elif out_format == 'xlsx':
				out_fname = out_root / f"{recipe_id}.xlsx"
				df.to_excel(out_fname, index=False)
			elif out_format == 'sav':
				out_fname = out_root / f"{recipe_id}.sav"
				try:
					import pyreadstat

					# pyreadstat expects pandas DataFrame
					pyreadstat.write_sav(df, str(out_fname))
				except Exception:
					# Fallback to CSV if pyreadstat not available
					out_fname = out_root / f"{recipe_id}.csv"
					df.to_csv(out_fname, index=False)
			elif out_format == 'r':
				# Try to write a feather file (widely readable by R via arrow)
				out_fname = out_root / f"{recipe_id}.feather"
				try:
					df.to_feather(out_fname)
				except Exception:
					# Fallback to CSV
					out_fname = out_root / f"{recipe_id}.csv"
					df.to_csv(out_fname, index=False)

			if out_fname and out_fname.exists():
				written_files += 1

		else:
			# legacy behaviour (prism/flat per-participant outputs)
			for in_path in matching:
				processed_files += 1
				sub_id, ses_id = _infer_sub_ses_from_path(in_path)
				if not sub_id:
					continue
				if not ses_id:
					ses_id = "ses-1"

				in_header, in_rows = _read_tsv_rows(in_path)
				if not in_header or not in_rows:
					continue

				out_header, out_rows = _apply_survey_derivative_recipe_to_rows(recipe, in_rows)
				if not out_header:
					break

				if out_format == "flat":
					prefix = f"{recipe_id}_"
					for row_index, score_row in enumerate(out_rows):
						key = (sub_id, ses_id, recipe_id, row_index)
						if key in flat_key_to_idx:
							merged = flat_rows[flat_key_to_idx[key]]
						else:
							merged = {"participant_id": sub_id, "session": ses_id, "survey": recipe_id}
							flat_key_to_idx[key] = len(flat_rows)
							flat_rows.append(merged)

						for col in out_header:
							merged[prefix + col] = score_row.get(col, "n/a")

					written_files += 1
				else:
					out_dir = out_root / recipe_id / sub_id / ses_id / "survey"
					stem = in_path.stem
					if stem.endswith("_beh"):
						new_stem = stem[:-4] + "_desc-scores_beh"
					else:
						new_stem = stem + "_desc-scores"
					out_path = out_dir / f"{new_stem}.tsv"
					_write_tsv_rows(out_path, out_header, out_rows)
					written_files += 1

	if written_files == 0:
		msg = "No matching recipes applied."
		if selected:
			msg += " (No survey TSV matched the selected --survey.)"
		else:
			msg += " (No survey TSV matched any recipe TaskName.)"
		raise ValueError(msg)

	if out_format == "flat":
		fixed = ["participant_id", "session", "survey"]
		score_cols = sorted({k for r in flat_rows for k in r.keys() if k not in fixed})
		flat_header = fixed + score_cols
		flat_out_path = prism_root / "derivatives" / "survey_derivatives.tsv"
		_write_tsv_rows(flat_out_path, flat_header, flat_rows)

	_ensure_dir(out_root)
	_write_derivatives_dataset_description(out_root=out_root)

	return SurveyDerivativesResult(
		processed_files=processed_files,
		written_files=written_files,
		out_format=out_format,
		out_root=out_root,
		flat_out_path=flat_out_path,
	)