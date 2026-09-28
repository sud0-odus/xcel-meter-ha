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


def test_import_profile_accepts_digital_signature_with_other_key_usages(tmp_path: Path):
    from datetime import UTC, datetime, timedelta

    from cryptography.hazmat.primitives import hashes
    from cryptography.x509.oid import NameOID

    from xcel_meter.certificate import IEEE_2030_5_SELF_SIGNED_CLIENT_POLICY

    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ImportTest")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.CertificatePolicies(
                [x509.PolicyInformation(IEEE_2030_5_SELF_SIGNED_CLIENT_POLICY, None)]
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    info = inspect_client_identity(cert_path, key_path)
    assert info.digital_signature_present is True
    assert info.digital_signature_only is False
    assert info.key_usage_critical is True
    assert info.ieee_policy_critical is True
    assert info.self_signed is True
