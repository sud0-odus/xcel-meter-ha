# Testing with the Xcel SDK Meter Simulator on Linux

This guide is for developers who have access to Xcel's `energy-launchpadsdk-client` meter-simulator source and want to validate Xcel Meter HA without touching a production meter or production Launchpad identity.

It assumes Linux and Docker are already installed. It does not explain host dependency installation.

## Safety model

Keep simulator work separate from Home Assistant and production certificates.

A good disposable layout is:

```text
/var/tmp/xcel-meter-sim-XXXXXX/
  xcel-meter-ha/
  energy-launchpadsdk-client-feature-meter-simulator/
  certs/
  state-test/
```

Use a Docker `--internal` network and do not publish simulator port `8081` to the host/LAN unless a specific test requires it.

Never copy a production `cert.pem` or `key.pem` into this workspace.

## 1. Create an isolated workspace

```bash
SIM_ROOT="$(mktemp -d /var/tmp/xcel-meter-sim-XXXXXX)"
chmod 700 "$SIM_ROOT"
cd "$SIM_ROOT"
```

Place/extract the Xcel SDK simulator checkout under this directory, then clone Xcel Meter HA:

```bash
git clone https://github.com/sud0-odus/xcel-meter-ha.git
```

For a reproducible release test, check out the exact commit/tag you intend to validate.

## 2. Build the Xcel Meter HA client image

```bash
cd "$SIM_ROOT"

docker build \
  -t xcel-meter-ha-sim-client:local \
  -f xcel-meter-ha/tools/simulator/Dockerfile.client \
  xcel-meter-ha
```

## 3. Build the secure Xcel simulator image

The simulator must run in **Production** mode. Do not use an SDK compose profile that disables certificate security for development/Swagger use.

Typical build:

```bash
docker build \
  -t xcel-launchpad-meter-simulator:local \
  -f energy-launchpadsdk-client-feature-meter-simulator/launchpad/Dockerfile \
  energy-launchpadsdk-client-feature-meter-simulator/launchpad
```

During the 0.4.5b2 validation campaign, the supplied SDK Dockerfile's Bullseye `curl` install/healthcheck failed because old package URLs returned `404`. The simulator itself still built and ran after making a **disposable Dockerfile copy** that removed only the `curl` install and healthcheck. If you encounter the same packaging-only failure, do not alter simulator source, TLS settings, application entrypoint, or meter behavior to make the test pass.

## 4. Create a private Docker network and disposable identity

```bash
docker network create --internal xcel-meter-ha-sim-net
mkdir -p certs
chmod 700 certs

docker run --rm \
  -v "$PWD/certs:/certs" \
  xcel-meter-ha-sim-client:local \
  cert init --dir /certs
```

Record the **disposable** LFDI printed by the command. Do not register it in the real Xcel Launchpad portal.

The generated certificate should report P-256/secp256r1, SHA-256, Digital Signature key usage, the IEEE 2030.5 client policy, and a self-signed certificate.

## 5. Prove an unregistered LFDI is rejected

Start Agent v1 with an intentionally incorrect ACL value:

```bash
WRONG_LFDI="0000000000000000000000000000000000000000"

docker run -d \
  --name xcel-meter-sim-v1 \
  --network xcel-meter-ha-sim-net \
  -e ASPNETCORE_ENVIRONMENT=Production \
  -e ASPNETCORE_URLS=https://+:8081 \
  -e ItronAgentVersion=1 \
  -e LFDIs__0="$WRONG_LFDI" \
  xcel-launchpad-meter-simulator:local
```

Probe from the client container:

```bash
docker run --rm \
  --network xcel-meter-ha-sim-net \
  -v "$PWD/certs:/certs:ro" \
  xcel-meter-ha-sim-client:local \
  probe --host xcel-meter-sim-v1 --port 8081 \
  --dir /certs --path /upt --timeout 8
```

Expected simulator result: HTTP `403` and a non-zero client exit code. Xcel's simulator documentation distinguishes this from the real-agent notes, which describe `401` for an unregistered client.

This test demonstrates ACL rejection. It does **not** simulate Xcel's cloud provisioning delay.

## 6. Allowlist the exact same identity

Remove/restart the simulator using the LFDI generated in step 4:

```bash
TEST_LFDI="PUT_THE_DISPOSABLE_40_HEX_LFDI_HERE"

docker rm -f xcel-meter-sim-v1

docker run -d \
  --name xcel-meter-sim-v1 \
  --network xcel-meter-ha-sim-net \
  -e ASPNETCORE_ENVIRONMENT=Production \
  -e ASPNETCORE_URLS=https://+:8081 \
  -e ItronAgentVersion=1 \
  -e LFDIs__0="$TEST_LFDI" \
  xcel-launchpad-meter-simulator:local
```

