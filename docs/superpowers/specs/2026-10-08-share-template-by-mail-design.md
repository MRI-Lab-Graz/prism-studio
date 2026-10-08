# Share a new template with the PRISM team by mail

## Intent
A student imports a survey that has no match in the library, makes it valid and saves it.
They have no git and no GitHub account and want none. Studio offers to send the template
to the PRISM team (mri-lab@uni-graz.at), who check it (including copyright) and add it to
the library by hand.

## Flow
1. Import -> fill the missing fields (Citation, Category) -> Validate -> Save to Project.
2. If the import had no library match and the save succeeded, an in-page message asks once:
   "Share this template with the PRISM team (mri-lab@uni-graz.at)? It will be checked,
   including its copyright status, before it is added to the library."
   with two buttons. (Not a native confirm: its buttons cannot be relabelled, and browsers
   block a mail program that is opened outside the user's own click.)
3. "Yes, share by mail" is a real `mailto:` link (To, Subject with the template name, Body with
   title, citation, source and a request to attach the file); its click also downloads the
   template JSON. "No thanks" clears the message; not asked again for that template.

The share file is the template JSON itself. A maintainer opens it with the existing
"Import Template Source", reviews it and saves it to the library. No new format.

## Backend (one implementation)
- `src/template_share.py`: `SHARE_ADDRESS` constant and `share_mail(template, filename)`
  returning `{to, subject, body}`.
- CLI: `prism_tools.py library share-template --input X.json` prints to/subject/body and
  the mailto link.
- Flask: one thin route calling `share_mail`; JavaScript only downloads the JSON and
  opens the mailto link.

## Out of scope
SMTP or any server, copyright check at send time, author fields (the mail carries the
sender), automatic library import.

## Tests
- Unit: `share_mail` (address, subject, body content, URL-safe mailto), CLI output.
- E2E: prompt appears only for an unmatched template after a successful save; No does
  nothing and does not re-ask; Yes downloads the JSON and opens the mailto link.
