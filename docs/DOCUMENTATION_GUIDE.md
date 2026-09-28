# Documentation Maintenance Guide

Documentation is part of the release, not an afterthought. This project is intended to be understandable by a first-time Home Assistant user, a protocol-oriented developer, and a utility/vendor reviewer without forcing any of them to reverse-engineer the code first.

## Reader paths

Keep these paths working:

1. **New user:** README -> Getting Started -> Xcel enrollment -> healthy Home Assistant device.
2. **Existing user:** README -> migration instructions -> restart verification -> old add-on removal.
3. **Troubleshooter:** error/log message -> Troubleshooting -> safe next action without identity loss.
4. **Developer/reviewer:** Architecture -> SDK alignment -> Compatibility -> Validation -> simulator procedure.
5. **Support reporter:** Troubleshooting -> Support checklist -> structured GitHub issue.
6. **Rate contributor:** TOU design -> rate-profile catalog -> rate-profile issue/pull request.

## Documentation gate for every meaningful change

Before merging a user-visible or protocol-visible change, ask:

- Does the README still describe the actual current behavior?
- Does `xcel-meter-diagnostic/DOCS.md` match the options shown in `config.yaml`?
- Does a changed onboarding/error behavior require a Troubleshooting update?
- Does a new protocol assumption belong in `SDK_ALIGNMENT_0.4.5.md` or `COMPATIBILITY.md`?
- Was new evidence recorded in `VALIDATION_0.4.5.md` and labeled by evidence type?
- Did we add/close an upstream concern that belongs in `upstream-issue-review.md`?
- Do Mermaid diagrams still represent the implementation rather than the intended future state?
- Do support instructions still request the evidence needed without asking for secrets?
- Did a rate-plan example change? Run `python tools/check_rate_profiles.py` and verify its source/effective date.

## Evidence labels

Use explicit wording:

- **Production validated** - observed on a real provisioned Xcel/Itron meter.
- **SDK simulator validated** - observed against Xcel's secure local simulator.
- **Automated tested** - covered by repository unit/integration tests.
- **Community reported** - reported in another project or forum, not independently reproduced here.
- **Planned / open question** - design intent or unresolved vendor behavior.

Do not present simulator behavior as proof of production provisioning timing, Wi-Fi behavior, or every firmware layout.

## Screenshot policy

Screenshots should be current, useful, and safe to publish.

- Capture our own Xcel/Home Assistant screenshots where possible.
- Redact account names, addresses, meter/account numbers, Wi-Fi SSIDs/passwords, IPs when unnecessary, LFDIs when unnecessary, trace IDs, and other unique account data.
- Do not show private-key content under any circumstances.
- Prefer a tightly cropped screenshot focused on the control being described.
- Add alt text that explains what the reader should notice.
- Record the capture date in `docs/images/README.md` because Xcel/Home Assistant UI text changes.
- Do not copy screenshots from another repository unless its license clearly permits reuse and attribution is preserved.

## Mermaid policy

Use diagrams when they explain relationships better than prose, especially for:

- onboarding/identity lifecycle;
- local data flow;
- failure-domain separation;
- import/export/solar semantics;
- discovery/paging/classification;
- migration state.

A diagram should show the **current implemented flow**. Future work belongs in a clearly labeled future-state diagram.

## Link and wording maintenance

CI runs `python tools/check_docs.py` to catch missing local Markdown targets/anchors and unclosed fenced code blocks. Run the same command locally after documentation changes.

- Prefer stable project-relative links for repository documentation.
- Link to the Xcel portal from one canonical Getting Started section rather than duplicating fragile instructions everywhere.
- State that Xcel portal labels can change.
- When quoting community timing such as "about a week," label it as community experience rather than an Xcel service-level promise.
- Keep Home Assistant wording tolerant of UI naming changes such as Apps/Add-ons.

## Release checklist

For a release candidate:

```text
[ ] README status/version is current
[ ] config.yaml options and DOCS.md agree
[ ] Getting Started path works for a fresh identity
[ ] Existing-user migration path is still safe
[ ] Troubleshooting never recommends identity deletion as a generic fix
[ ] Compatibility/validation evidence is current
[ ] Upstream issue review date/statuses are current
[ ] `python tools/check_docs.py` passes
[ ] `python tools/check_rate_profiles.py` passes
[ ] Mermaid blocks render on GitHub
[ ] Screenshot redaction reviewed
[ ] No private keys, credentials, production IPs, or account identifiers were added
```
