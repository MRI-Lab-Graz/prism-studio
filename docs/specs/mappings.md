# Mappings

PRISM data carries IDs and nothing else about meaning. What an ID is the same as, what it measures, which way
a value points and how a value is read as a state is written in a separate layer, `mappings/`. A mapping can be
added, corrected or removed without a new schema version, because it never touches the data or the ID.

PRISM keeps no list of symptoms or constructs of its own: a link points to an entry in an existing external
vocabulary. The URLs in the example below are placeholders (`example.org`), not real codes; the files under "Shipped mappings" use real ones.

## A mapping file

One file per ID family: `mappings/<modality>/<family>.json`. The file name is the local part of the family's ID:
`mappings/survey/phq9.json` holds the instrument, its items and its scores; `mappings/biosample/cortisol.json`
holds `prism:cortisol` and its specimen children. Keys are full IDs of that family.

```json
{
  "prism:example": {
    "SameAs": {"snomed": "https://example.org/placeholder"}
  },
  "prism:task.item01": {
    "Measures": [
      {"URL": "https://example.org/placeholder", "Match": "exact", "Higher": "more",
       "Source": "who made the link", "Checked": "2026-01-01", "Status": "reviewed"}
    ],
    "ValueRules": [
      {"Name": "task-present", "Source": "the manual",
       "Rules": [{"When": {"Op": ">=", "Value": 2}, "State": "present"},
                 {"When": {"Op": "<",  "Value": 2}, "State": "absent"}]}
    ],
    "Levels": {
      "3": {"Measures": [{"URL": "https://example.org/placeholder", "Match": "narrower"}]}
    }
  }
}
```

## The four fields

| Field | Meaning |
|---|---|
| `SameAs` | The ID is the same thing as that entry in another vocabulary: `{vocabulary: URL}`, one URL per vocabulary. |
| `Measures` | The item, score or variable measures that concept: a list of `{URL, Match, Higher, Source, Checked, Status}`. Only `URL` is required. `Match` is `exact`, `broader`, `narrower` or `related`; `Higher` is `more` or `less` (a higher value means more or less of the concept); `Checked` is a date `YYYY-MM-DD`; `Status` is `reviewed` or `unreviewed`. |
| `ValueRules` | Named rules that read a value as a state: a list of `{Name, Source, Rules}`; each rule is `{When: {Op, Value}, State}`. `Op` is one of `==`, `!=`, `>=`, `>`, `<=`, `<`, `in` (`in` takes a list). `Name` and `State` are slugs. Several rules may exist and disagree; none is the truth, a consumer picks one by name. |
| `Levels` | `SameAs`, `Measures` and `ValueRules` for one answer value or category, keyed by the level code of the term's or template's `Levels`. A study's data may use other codes; a link applies only to the code it is written for. |

A mapping file holds no free text except `Source` (and the slug `Name`). It never quotes item wording.

## The rules

`python scripts/check_mappings.py` checks that:

* every key is a released ID of the file's modality: a term of `terms/<modality>/` (or a child of an existing
  analyte), or for survey an ID in `ids/survey-ids.txt`; the IDs derived from `library/` and `recipes/` must all
  be in that list too;
* the family of the key is the file name;
* every `SameAs` name is a vocabulary in `mappings/vocabularies.json`, and every URL matches the pattern of its
  vocabulary (a `Measures` URL must match one of them). The patterns are data, not code; the patterns check the
  shape of a URL, not that the entry exists, so the author looks every link up;
* every `Levels` code exists in the definition of the ID (the term's or the template's `Levels`); an ID without
  `Levels` takes none;
* the types are right (a wrong type is a message, not a crash), and no ID is in two files;
* `ids/survey-deprecated.json` is valid (`ids/README.md`). A link on a deprecated ID is a warning, not a failure: link
  the replacement.

A specimen child (`prism:cortisol.serum`) inherits the links of its analyte; no check is needed for that.

## Vocabularies

A `SameAs` name, and the URL of a `Measures` link, must come from `mappings/vocabularies.json`. These are known:

| Name | Vocabulary |
|---|---|
| `snomed` | SNOMED CT |
| `loinc` | LOINC |
| `chebi` | ChEBI |
| `ncit` | NCI Thesaurus |
| `hpo` | Human Phenotype Ontology |
| `mondo` | Mondo Disease Ontology |
| `doid` | Human Disease Ontology |
| `mfoem` | Emotion Ontology |
| `mfomd` | Mental Disease Ontology |
| `uberon` | Uberon anatomy ontology |
| `pato` | Phenotype And Trait Ontology |
| `cmo` | Clinical Measurement Ontology |
| `oba` | Ontology of Biological Attributes |
| `efo` | Experimental Factor Ontology |
| `icd11` | ICD-11 (WHO foundation entity or MMS) |
| `icd10` | ICD-10 (WHO) |
| `mesh` | MeSH |
| `umls` | UMLS Metathesaurus |
| `wikidata` | Wikidata |
| `cogatlas` | Cognitive Atlas |
| `cde` | NIH Common Data Elements Repository |
| `pubchem` | PubChem compound |
| `uniprot` | UniProt |
| `atc` | ATC (WHO drug classification) |
| `orphanet` | Orphanet |
| `omim` | OMIM |
| `hmdb` | Human Metabolome Database |
| `drugbank` | DrugBank |
| `rxnorm` | RxNorm |
| `neurobagel` | Neurobagel |

The list is data: a new vocabulary is one entry (name, label, URL pattern) with a real example URL in
`tests/test_vocabularies.py`, which checks that the example matches its own pattern and no other. A pattern checks the
shape of a URL, never that the entry exists; the author looks every link up. When a vocabulary was added, the shape was
confirmed by opening a real entry, except for `drugbank`, `hmdb`, `icd11`, `loinc`, `omim`, `rxnorm`: those services refuse automated
look-ups, so their shape is the one in their own documentation and a link there needs a manual look-up.

The `neurobagel`
names are those in Neurobagel's own configuration (`neurobagel/communities`); its URLs are identifiers, not pages.

## Who reviews links

An author adds a link as `unreviewed`, looks the URL up in the vocabulary and writes `Source` and `Checked`. A
maintainer who has checked it sets `Status` to `reviewed`. Content arrives by pull request, like terms.

## Shipped mappings

* **DASS and DASS-21** (`mappings/survey/dass.json`, `dass21.json`): every item is linked to the SNOMED CT score of
  the subscale it counts towards (depression, anxiety or stress), as `Measures` with `Match` `related`, `Higher`
  `more`. The assignment is the one on the DASS authors' own scoring template; the three codes were looked up on a
  SNOMED CT terminology server (edition 2026-07-01). Links are `unreviewed` until a maintainer has checked them.
  The templates define no subscale scores, so there are no links for scores.
* **Demo** (`mappings/survey/demo.json`): one `ValueRules` entry on the demo total score. It is invented, to show the
  format, and is not a research rule.
