---
applyTo: '**'
---
# Repository Instructions
prism is a add-on to bids - it does not replace bids
bids-standards should not be changed
we add schmeas (like survey) that are not in bids

it's imporatnt that bids apps still work on prism datasets

Always activate .venv in your terminal before running any scripts.
missing packages should be installed via the setup script NOT manually
prism.py is the main script
Webinterface is BASED on prism.py - not a separate tool!

# making changes to prism
- backend code is in src, frontend code in under app/src !!
- frontend code is always executing backend code - so if you are making changes to the frontend, make sure to check if there are any changes needed in the backend as well
- make sure to run the tests after making changes
- if you are adding a new feature, please add tests for it
- make a roadmap and mark solved issues, add "lessions-learned"

