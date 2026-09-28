# Milestone 3: Home Assistant-native validation

> **Historical milestone document.** This file records an earlier implementation stage and is retained for project history. For current installation and behavior, use the root `README.md`, `docs/GETTING_STARTED.md`, and `docs/VALIDATION_0.4.5.md`.


## Goal

Validate the maintained IEEE 2030.5 client in the environment where it will actually run: Home
Assistant OS / Supervisor apps.

No desktop Python installation is required for users.

## Scope

The `xcel-meter-diagnostic` app:

1. Starts inside Home Assistant.
2. Finds an identity from its own app config or a legacy `xcel-itron-mqtt` app.
3. Derives the LFDI from the actual certificate.
4. Optionally compares it to the user's Launchpad LFDI.
5. Validates certificate/key shape and expiry.
6. Connects to the meter using IEEE 2030.5 TLS 1.2.
7. Detects Itron agent/software version.
8. Discovers the active electricity UsagePoint and MeterReadings.
9. Prints normalized instantaneous demand and delivered/received energy.
10. Repeats at a configurable interval so stability can be observed.

## Deliberate non-goals

- No MQTT publishing yet.
- No Home Assistant entities yet.
- No certificate generation during diagnostic startup.
- No copying or modifying the legacy app identity.
- No hidden automatic migration.

## Migration permission

The diagnostic app maps `all_addon_configs` read-only so an existing identity can be reused without
manual extraction. This is intentionally temporary. Once migration is implemented, the stable app
will store its identity only in its own `addon_config` and will not need broad add-on config access.

## Pass criteria

A real Home Assistant installation should show all of the following in app logs:

```text
Certificate/key match: OK
IEEE 2030.5 policy: OK
LFDI validation: MATCH
TLS/IEEE 2030.5 connection: PASS
Itron agent version: ...
Instantaneous power: ... W
Energy delivered: ... Wh
RESULT: PASS
```

A mismatch must fail clearly before repeated meter connection attempts.
