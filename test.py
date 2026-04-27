from flask import Flask
from app.src.web.blueprints.tools_helpers import _load_prism_schema, _validate_against_schema
from app.src.web.blueprints.tools_template_editor_blueprint import _normalize_template_for_validation
import json
with open('/Volumes/Thunder/129_PK01/rawdata/code/library/survey/survey-pss.json') as f: tpl=json.load(f)
app = Flask(__name__)
app.root_path = 'app'
with app.app_context():
    s = _load_prism_schema(modality='survey', schema_version='stable')
    errs = _validate_against_schema(instance=_normalize_template_for_validation(modality='survey', template=tpl), schema=s)
    print(errs)
