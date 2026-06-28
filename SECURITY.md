# Security policy

## Supported versions

This kit is a small, focused capability demo, not a long-lived library.
Security fixes are made against `main` and the latest tagged release.

| Version | Supported |
|---------|-----------|
| `main` + latest tag | Yes |
| Older tags | No (cut a fresh release if you depend on it) |

## Reporting a vulnerability

**Please don't open a public issue for anything sensitive.**

Email `derekgallardo01@gmail.com` with:

- A clear description of the vulnerability.
- Repro steps and the commit / tag affected.
- Any suggested mitigation.

You can expect:

- An acknowledgement within **48 hours**.
- A fix or a clear "won't fix, here's why" within **14 days** for confirmed
  issues affecting the latest tag.
- Credit in the release notes when the fix ships, unless you'd prefer to
  stay anonymous.

## Scope

These kits are demos of patterns; they don't ship as deployed services.
The most relevant security concerns therefore tend to be:

- **Secrets handling**: any example pointing at a real connector / API
  must not embed credentials. All examples use environment variables or
  references; PRs that embed secrets will be rejected.
- **PII / client data**: examples ship with synthetic data only. A repo
  containing real client data is a vulnerability — report it as one.
- **Output XSS / injection**: the renderers in
  [sharepoint-intranet-generator](https://github.com/derekgallardo01/sharepoint-intranet-generator)
  and the GitHub Pages workflows escape user-controllable input via
  `html.escape`. Bypasses (definitions or data that produce raw HTML in
  output) are in scope.

## Not in scope

- Vulnerabilities in dependencies — these kits are stdlib-only by design.
  If a workflow's pinned action version (e.g. `actions/checkout@v4`) is
  vulnerable, Dependabot raises the PR.
- "Best practice" suggestions without a demonstrable security impact.
