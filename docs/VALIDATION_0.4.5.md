# 0.4.5 validation record

## Production-meter baseline validated on 2026-09-28

The 0.4.5b1 candidate completed the following checks against a production Xcel/Itron meter:

- GitHub CI passed lint, root/add-on source parity, package/app version parity, and the Python 3.12/3.13/3.14 pytest matrix.
- The legacy `xcel-itron-mqtt` client certificate/key were migrated into Xcel Meter HA app-owned `/config/certs` storage.
- The certificate-derived LFDI remained unchanged during migration.
- The migrated identity passed certificate/key, P-256, SHA-256, IEEE 2030.5 policy, critical KeyUsage, and self-signed validation.
- The production meter accepted the migrated app-owned identity and returned live meter readings.
- After restarting Xcel Meter HA, the app reused `Identity source: own` without repeating migration.
- After uninstalling the legacy add-on, Xcel Meter HA restarted again using only the app-owned identity and still passed TLS/IEEE 2030.5, meter health, core readings, and MQTT publication.

No production identifiers or private-key material are recorded in this document.

## 0.4.5b2 secure simulator gate

Before intentionally testing a brand-new identity against Xcel Launchpad, use the secure SDK simulator harness in `tools/simulator/`. The desired result is:

1. disposable identity generated once;
2. unregistered LFDI rejected by the simulator with its documented HTTP 403 behavior;
3. same LFDI added to simulator ACL;
4. TLS 1.2 / ECDHE-ECDSA-AES128-CCM8 succeeds;
5. v1 secure discovery/read succeeds;
6. v3 secure discovery/read succeeds.

A production Launchpad enrollment test should use a separate deliberate lifecycle plan; never replace the currently provisioned production identity merely to exercise onboarding.
