# Xcel Meter HA 0.4.5b3

Xcel Meter HA reads a Launchpad-enabled Xcel/Itron meter locally over IEEE 2030.5 and publishes validated readings as one Home Assistant MQTT device.

For a new installation, start with the repository's [`docs/GETTING_STARTED.md`](../docs/GETTING_STARTED.md).

## Existing-user migration

If your Launchpad LFDI is already provisioned through the older Xcel iTron MQTT add-on, preserve that identity. Do not create a new certificate just to migrate applications.

For the first migration test, keep the legacy add-on installed but stopped.

With these defaults, `identity_source: auto` first looks for Xcel Meter HA's own identity. If none exists, it can find the legacy pair, validate it, copy it into app-owned `/config/certs`, and verify that the certificate-derived LFDI did not change.

```yaml
meter_ip: 192.168.1.50
meter_port: 8081
expected_lfdi: YOUR_EXISTING_LAUNCHPAD_LFDI
identity_source: auto
migrate_legacy_identity: true
generate_identity_if_missing: true
legacy_addon_slug: ""
timeout: 8
poll_interval: 60
log_level: INFO
mqtt_enabled: true
energy_export_enabled: false
```

If more than one possible legacy add-on exists, set `legacy_addon_slug` explicitly.

Before removing the legacy add-on, confirm all of the following:

```text
[ ] migrated app-owned identity reports the expected LFDI
[ ] LFDI validation is MATCH when expected_lfdi is configured
[ ] TLS/IEEE 2030.5 connection is PASS
[ ] live core readings are returned
[ ] restart Xcel Meter HA
[ ] restart reports Identity source: own
[ ] second live meter poll succeeds
[ ] MQTT device/state is healthy if MQTT is enabled
```

Only after that should the legacy add-on be removed. This migration sequence has been validated against a production meter.

## New installation

If no app-owned or legacy identity exists and `generate_identity_if_missing` is enabled, the app creates one durable P-256 IEEE 2030.5 client identity in `/config/certs`.

`meter_ip` may be left unset during the first identity step. The log prints the generated LFDI so it can be entered into Xcel Energy Launchpad.

Follow the complete Launchpad/Wi-Fi walkthrough in:

[`../docs/GETTING_STARTED.md`](../docs/GETTING_STARTED.md#2-enroll-the-meter-in-xcel-energy-launchpad)

Once a new generated identity exists, **keep it while provisioning completes**. The app does not regenerate identity because the meter is not yet authorized.

For a never-authenticated generated identity, an explicit TLS client-auth rejection or HTTP `401`/`403` may be classified as onboarding/provisioning pending. Once that same identity has successfully authenticated, a later `401`/`403` is a real authorization error.

## Identity files

App-owned files:

- `/config/certs/cert.pem`
- `/config/certs/key.pem`
- `/config/certs/identity.json` - non-secret identity/provisioning status

The private key is never emitted in normal logs or written to `identity.json`.

## Identity options

- `identity_source: auto` - prefer app-owned identity; otherwise migrate/use legacy; otherwise generate if enabled.
- `identity_source: own` - use app-owned identity or generate it when generation is enabled.
- `identity_source: legacy` - read the legacy identity directly without migration; intended for fallback/debug use.
- `migrate_legacy_identity` - allow auto mode to copy a valid legacy pair into app-owned storage and verify the LFDI.
- `generate_identity_if_missing` - generate one durable identity only when no usable identity exists.
- `expected_lfdi` - optional local guard that must match the certificate-derived **client** LFDI registered with Launchpad.

The app refuses to overwrite a partial or conflicting app-owned identity.

## Network

The meter's local IEEE 2030.5 service is reached on TCP port `8081` by default. A DHCP reservation for the meter is strongly recommended.

An IoT VLAN/SSID is optional. If used, allow the Home Assistant host to initiate traffic to the meter on TCP `8081`.

## MQTT and meter health

Meter health and Home Assistant/MQTT publication are separate:

- real meter-side failure can publish `Meter Health = Problem`;
- broker/Home Assistant outage can make MQTT entities unavailable while meter polling remains healthy;
- broker recovery retries automatically without restarting the app.

## Export monitoring / solar

`energy_export_enabled: false` is the default. Enable it when Current Summation Received is meaningful and the meter supports the reading.

For solar installations, use the inverter/solar integration for production. Meter Energy Delivered/Received represent grid-boundary import/export, not gross solar generation.

## Troubleshooting

See [`../docs/TROUBLESHOOTING.md`](../docs/TROUBLESHOOTING.md).

The most important troubleshooting rule is: **do not delete/regenerate a provisioned certificate as a generic recovery step.**

## Technical validation

- Production evidence: [`../docs/VALIDATION_0.4.5.md`](../docs/VALIDATION_0.4.5.md)
- SDK alignment: [`../docs/SDK_ALIGNMENT_0.4.5.md`](../docs/SDK_ALIGNMENT_0.4.5.md)
- Secure simulator/Linux test guide: [`../docs/TESTING_WITH_XCEL_SDK_SIMULATOR.md`](../docs/TESTING_WITH_XCEL_SDK_SIMULATOR.md)
