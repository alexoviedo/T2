# Launch Blockers

These items should be resolved before presenting USB2BLE as a fully open-source
public release.

## 1. Root License Decision

Status: unresolved.

There is no root `LICENSE` file. A public repository without an explicit license
does not grant clear open-source reuse rights. Alex should choose a license
before launch.

Common choices:

| License | Practical effect |
| --- | --- |
| MIT | Short permissive license; easy for hobbyists and companies to reuse with attribution. |
| Apache-2.0 | Permissive like MIT, with explicit patent grant and more formal terms. |
| GPL-3.0 | Copyleft license; derivative distributions generally need to remain GPL-compatible. |

Recommendation: Alex should explicitly choose MIT or Apache-2.0 if the goal is
maximum adoption by makers, embedded developers, and downstream integrators. If
strong copyleft is desired, choose GPL-3.0 intentionally.

Do not infer a project license from `web/package.json`; that package metadata is
not a root repository license.

## 2. Public URLs

Status: unresolved.

Before launch, confirm:

- public GitHub repository URL,
- GitHub Pages URL,
- where users should file issues,
- whether GitHub Discussions is enabled.

Docs currently avoid hard-coded public URLs until those destinations are final.

## 3. Final CI Pass

Status: pending public branch.

Run one final clean CI pass on the branch/tag that will be announced publicly.
