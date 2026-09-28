from __future__ import annotations

import json
from pathlib import Path

import pytest

from xcel_meter.certificate import generate_client_identity
from xcel_meter.identity_lifecycle import (
    prepare_identity,
    read_identity_manifest,
    write_identity_manifest,
)


def test_auto_migrates_legacy_identity_without_changing_lfdi(tmp_path: Path) -> None:
    own = tmp_path / "own"
    all_addons = tmp_path / "addons"
    legacy = all_addons / "513749ae_xcel-itron-mqtt" / "certs"
    legacy.mkdir(parents=True)
    source = generate_client_identity(legacy / "cert.pem", legacy / "key.pem")

    prepared = prepare_identity(
        "auto",
        own_config_root=own,
        all_addon_configs_root=all_addons,
        migrate_legacy=True,
    )

    assert prepared.action == "migrated"
    assert prepared.location.source == "own"
    assert prepared.info.lfdi == source.lfdi
    assert prepared.location.cert_path == own / "certs" / "cert.pem"
    assert prepared.location.key_path == own / "certs" / "key.pem"
    assert prepared.location.key_path.stat().st_mode & 0o777 == 0o600


def test_auto_generates_once_when_no_identity_exists(tmp_path: Path) -> None:
    own = tmp_path / "own"
    addons = tmp_path / "addons"

    first = prepare_identity(
        "auto",
        own_config_root=own,
        all_addon_configs_root=addons,
    )
    second = prepare_identity(
        "auto",
        own_config_root=own,
        all_addon_configs_root=addons,
    )

    assert first.action == "generated"
    assert second.action == "existing"
    assert first.info.lfdi == second.info.lfdi


def test_partial_app_identity_is_never_overwritten(tmp_path: Path) -> None:
    own = tmp_path / "own"
    certs = own / "certs"
    certs.mkdir(parents=True)
    (certs / "cert.pem").write_text("partial", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Incomplete certificate identity"):
        prepare_identity(
            "auto",
            own_config_root=own,
            all_addon_configs_root=tmp_path / "addons",
        )


def test_identity_manifest_preserves_origin_and_records_authentication(tmp_path: Path) -> None:
    own = tmp_path / "own"
    prep = prepare_identity(
        "auto",
        own_config_root=own,
        all_addon_configs_root=tmp_path / "addons",
    )
    path = write_identity_manifest(prep, own_config_root=own)
    assert path is not None

    existing = prepare_identity(
        "auto",
        own_config_root=own,
        all_addon_configs_root=tmp_path / "addons",
    )
    write_identity_manifest(existing, own_config_root=own, meter_authenticated=True)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["identity_origin"] == "generated"
    assert payload["meter_authenticated"] is True
    assert payload["onboarding_state"] == "active"
    assert payload["last_meter_authenticated_utc"]


def test_read_identity_manifest_returns_persisted_status(tmp_path: Path) -> None:
    own = tmp_path / "own"
    prep = prepare_identity(
        "auto",
        own_config_root=own,
        all_addon_configs_root=tmp_path / "addons",
    )
    write_identity_manifest(prep, own_config_root=own)

    payload = read_identity_manifest(own)
    assert payload["identity_origin"] == "generated"
    assert payload["lfdi"] == prep.info.lfdi
    assert payload["meter_authenticated"] is False


def test_identity_manifest_keeps_success_history_after_later_failure(tmp_path: Path) -> None:
    own = tmp_path / "own"
    addons = tmp_path / "addons"
    generated = prepare_identity(
        "auto",
        own_config_root=own,
        all_addon_configs_root=addons,
    )
    path = write_identity_manifest(generated, own_config_root=own)
    assert path is not None

    existing = prepare_identity(
        "auto",
        own_config_root=own,
        all_addon_configs_root=addons,
    )
    write_identity_manifest(existing, own_config_root=own, meter_authenticated=True)
    authenticated = read_identity_manifest(own)
    authenticated_at = authenticated["last_meter_authenticated_utc"]

    # A later authorization failure must not make this identity look like it has never worked.
    write_identity_manifest(existing, own_config_root=own, meter_authenticated=False)
    payload = read_identity_manifest(own)

    assert payload["meter_authenticated"] is True
    assert payload["onboarding_state"] == "active"
    assert payload["last_meter_authenticated_utc"] == authenticated_at
