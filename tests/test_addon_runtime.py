from pathlib import Path

import pytest

from xcel_meter.addon_runtime import find_identity


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
