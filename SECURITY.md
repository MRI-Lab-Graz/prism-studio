# Security Policy

PRISM Studio is open-source research software. We aim for practical, responsible security for a local-first tool used by the scientific community.

## Supported Versions

Security fixes are applied to the `main` branch.

## Reporting a Vulnerability

Please do **not** open a public issue for security vulnerabilities.

- Use GitHub Security Advisories (preferred) or contact the maintainers directly.
- Include reproduction steps, impact, and affected files/paths if possible.
- We will acknowledge receipt and coordinate a fix and disclosure.

## Security Baseline

We prioritize:

- Safe handling of file paths and uploaded files
- No secrets in repository history
- Dependency updates and vulnerability checks in CI
- No execution of raw user input as shell commands
- Error handling that avoids leaking sensitive details

## Scope Notes

- PRISM Studio is primarily a local desktop/web workflow and is not designed as a hardened multi-tenant internet service.
- If you deploy it in a networked or production-like environment, add environment-specific hardening (reverse proxy, access control, TLS, monitoring, etc.).
