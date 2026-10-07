# Security Policy

## Supported Versions

Security fixes are applied to the latest released version of PRISM. Before
reporting an issue, update to the newest release and confirm that the problem
still occurs.

## Reporting a Vulnerability

Do not report suspected vulnerabilities in public issues or discussions. Email
[Karl Koschutnig](mailto:karl.koschutnig@uni-graz.at) with a description of
the issue, affected PRISM version, reproducible steps, and its potential
impact. The maintainer will acknowledge the report and coordinate disclosure
and remediation with the reporter.

## BIDS check

The BIDS check starts the bundled Deno through the `bids-validator-deno` launcher with exactly `--allow-read --allow-env --allow-net --allow-write --allow-run=git` (plus `--allow-sys=osRelease` on Windows); network access is allowed, no other program may be started.
