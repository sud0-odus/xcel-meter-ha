# xcel-meter-ha

A maintained Xcel Energy / Itron Gen 5 Riva smart-meter client and Home Assistant bridge.

The project is being built and validated **inside Home Assistant first**. The official Xcel Energy
Launchpad client SDK is used as the behavior reference for IEEE 2030.5 identity, Itron agent
versions, and reading-type semantics.

## Status: v0.3 Home Assistant diagnostic milestone

Implemented:

- IEEE 2030.5 EC P-256 client identity generation and inspection
- certificate-derived LFDI
- expected/Launchpad LFDI mismatch detection
- TLS/HTTP diagnostics
- DeviceInformation + Itron agent version discovery
- active electricity UsagePoint discovery
- MeterReading/ReadingType discovery
- Itron v2/v3 core reading classification
- instantaneous demand, delivered energy and received energy normalization
- Home Assistant diagnostic app packaging
- read-only reuse of an existing `xcel-itron-mqtt` identity for migration testing
- automated tests and Python 3.12/3.13/3.14 CI

The v0.3 diagnostic app intentionally **does not publish MQTT** and **does not modify certificate
files**. Its job is to prove the new client against real Home Assistant installations and real
Xcel/Itron meters before it becomes a replacement bridge.

## Important: preserve your identity

Deleting the certificate directory creates a new certificate and therefore a new LFDI. Xcel must
provision that new LFDI before the meter accepts it. Never delete/regenerate certs as a generic
troubleshooting step.

The project explicitly detects this condition:

```text
Expected/Launchpad LFDI: D80C3...
Certificate-derived LFDI: 65C05...
ERROR: identity mismatch; do not connect/retry.
```

## Home Assistant diagnostic app

The app is under `xcel-meter-diagnostic/`.

For migration validation it can read an existing legacy Xcel iTron MQTT app identity **read-only**.
With `identity_source: auto`, it checks its own public config first and then scans legacy app config
folders matching `*_xcel-itron-mqtt`.

A successful run reports:

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

See `xcel-meter-diagnostic/DOCS.md` and `docs/MILESTONE3.md`.

## Development install

Development and CI can still run outside Home Assistant, but desktop Python is **not required for
end users**.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

## Roadmap

1. Identity + TLS diagnostics — complete
2. Agent/UsagePoint discovery + core readings — complete in library
3. Home Assistant-native diagnostic validation — current milestone
4. MQTT publisher + modern Home Assistant device discovery
5. Safe identity migration into this app's own `addon_config` and removal of broad migration access
6. interval/TOU readings, diagnostics entities, certificate lifecycle alerts
7. simulator-backed regression matrix and public release tooling

## Security

- Never commit private keys or HA backups.
- Never log private-key material.
- Persist the client identity so the Launchpad-registered LFDI remains stable.
- Rotate before expiry and register/provision the replacement identity before switching.
- `all_addon_configs` is used read-only only in the v0.3 migration/diagnostic build. The stable app
  is intended to use only its own `addon_config` after migration.
