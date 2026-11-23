# Ontology-ready

PRISM data can be used with ontologies and other external vocabularies. PRISM does not do the linking for you and
does not change your data to do it: it gives every measurement a stable ID, and keeps links from those IDs to
vocabularies such as SNOMED CT, LOINC or ChEBI in a separate, checked layer.

**What PRISM claims, and nothing beyond it:**

> PRISM IDs are stable and resolvable; links from IDs to external vocabularies live in a separate, checked
> `mappings/` layer; PRISM never changes data to carry meaning.

## An ID is an address

Every term of the term registries and every instrument, item and score of the shipped survey library has a PRISM ID
such as `prism:cortisol` or `prism:dass21.dass2101`. In your sidecars the ID is the only thing that names a measurement (`Term`); a data file never says what a value
*means* in an outside vocabulary.

An ID becomes a web address by a fixed rule:

| ID | Address |
|---|---|
| `prism:cortisol` (biosample) | `https://w3id.org/prism-specification/terms/biosample/cortisol` |
| `prism:air-temperature` (environment) | `https://w3id.org/prism-specification/terms/environment/air-temperature` |
| `prism:dass21` or `prism:dass21.dass2101` (survey) | `https://w3id.org/prism-specification/terms/survey/dass21`, `.../terms/survey/dass21.dass2101` |

The address redirects to the file that defines the ID in the
[prism-specification](https://github.com/MRI-Lab-Graz/prism-specification) repository: the term file for biosample
and environment terms, the instrument's template for a survey ID (an item or a score lands on its instrument).

**What resolves today:** all biosample and environment terms, and every instrument of the shipped survey library
(23 templates at this release) with its items and scores. A survey ID that is released but has no template in the
library yet (most released instruments are still waiting for theirs) does not resolve until the template is
added. A project's own `local:` IDs are
yours alone and have no address.

## Links live in `mappings/`

A link is not part of the term and not part of your data. It is one entry in a mapping file,
`mappings/<modality>/<family>.json`, which can be added, corrected or removed without changing a schema version or
a single data file. This is the shipped file for follicle-stimulating hormone:

```json
{
  "prism:fsh": {
    "SameAs": {"snomed": "https://snomed.info/id/25217009"}
  }
}
```

`SameAs` says the ID is the same thing as that entry in another vocabulary. An item or score can instead carry
`Measures` (what it measures, with how close the match is, who made the link and when) and `ValueRules` (named
ways of reading a value as a state). The format, with every field, is in the
[mappings specification](specs/mappings.md). The same layout works for every kind of data and every vocabulary; PRISM
keeps no list of symptoms or constructs of its own.

PRISM knows 29 vocabularies at this release (SNOMED CT, LOINC, ChEBI, ICD-11, Wikidata, the Human Phenotype Ontology and others); the list, with the shape
of each vocabulary's addresses, is `official/library/mappings/vocabularies.json` and is data, so a vocabulary can be
added without new code. The shipped links are a start, not a complete mapping: ten biosample terms (sex hormones, prolactin, SHBG, CRP,
IL-6), the two DASS instruments (every item linked to the SNOMED CT score of its subscale) and the demonstration
questionnaire. Most terms, including `prism:cortisol`, have an address but no link yet, and no environment term has
one.

## See the links of an ID

```bash
python prism_tools.py terms show prism:fsh
python prism_tools.py terms show prism:dass21.dass2101 --modality survey
```

The first prints the SNOMED CT link of FSH, the second the SNOMED CT score the first DASS-21 item contributes to,
each with where it comes from. `--json` gives the same as data.

## Add links of your own

Links you need for your study stay in your project, in `code/specification/mappings/<modality>/<family>.json` (the
same layout as above, with your own terms written `local:<id>`):

```bash
python prism_tools.py spec local add-term --project <project> --data <file.tsv> --column <column> \
    --link loinc=https://loinc.org/2191-5
python prism_tools.py terms check-links --project <project>
```

`--link VOCABULARY=URL` can be repeated and takes any vocabulary of the list, for any kind of data. `terms
check-links` checks your files with the specification's own checker: an unknown vocabulary, an address that does not
fit its vocabulary, an ID that does not exist, a file named for the wrong family. It only reads. You can also point
it at a folder of mapping files with `--dir <folder>`.

## Share links with everyone

A link that others should have goes to the specification as a proposal. The proposal carries the mapping file next
to the term:

```bash
python prism_tools.py terms propose --sidecar <sidecar.json> --column <column> --link snomed=<address>
python prism_tools.py spec propose-metric --name <name> --description <text> --units <units> --specimen <sample type> \
    --link loinc=<address>
```

Nothing is sent unless you add `--open`, which opens a prefilled form in your browser. The *Specifications →
Propose changes* page in PRISM Studio does the same, with a field for links. The maintainers check each link
against its vocabulary before it ships.

## What PRISM does not do

* It does not tag your data, your participants or your symptoms with ontology terms.
* It does not map automatically: a link is made by a person who looked the entry up, and the checker only verifies
  the *shape* of an address, not that the entry exists.
* It is not an ontology editor and ships no ontology of its own.
* It does not map every instrument. Most survey IDs have no mapping yet, and some have no template either.
* It does not change a data file to carry a link or a meaning.

Details of the file format: [Mappings](specs/mappings.md).
