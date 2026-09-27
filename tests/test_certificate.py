from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from xcel_meter.certificate import compute_lfdi, generate_client_identity, inspect_client_identity


def test_generated_identity_is_ieee_2030_5_shaped(tmp_path: Path):
    cert_path = tmp_path / ".cert.pem"
    key_path = tmp_path / ".key.pem"

    info = generate_client_identity(cert_path, key_path)

    assert len(info.lfdi) == 40
    assert info.lfdi == info.lfdi.upper()
    assert info.key_matches
    assert info.ieee_policy_present
    assert info.digital_signature_only
    assert info.curve == "secp256r1"
    assert not info.is_expired
    assert info.days_remaining > 1000

    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    assert compute_lfdi(cert) == info.lfdi

    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    assert isinstance(key, ec.EllipticCurvePrivateKey)


def test_existing_identity_is_not_overwritten_by_default(tmp_path: Path):
    cert_path = tmp_path / ".cert.pem"
    key_path = tmp_path / ".key.pem"
    first = generate_client_identity(cert_path, key_path)

    try:
        generate_client_identity(cert_path, key_path)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected FileExistsError")

    second = inspect_client_identity(cert_path, key_path)
    assert first.lfdi == second.lfdi
