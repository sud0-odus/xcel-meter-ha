# Documentation Screenshot Inventory

These images support the written onboarding and Home Assistant instructions. They were captured or prepared from current interfaces on **2026-09-28** and should be refreshed when the Xcel or Home Assistant UI changes materially.

Screenshots are supporting visuals, not the sole source of instructions. The surrounding documentation should remain usable if a portal label or layout changes.

| File | Shows | Used in |
|---|---|---|
| `xcel-launchpad-enrolled.png` | Xcel Energy Launchpad enrolled card and **Manage** action | `GETTING_STARTED.md` |
| `xcel-launchpad-connect-wifi.png` | Meter Wi-Fi setup and 2.4 GHz requirement | `GETTING_STARTED.md` |
| `xcel-launchpad-add-device-button.png` | **My Devices** area and **Add a Device** action | `GETTING_STARTED.md` |
| `xcel-launchpad-add-device-form.png` | Add Device form with LFDI, nickname, manufacturer, and device type fields | `GETTING_STARTED.md` |
| `ha-add-repository.png` | Home Assistant repository-add dialog | `GETTING_STARTED.md` |
| `ha-addon-overview.png` | Xcel Meter HA add-on overview and controls | `GETTING_STARTED.md` |
| `ha-addon-options.png` | Xcel Meter HA configuration options | `GETTING_STARTED.md` |
| `ha-smart-meter-device.png` | Home Assistant device sensors and diagnostics | `README.md`, `GETTING_STARTED.md` |
| `ha-energy-dashboard.png` | Home Assistant Energy dashboard using cumulative meter energy | `README.md`, `GETTING_STARTED.md` |

## Publication checklist

Before replacing or adding an image:

- crop tightly around the control or result being explained;
- remove or redact account numbers, addresses, meter numbers, SSIDs/passwords, production IP addresses, and production LFDIs unless they are synthetic;
- never include private-key contents;
- prefer synthetic example values when a value itself is not the point of the screenshot;
- keep text readable on a typical GitHub page without requiring extreme zoom;
- update this inventory and the capture date when the visual materially changes.

The project intentionally uses its own current screenshots rather than copying UI images from older community repositories.
