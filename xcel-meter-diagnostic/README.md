# Xcel Meter HA

Local-first Home Assistant app for Xcel Energy / Itron IEEE 2030.5 smart-meter readings.

For a new install, follow [`../docs/GETTING_STARTED.md`](../docs/GETTING_STARTED.md).

If you already use the older Xcel iTron MQTT add-on, read [`DOCS.md`](DOCS.md#existing-user-migration) before removing it so the provisioned Launchpad identity is migrated safely.

0.4.5b2 includes native durable identity generation, safe legacy identity migration, SDK-aligned ReadingType discovery/paging, source freshness protection, secure Xcel SDK simulator validation, and MQTT/meter failure isolation.
