# Compatibility strategy

The project treats Xcel Energy's Energy Launchpad client SDK as the protocol reference while
implementing a small Python client intended for Home Assistant deployments.

Current targets:

- IEEE 2030.5 mutual TLS on TCP/8081.
- EC P-256 self-signed client identity.
- SHA-256 LFDI, left-truncated to 160 bits.
- TLS 1.2 with `ECDHE-ECDSA-AES128-CCM8`.
- `/sdev/sdi` DeviceInformation and Itron agent version discovery.
- `/upt` dynamic active-electricity UsagePoint discovery.
- Dynamic MeterReading + ReadingType enumeration.
- Agent v2/v3 reading-type rules from the official Xcel Launchpad SDK.
- Core instantaneous demand and delivered/received summation values.

## Certificate lifecycle

A client certificate is the identity Xcel/Itron authorizes. Regenerating the certificate changes
the LFDI. The new LFDI must be registered through Xcel Energy Launchpad before the meter accepts
that identity.

The CLI can compare the expected/Launchpad LFDI to the LFDI calculated from the actual certificate
before opening a network connection. This directly prevents the failure discovered during the
2026 real-world test where the HA add-on retained an old displayed LFDI after the certificate had
been regenerated.

## Itron agent versions

The official SDK reports agent v3 when `/sdev/sdi` has a software version with major version 3;
otherwise it defaults to v2 because reliable version metadata was added with v3.

Agent v3 changes ReadingType semantics and makes current summation Wh and TOU Wh structurally
indistinguishable. The official SDK uses the MeterReading description to distinguish these two
cases, and this project mirrors that behavior.

## Failure classification

`SSLV3_ALERT_BAD_CERTIFICATE` means the peer rejected the client certificate during TLS.
Troubleshoot certificate identity/provisioning before MQTT or Home Assistant discovery.
