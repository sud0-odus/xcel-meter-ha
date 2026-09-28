from pathlib import Path

import pytest

from xcel_meter.addon_runtime import OnboardingPendingError, find_identity, run_once
from xcel_meter.http import MeterHttpError


def _touch_pair(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "cert.pem").write_text("cert")
    (directory / "key.pem").write_text("key")


def test_auto_prefers_own_identity(tmp_path: Path) -> None:
    own = tmp_path / "own"
    all_configs = tmp_path / "addons"
    _touch_pair(own / "certs")
    _touch_pair(all_configs / "123_xcel-itron-mqtt" / "certs")

    location = find_identity("auto", own, all_configs)

    assert location.source == "own"
    assert location.cert_path == own / "certs" / "cert.pem"


def test_auto_finds_legacy_identity(tmp_path: Path) -> None:
    own = tmp_path / "own"
    all_configs = tmp_path / "addons"
    _touch_pair(all_configs / "513749ae_xcel-itron-mqtt" / "certs")

    location = find_identity("auto", own, all_configs)

    assert location.source == "legacy"
    assert location.cert_path == all_configs / "513749ae_xcel-itron-mqtt" / "certs" / "cert.pem"


def test_explicit_legacy_slug(tmp_path: Path) -> None:
    own = tmp_path / "own"
    all_configs = tmp_path / "addons"
    _touch_pair(all_configs / "one_xcel-itron-mqtt" / "certs")
    _touch_pair(all_configs / "two_xcel-itron-mqtt" / "certs")

    location = find_identity("legacy", own, all_configs, "two_xcel-itron-mqtt")

    assert location.cert_path == all_configs / "two_xcel-itron-mqtt" / "certs" / "cert.pem"


def test_legacy_missing_has_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="No legacy Xcel iTron MQTT"):
        find_identity("legacy", tmp_path / "own", tmp_path / "addons")


def test_run_once_prepares_identity_before_meter_ip_is_configured(monkeypatch, tmp_path: Path) -> None:
    class DummyInfo:
        lfdi = "A" * 40

    class DummyLocation:
        source = "own"
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

    class DummyPreparation:
        action = "existing"
        location = DummyLocation()
        info = DummyInfo()

    prepared = DummyPreparation()
    calls: list[str] = []

    def fake_prepare(*args, **kwargs):
        calls.append("prepare")
        return prepared

    def fake_validate(location, expected_lfdi):
        calls.append("validate")
        return prepared.info

    def fake_manifest(preparation, **kwargs):
        calls.append("manifest")
        return None

    monkeypatch.setattr("xcel_meter.addon_runtime.prepare_identity", fake_prepare)
    monkeypatch.setattr("xcel_meter.addon_runtime.validate_identity", fake_validate)
    monkeypatch.setattr("xcel_meter.addon_runtime.write_identity_manifest", fake_manifest)

    with pytest.raises(OnboardingPendingError, match="Client identity is ready"):
        run_once({"meter_ip": "", "identity_source": "auto"})

    assert calls == ["prepare", "validate", "manifest"]


def test_generated_never_authenticated_client_rejection_is_onboarding_pending(monkeypatch, tmp_path: Path) -> None:
    class DummyInfo:
        lfdi = "B" * 40

    class DummyLocation:
        source = "own"
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

    class DummyPreparation:
        action = "existing"
        location = DummyLocation()
        info = DummyInfo()

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("xcel_meter.addon_runtime.prepare_identity", lambda *a, **k: DummyPreparation())
    monkeypatch.setattr("xcel_meter.addon_runtime.validate_identity", lambda *a, **k: DummyInfo())
    monkeypatch.setattr("xcel_meter.addon_runtime.write_identity_manifest", lambda *a, **k: None)
    monkeypatch.setattr(
        "xcel_meter.addon_runtime.read_identity_manifest",
        lambda: {"identity_origin": "generated", "meter_authenticated": False},
    )
    monkeypatch.setattr("xcel_meter.addon_runtime.Ieee20305Client", DummyClient)

    def reject(*args, **kwargs):
        raise MeterHttpError("client rejected", kind="client_auth", path="/upt")

    monkeypatch.setattr("xcel_meter.addon_runtime.discover_core_profile", reject)

    with pytest.raises(OnboardingPendingError, match="provisioning may still be pending"):
        run_once({"meter_ip": "192.0.2.10", "identity_source": "auto"})


