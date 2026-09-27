from pathlib import Path

from xcel_meter.certificate import generate_client_identity
from xcel_meter.identity import check_identity, normalize_lfdi, resolve_identity_paths


def test_resolve_upstream_hidden_identity(tmp_path: Path):
    cert = tmp_path / ".cert.pem"
    key = tmp_path / ".key.pem"
    generate_client_identity(cert, key)
    assert resolve_identity_paths(str(tmp_path)) == (cert, key)


def test_resolve_addon_plain_identity(tmp_path: Path):
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    generate_client_identity(cert, key)
    assert resolve_identity_paths(str(tmp_path)) == (cert, key)


def test_expected_lfdi_mismatch_is_detected(tmp_path: Path):
    generate_client_identity(tmp_path / ".cert.pem", tmp_path / ".key.pem")
    check = check_identity(str(tmp_path), "00-11-22")
    assert check.lfdi_matches_expected is False
    assert normalize_lfdi(check.info.lfdi) != normalize_lfdi("00-11-22")
