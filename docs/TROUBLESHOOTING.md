# Troubleshooting

Start with the failure domain shown in the log. Avoid deleting certificates as a general recovery step.

## New install is still `Onboarding / provisioning pending`

This state is intentionally available only for an app-generated identity that has **never authenticated successfully** and receives an explicit client-auth rejection/HTTP `401` or `403`.

Check:

1. The LFDI shown in Xcel Meter HA is exactly the LFDI entered in Xcel Launchpad.
2. The meter is shown as enrolled/managed in Xcel's portal.
3. The meter has joined Wi-Fi and has a reachable IP address.
4. Home Assistant can reach that IP on TCP `8081`.
5. Keep the existing `/config/certs/cert.pem` and `/config/certs/key.pem` while waiting.

Do **not** regenerate the identity to "try again." A new certificate creates a different LFDI and starts a different provisioning lifecycle.

## HTTP 401/403 after the meter previously worked

Once the same identity has authenticated successfully, a later `401`/`403` is treated as a real authorization problem, not first-time provisioning.

Check whether:

- the Launchpad device registration was changed or removed;
- the wrong LFDI is now registered;
- a different certificate/key was restored from backup;
- Xcel changed the meter/account/device authorization;
- the physical meter was replaced.

Preserve the current identity until the cause is understood.

## LFDI mismatch

If `expected_lfdi` is configured and does not match the certificate-derived LFDI, stop and determine which identity is actually registered with Xcel.

Do not "fix" a mismatch by deleting the certificate. If the Launchpad registration points to an older working identity, restore that identity. If you intentionally choose a new identity, it must be registered/provisioned as a new device.

## Meter is unreachable or times out

Check the network before changing identity:

- confirm the meter is associated with Wi-Fi;
- verify the current meter IP in the router/controller;
- use a DHCP reservation so it remains stable;
- ensure VLAN/firewall rules allow Home Assistant -> meter TCP `8081`;
- look for ordinary timeouts versus TLS/authentication errors in the app log.

The meter can exhibit transient response/TLS failures. Xcel Meter HA keeps a discovered profile across ordinary transport failures rather than forcing a full rediscovery every time.

## `BAD_SIGNATURE` or intermittent TLS errors

Transient TLS `BAD_SIGNATURE`/handshake failures have been seen in this meter ecosystem. The app uses conservative retry behavior and a low request rate rather than increasing concurrency.

Repeated failures should be investigated as transport/meter compatibility problems. They must not trigger certificate regeneration.

## Instantaneous Power looks stuck during an outage

Do not assume the right correction is `0 W`.

Xcel Meter HA uses meter-provided source timestamps when present. A stale sample is not published as fresh current power and is not replaced with a fabricated zero. If the meter does not provide timestamp metadata, freshness is explicitly unavailable.

Check the log for sample freshness details and compare the behavior with meter/network reachability.

## MQTT entities are unavailable but meter polling is healthy

This can be normal during a broker or Home Assistant outage. Meter health and MQTT publication are separate failure domains.

If the log continues to show successful meter reads while MQTT publication fails, fix the MQTT broker/Supervisor service without changing the meter identity. Xcel Meter HA retries MQTT publication and has been validated to recover without an app restart after a Mosquitto outage.

## Agent/software version shows `unknown`

That is not automatically an error. Some meters do not expose an authoritative software version. Xcel Meter HA uses ReadingType/resource discovery instead of silently guessing firmware from a missing value.

## Energy Received is missing

`energy_export_enabled` defaults to `false`. If the installation exports power and the meter exposes Current Summation Received, enable it:

```yaml
energy_export_enabled: true
```

Do not infer solar production from Energy Received. It is grid export at the meter boundary.

## Useful files

App-owned identity/status files:

```text
/config/certs/cert.pem
/config/certs/key.pem
/config/certs/identity.json
```

`identity.json` is intended for non-secret diagnostic state. **Never post `key.pem`.**

## When opening an issue

Include:

- Xcel Meter HA version;
- Home Assistant version/platform;
- whether this is a fresh identity or migrated identity;
- whether this exact identity ever authenticated successfully;
- sanitized log lines around the failure;
- whether meter TCP `8081` is reachable;
- whether MQTT is healthy;
- meter software/agent version only if the app reports it authoritatively.

Redact account information, public IPs, Wi-Fi credentials, and any private key. A client or meter LFDI is not the private key, but it is still an installation identifier and should be redacted from public issue logs unless it is specifically needed.
