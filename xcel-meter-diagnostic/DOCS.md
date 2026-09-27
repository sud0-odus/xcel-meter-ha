# Xcel Meter HA Diagnostic

This experimental Home Assistant app validates an Xcel Energy Itron IEEE 2030.5 meter directly from Home Assistant.

It **does not publish MQTT**, **does not regenerate certificates**, and **does not modify the legacy Xcel iTron MQTT app's files**.

## Why this build exists

The first goal is to prove the new maintained client against real Home Assistant installations and real Xcel/Itron meters before adding MQTT discovery or replacing an existing bridge.

## Identity sources

`identity_source: auto` checks, in order:

1. This app's own `/config/certs/cert.pem` + `key.pem`.
2. A legacy Home Assistant Xcel iTron MQTT app under `/addon_configs/*_xcel-itron-mqtt/certs/`.

The legacy directory is mounted read-only. This diagnostic build cannot alter those files.

If more than one legacy app exists, set `legacy_addon_slug` to the exact slug, for example `513749ae_xcel-itron-mqtt`.

## Recommended validation settings

```yaml
meter_ip: 192.168.1.100
meter_port: 8081
expected_lfdi: YOUR-LAUNCHPAD-LFDI
identity_source: auto
legacy_addon_slug: ""
timeout: 8
poll_interval: 60
log_level: INFO
```

Replace the IP, LFDI, and legacy slug for other installations.

## Expected successful log

```text
Identity source: legacy
Certificate-derived LFDI: ...
LFDI validation: MATCH
TLS/IEEE 2030.5 connection: PASS
Itron agent version: ...
Meter software version: ...
Instantaneous power: ... W
Energy delivered: ... Wh
Energy received: ... Wh
RESULT: PASS
```

## Security note

This diagnostic app temporarily requests read-only access to `all_addon_configs` solely to discover an existing legacy Xcel meter identity without copying or exposing its private key. The stable replacement is intended to use only its own `addon_config` after identity migration, eliminating this broad read permission.
