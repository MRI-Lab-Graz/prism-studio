"""convert_participant_data reads a LimeSurvey .lsa archive, not as CSV."""

import zipfile

from src.participants_converter import ParticipantsConverter

LSR = """<?xml version="1.0" encoding="UTF-8"?>
<document><LimeSurveyDocType>Responses</LimeSurveyDocType><DBVersion>636</DBVersion>
<languages><language>de</language></languages><responses>
<fields><fieldname>id</fieldname><fieldname>age</fieldname></fields>
<rows><row><id><![CDATA[1]]></id><age><![CDATA[30]]></age></row>
<row><id><![CDATA[2]]></id><age><![CDATA[40]]></age></row></rows>
</responses></document>"""

MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {
            "source_column": "id",
            "standard_variable": "participant_id",
            "type": "string",
        },
        "age": {"source_column": "age", "standard_variable": "age", "type": "string"},
    },
}


def test_lsa_source_is_converted(tmp_path):
    src = tmp_path / "survey_archive_1.lsa"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("survey_1_responses.lsr", LSR)

    success, df, messages = ParticipantsConverter(tmp_path).convert_participant_data(
        src, MAPPING, output_file=tmp_path / "participants.tsv"
    )

    assert success, messages
    assert sorted(df["participant_id"]) == ["sub-1", "sub-2"]
