# Xcel Meter HA 0.4.5b2

This Home Assistant app reads a Launchpad-enabled Xcel/Itron meter locally over IEEE 2030.5 and publishes the validated readings as one Home Assistant MQTT device.

## Existing-user upgrade

Keep the legacy Xcel iTron MQTT add-on installed but stopped for the first 0.4.5b2 migration test.

With the defaults below, `identity_source: auto` first looks for this app's own identity. If none exists, it finds the legacy certificate/key, validates the IEEE 2030.5 profile, copies the pair into this app's writable `/config/certs` storage, verifies that the LFDI did not change, and then connects using the app-owned copy.

```yaml
meter_ip: 192.168.1.122
meter_port: 8081
expected_lfdi: YOUR_LAUNCHPAD_LFDI
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

If more than one legacy add-on exists, set `legacy_addon_slug` explicitly.

Do not remove the legacy add-on until the log confirms the migrated app-owned identity has the same LFDI and completes a real meter poll. After that, restart Xcel Meter HA once more and confirm it reports `Identity source: own` and continues to pass.

## New install

If there is no app-owned or legacy identity and `generate_identity_if_missing` is enabled, the app creates one P-256 IEEE 2030.5 client identity in `/config/certs`.

`meter_ip` may be left unset during this first identity step. The log will print an action message containing the generated LFDI and then report `Onboarding pending` rather than treating the missing meter address as a meter failure. Register that exact LFDI in Xcel Energy Launchpad, keep the generated certificate/key, and configure `meter_ip` when ready to validate the local meter connection.

After `meter_ip` is set, the app retries with the same durable identity while provisioning completes. If the meter explicitly rejects a newly generated certificate during TLS and that identity has never authenticated successfully, the app reports the state as possible provisioning-pending and tells the user to keep the same LFDI. Migrated/previously active identity failures remain real errors.

Because Xcel does not expose a provisioning-status API in the supplied SDK, every possible pre-provisioning failure cannot be identified perfectly; transport failures still remain ordinary meter/network failures.

## Identity files

App-owned files:

- `/config/certs/cert.pem`
- `/config/certs/key.pem`
- `/config/certs/identity.json` (non-secret status only)

The private key is never emitted in logs or `identity.json`.

## Identity controls

- `identity_source: auto` — prefer app-owned identity; otherwise migrate/use legacy; otherwise generate if allowed.
- `identity_source: own` — use app-owned identity or generate it when generation is enabled.
- `identity_source: legacy` — read the legacy identity directly without migration; intended only as a fallback/debug mode.
- `migrate_legacy_identity` — when true, auto mode copies a valid legacy pair into app-owned storage and verifies the LFDI.
- `generate_identity_if_missing` — when true, auto/own mode generates one durable identity only when no identity exists.

The app refuses to overwrite a partial or conflicting app-owned identity.

## MQTT and meter health

The meter and Home Assistant/MQTT failure domains remain separate:

- real meter-side failure can publish `Meter Health = Problem`;
- broker/Home Assistant outage makes MQTT entities unavailable but does not turn a healthy meter into a meter problem;
- broker recovery retries automatically without restarting the app.

## Export monitoring

`energy_export_enabled: false` is the default. Homes that do not export electricity poll only Instantaneous Power and Energy Delivered. Enable the option if Current Summation Received is meaningful for the installation.

## SDK alignment

0.4.5b2 aligns certificate validation, ReadingType definitions, list paging, and the IEEE 2030.5 Accept header with the supplied Xcel Launchpad client SDK. See the repository document `docs/SDK_ALIGNMENT_0.4.5.md` for intentional differences and open questions.
