# Xcel Meter HA

Local-first Home Assistant app for Xcel Energy / Itron IEEE 2030.5 smart-meter readings.

For a new install, follow [`../docs/GETTING_STARTED.md`](../docs/GETTING_STARTED.md).

If you already use the older Xcel iTron MQTT add-on, read [`DOCS.md`](DOCS.md#existing-user-migration) before removing it so the provisioned Launchpad identity is migrated safely.

0.4.5b3 is the release-hardening candidate for native onboarding. It keeps the 0.4.5b2 protocol behavior, adds stronger identity-history regression coverage, expands the secure simulator harness, and adds documentation validation to CI.