Then probe and read:

```bash
docker run --rm \
  --network xcel-meter-ha-sim-net \
  -v "$PWD/certs:/certs:ro" \
  xcel-meter-ha-sim-client:local \
  probe --host xcel-meter-sim-v1 --port 8081 \
  --dir /certs --expected-lfdi "$TEST_LFDI" \
  --path /upt --timeout 8

docker run --rm \
  --network xcel-meter-ha-sim-net \
  -v "$PWD/certs:/certs:ro" \
  xcel-meter-ha-sim-client:local \
  read --host xcel-meter-sim-v1 --port 8081 \
  --dir /certs --expected-lfdi "$TEST_LFDI" \
  --timeout 8 --pretty
```

Expected secure result:

```text
HTTP 200 OK
Cipher: ECDHE-ECDSA-AES128-CCM8
```

The read should discover Instantaneous Demand, Current Summation Delivered, and Current Summation Received from the simulator.

## 7. Repeat with Agent v3

Stop v1 and start the same image with:

```bash
-e ItronAgentVersion=3
-e LFDIs__0="$TEST_LFDI"
```

Repeat `probe` and `read` with the v3 container name. Using the same disposable identity across v1 and v3 proves the client identity is independent of the simulated agent generation.

## 8. Extended regression checks

The 0.4.5b2 campaign also exercised these cases. The b3 PowerShell harness now automates identity overwrite protection and expected-LFDI mismatch; the remaining checks are still useful after changes to identity/discovery code.

### Identity overwrite protection

The b3 automated harness performs this check. For a manual Linux run, hash `cert.pem` and `key.pem`, run `cert init --dir /certs` again, and verify:

- command exits non-zero;
- it says the existing identity must be reused;
- both file hashes remain byte-for-byte identical.

### Expected-LFDI mismatch

The b3 automated harness performs this check. For a manual run, use `cert show` with a deliberately wrong `--expected-lfdi`. Expected result: `LFDI check: MISMATCH` and a non-zero exit code.

### Real paging behavior

Force the simulator MeterReading list to `l=1` and verify discovery follows returned result counts/start offsets until all advertised items are read. In the v3 simulator campaign, four requests were required and four resources were classified, including `Wh Interval Delivered`.

### Onboarding state machine

Use a second fresh disposable identity:

1. Keep it off the ACL -> newly generated, never-authenticated identity should be onboarding pending.
2. Add the exact LFDI -> state should become active and record `meter_authenticated: true`.
3. Remove the LFDI after success -> HTTP `403` must be an authorization error, **not** a return to first-time provisioning pending.
4. Restore the LFDI -> same identity should become active again without regeneration.

### Server identity correlation

For the Xcel simulator, derive the LFDI from the TLS server certificate (`SHA-256(DER)`, first 20 bytes) and compare it with `/sdev/sdi`. The 0.4.5b2 campaign observed an exact match.

This is evidence worth retaining, but production pinning is not enabled until Xcel's meter-replacement/certificate-rotation contract is understood.

### Interval resources

The v3 simulator advertised `Wh Interval Delivered` and a ReadingSet with a 43,200-second time period, while the linked ReadingList returned `all="0" results="0"`.

That proves an advertised interval resource does not guarantee interval samples are available. Do not treat interval history as supported solely because a link exists.

## What these tests prove

They provide strong local evidence for:

- SDK-compatible client certificate generation/LFDI derivation;
- mutual TLS/cipher interoperability with Xcel's simulator;
- LFDI authorization behavior;
- safe identity persistence;
- v1/v3 discovery and classification;
- paging behavior;
- onboarding state transitions driven by prior authentication history;
- specific simulator server-identity and interval-resource semantics.

## What these tests do not prove

They do **not** prove:

- Xcel's real provisioning time or portal workflow;
- production Wi-Fi/radio behavior;
- every Itron firmware layout;
- real-meter behavior during a utility outage;
- physical meter replacement/counter-reset semantics;
- whether production clients should pin the meter/server LFDI;
- real interval-history availability;
- Home Assistant/MQTT behavior unless those layers are separately included in the test.

Production evidence remains documented separately in [`VALIDATION_0.4.5.md`](VALIDATION_0.4.5.md).

## Preserve or clean up

If more validation is planned soon, stop the simulator container and keep the isolated workspace/images/network. Otherwise, remove only resources created for this test. Avoid broad `docker system prune` commands on a shared host.
