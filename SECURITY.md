# Security Policy

## Supported Versions

This repository is a template / experimentation base. The `main` branch is the only version actively maintained. Example branches (`example/*`) are provided as-is for reference.

| Branch | Supported |
| --- | --- |
| `main` | :white_check_mark: |
| `example/*` | :x: (reference only) |

## Reporting a Vulnerability

If you discover a security vulnerability in this repository, **please do not open a public issue**.

Instead, report it privately by emailing the maintainer or using [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability):

1. Go to the **Security** tab of this repository.
2. Click **"Report a vulnerability"**.
3. Fill in the details (description, impact, steps to reproduce, and any suggested fix).

You can expect an acknowledgement within **5 business days**. We will work with you to assess the issue and, if confirmed, publish a fix and credit you in the release notes (unless you prefer to remain anonymous).

## Scope

Issues in scope include:

- Vulnerabilities in the backend (`assistant-service`) that could expose or exfiltrate data
- Vulnerabilities in the frontend that could compromise a user's session or browser
- Dependency vulnerabilities with practical exploitability in this context

Out of scope:

- Theoretical or highly unlikely attack vectors with no practical impact
- Issues already covered by an open GitHub Advisory or known CVE in a dependency
