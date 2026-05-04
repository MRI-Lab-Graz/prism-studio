from app.src.web.neurobagel import augment_neurobagel_data


def test_group_and_diagnosis_without_source_levels_are_empty() -> None:
    raw = {
        "properties": {
            "group": {"data_type": "categorical"},
            "diagnosis": {"data_type": "categorical"},
        }
    }

    augmented = augment_neurobagel_data(raw)
    assert augmented["properties"]["group"]["levels"] == {}
    assert augmented["properties"]["diagnosis"]["levels"] == {}


def test_group_source_levels_keep_source_keys_and_known_uris() -> None:
    raw = {
        "properties": {
            "group": {
                "data_type": "categorical",
                "Levels": {
                    "CTRL": "Healthy Control",
                    "AD": "Alzheimer's Disease",
                    "CUSTOM": "Site-specific class",
                },
            }
        }
    }

    augmented = augment_neurobagel_data(raw)
    levels = augmented["properties"]["group"]["levels"]

    assert set(levels.keys()) == {"CTRL", "AD", "CUSTOM"}
    assert levels["CTRL"]["uri"] == "ncit:C94342"
    assert levels["AD"]["uri"] == "snomed:26929004"
    assert levels["CUSTOM"]["uri"] is None
    assert levels["CUSTOM"]["label"] == "Site-specific class"


def test_sex_still_uses_default_levels_without_source_levels() -> None:
    raw = {"properties": {"sex": {"data_type": "categorical"}}}

    augmented = augment_neurobagel_data(raw)
    levels = augmented["properties"]["sex"]["levels"]

    assert {"M", "F", "O"}.issubset(set(levels.keys()))
