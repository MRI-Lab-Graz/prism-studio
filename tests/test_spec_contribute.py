"""The Propose-changes catalog: what can be proposed, without any project."""

from src.spec_contribute import spec_catalog


def _entry(name):
    return next((m for m in spec_catalog()["modalities"] if m["name"] == name), None)


def test_catalog_lists_biosample_with_specimen_types():
    biosample = _entry("biosample")
    specimen = next(x for x in biosample["lists"] if x["field"] == "Technical.SpecimenType")
    assert specimen["label"] == "Specimen type" and "saliva" in specimen["values"]
    assert biosample["label"] == "Biosample"
    assert biosample["metrics"] and all(m["id"].startswith("prism:") for m in biosample["metrics"])


def test_catalog_has_no_modality_without_lists():
    assert _entry("events") is None


def test_catalog_metrics_none_without_registry():
    assert _entry("survey")["metrics"] is None


def test_catalog_units_sorted_and_unique():
    units = spec_catalog()["units"]
    assert "nmol/L" in units and units == sorted(set(units))


def test_catalog_specimens_match_the_biosample_list():
    specimen = next(x for x in _entry("biosample")["lists"] if x["field"] == "Technical.SpecimenType")
    assert spec_catalog()["specimens"] == specimen["values"]
