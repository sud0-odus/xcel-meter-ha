# Documentation Screenshot Plan

The documentation intentionally uses Mermaid diagrams and the My Home Assistant install badge immediately, while Xcel/Home Assistant UI screenshots should be captured from current interfaces rather than copied from older community projects.

Recommended screenshots:

| File | Capture | Redact/check |
|---|---|---|
| `xcel-launchpad-enroll.png` | Xcel Meters and Devices / Launchpad enrollment entry point | account name, address, account/meter numbers |
| `xcel-launchpad-manage.png` | Enrolled meter with Manage action | installation identifiers |
| `xcel-launchpad-wifi.png` | Wi-Fi Edit/configuration area | SSID/password, account data |
| `xcel-launchpad-add-device.png` | Add a Device form with LFDI field visible | use a fake/redacted LFDI and redact account data |
| `ha-add-repository.png` | Home Assistant repository-add dialog | instance URL if identifying |
| `ha-app-options.png` | Xcel Meter HA configuration screen | meter IP/LFDI if not needed |
| `ha-device.png` | Xcel Meter HA MQTT device/entities | unique installation IDs |
| `ha-energy-dashboard.png` | Energy dashboard using delivered/export readings | household-identifying data as desired |

When a screenshot is added, include capture date and Home Assistant/Xcel UI context below. Portal wording can change, so screenshots are supporting visuals rather than the only source of instructions.
