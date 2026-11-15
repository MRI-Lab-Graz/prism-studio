# Instrument templates (library/)

This folder is for instrument templates (questionnaires and similar). Each template stays under
ITS OWN terms, which are stated in the template and are set by the rights holder of the instrument.

* PRISM grants no rights to any instrument. Having a template here does not give you a licence to
  the instrument; read the terms in the template.
* The demonstration questionnaire `survey-demo.json` is the exception: it is written by the PRISM
  maintainers and released under CC0 1.0. It measures nothing and is not a real instrument.
* Nothing ships here unless its redistribution is verified: either a statement by the rights holder
  (kept with its source URL, the retrieval date and a saved copy) or an open licence.
* A template carries only the languages its licence evidence covers: `Study.LicenseLanguages` names them,
  and a translation the rights holder did not license is not shipped. Adding a language means editing that
  list in a reviewed change, with evidence for that language.
* Descriptive metadata (description, notes, reliability, validity, norming, keywords, licence terms, archive
  metadata) is always English, whatever the language of the instrument. Only the instrument's own text (items,
  response levels, instructions, original name), bibliographic data and the quoted licence statement stay in the
  original language.
* If you hold rights to an instrument and want it removed, write to
  <contact address to be set by the maintainers>.
* This folder is excluded from the CC BY 4.0 grant of this repository (see LICENSE). The rest of
  the repository (schemas, terms, specs, recipes, ids, mappings) is CC BY 4.0.

## Open Test Archive

Tests from the Open Test Archive (ZPID, <https://www.testarchiv.eu>) may ship here when the test's own
licence box names CC BY, CC BY-SA or CC0. Evidence: the archive's terms of use state that the tests "wurden
uns durch die Rechteinhaber/-innen zur weiteren Nachnutzung zur Verfügung gestellt"
(<https://www.testarchiv.eu/de/nutzungsbedingungen>), plus the test's page and its DOI, kept in
`Study.License`, `Study.Source` and `Study.LicenseChecked`. Tests under NC or ND licences are held for a
decision. The licence of each test is always read from that test's page, never assumed.

* `survey-sbi-d.json`: German Savoring Beliefs Inventory (SBI-d), CC BY-SA 4.0, the first one. Open point:
  the form (PDF) says 1 = stimme gar nicht zu, 7 = stimme voll zu, while the Testarchiv page text reads
  (1) stimme voll und ganz zu ... (7) stimme überhaupt nicht zu; the template gives only the two anchors of
  the form (`Study.Notes`), no scoring and no recipe until the scoring documentation has been read.
