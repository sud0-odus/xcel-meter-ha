# Xcel Meter HA

Local-first Home Assistant app for Xcel Energy / Itron IEEE 2030.5 smart-meter readings.

For a new install, follow [`../docs/GETTING_STARTED.md`](../docs/GETTING_STARTED.md).

If you already use the older Xcel iTron MQTT add-on, read [`DOCS.md`](DOCS.md#existing-user-migration) before removing it so the provisioned Launchpad identity is migrated safely.

0.4.5 is the stable native-onboarding release. It includes durable identity generation and migration, SDK-aligned meter discovery, freshness protection, MQTT/meter failure isolation, and the validated Home Assistant migration path.