def test_migrated_identity_client_rejection_remains_failure(monkeypatch, tmp_path: Path) -> None:
    class DummyInfo:
        lfdi = "C" * 40

    class DummyLocation:
        source = "own"
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

    class DummyPreparation:
        action = "existing"
        location = DummyLocation()
        info = DummyInfo()

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("xcel_meter.addon_runtime.prepare_identity", lambda *a, **k: DummyPreparation())
    monkeypatch.setattr("xcel_meter.addon_runtime.validate_identity", lambda *a, **k: DummyInfo())
    monkeypatch.setattr("xcel_meter.addon_runtime.write_identity_manifest", lambda *a, **k: None)
    monkeypatch.setattr(
        "xcel_meter.addon_runtime.read_identity_manifest",
        lambda: {"identity_origin": "migrated", "meter_authenticated": False},
    )
    monkeypatch.setattr("xcel_meter.addon_runtime.Ieee20305Client", DummyClient)

    def reject(*args, **kwargs):
        raise MeterHttpError("client rejected", kind="client_auth", path="/upt")

    monkeypatch.setattr("xcel_meter.addon_runtime.discover_core_profile", reject)

    with pytest.raises(MeterHttpError, match="client rejected"):
        run_once({"meter_ip": "192.0.2.10", "identity_source": "auto"})


@pytest.mark.parametrize("status", [401, 403])
def test_generated_never_authenticated_http_auth_rejection_is_onboarding_pending(
    monkeypatch,
    tmp_path: Path,
    status: int,
) -> None:
    class DummyInfo:
        lfdi = "D" * 40

    class DummyLocation:
        source = "own"
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

    class DummyPreparation:
        action = "existing"
        location = DummyLocation()
        info = DummyInfo()

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("xcel_meter.addon_runtime.prepare_identity", lambda *a, **k: DummyPreparation())
    monkeypatch.setattr("xcel_meter.addon_runtime.validate_identity", lambda *a, **k: DummyInfo())
    monkeypatch.setattr("xcel_meter.addon_runtime.write_identity_manifest", lambda *a, **k: None)
    monkeypatch.setattr(
        "xcel_meter.addon_runtime.read_identity_manifest",
        lambda: {"identity_origin": "generated", "meter_authenticated": False},
    )
    monkeypatch.setattr("xcel_meter.addon_runtime.Ieee20305Client", DummyClient)

    def reject(*args, **kwargs):
        raise MeterHttpError(
            f"HTTP {status}",
            kind="http",
            status=status,
            path="/upt",
        )

    monkeypatch.setattr("xcel_meter.addon_runtime.discover_core_profile", reject)

    with pytest.raises(OnboardingPendingError, match="SDK simulator returns HTTP 403"):
        run_once({"meter_ip": "192.0.2.10", "identity_source": "auto"})


@pytest.mark.parametrize("status", [401, 403])
def test_previously_authenticated_generated_identity_http_auth_remains_failure(
    monkeypatch,
    tmp_path: Path,
    status: int,
) -> None:
    class DummyInfo:
        lfdi = "E" * 40

    class DummyLocation:
        source = "own"
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"

    class DummyPreparation:
        action = "existing"
        location = DummyLocation()
        info = DummyInfo()

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr("xcel_meter.addon_runtime.prepare_identity", lambda *a, **k: DummyPreparation())
    monkeypatch.setattr("xcel_meter.addon_runtime.validate_identity", lambda *a, **k: DummyInfo())
    monkeypatch.setattr("xcel_meter.addon_runtime.write_identity_manifest", lambda *a, **k: None)
    monkeypatch.setattr(
        "xcel_meter.addon_runtime.read_identity_manifest",
        lambda: {"identity_origin": "generated", "meter_authenticated": True},
    )
    monkeypatch.setattr("xcel_meter.addon_runtime.Ieee20305Client", DummyClient)

    def reject(*args, **kwargs):
        raise MeterHttpError(f"HTTP {status}", kind="http", status=status, path="/upt")

    monkeypatch.setattr("xcel_meter.addon_runtime.discover_core_profile", reject)

    with pytest.raises(MeterHttpError, match=f"HTTP {status}"):
        run_once({"meter_ip": "192.0.2.10", "identity_source": "auto"})
