from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ObjectIdentifier

IEEE_2030_5_SELF_SIGNED_CLIENT_POLICY = ObjectIdentifier("1.3.6.1.4.1.40732.2.2")


@dataclass(frozen=True)
class CertificateInfo:
    cert_path: Path
    key_path: Path
    lfdi: str
    not_before: datetime
    not_after: datetime
    days_remaining: int
    is_expired: bool
    key_matches: bool
    ieee_policy_present: bool
    ieee_policy_critical: bool
    digital_signature_present: bool
    digital_signature_only: bool
    key_usage_critical: bool
    self_signed: bool
    signature_hash: str
    curve: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def compute_lfdi(cert: x509.Certificate) -> str:
    """IEEE 2030.5 LFDI: SHA-256(DER certificate), left-truncated to 160 bits."""
    der = cert.public_bytes(serialization.Encoding.DER)
    return sha256(der).hexdigest()[:40].upper()


def generate_client_identity(
    cert_path: Path,
    key_path: Path,
    common_name: str = "MeterReaderHanClient",
    valid_days: int = 1094,
    overwrite: bool = False,
) -> CertificateInfo:
    if not overwrite and (cert_path.exists() or key_path.exists()):
        raise FileExistsError(
            "Certificate/key already exist. Reuse them to preserve the registered LFDI, "
            "or explicitly request overwrite and re-register the NEW LFDI with Xcel Launchpad."
        )

    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = _utc_now()

    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=valid_days))
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
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

    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.chmod(0o600)

    return inspect_client_identity(cert_path, key_path)


def _is_self_signed(cert: x509.Certificate) -> bool:
    if cert.issuer != cert.subject:
        return False
    public_key = cert.public_key()
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        return False
    try:
        public_key.verify(
            cert.signature,
            cert.tbs_certificate_bytes,
            ec.ECDSA(cert.signature_hash_algorithm),
        )
    except (InvalidSignature, TypeError, ValueError):
        return False
    return True


def inspect_client_identity(cert_path: Path, key_path: Path) -> CertificateInfo:
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)

    cert_pub = cert.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    key_pub = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    try:
        policy_ext = cert.extensions.get_extension_for_class(x509.CertificatePolicies)
        ieee_policy_present = any(
            p.policy_identifier == IEEE_2030_5_SELF_SIGNED_CLIENT_POLICY
            for p in policy_ext.value
        )
        ieee_policy_critical = policy_ext.critical
    except x509.ExtensionNotFound:
        ieee_policy_present = False
        ieee_policy_critical = False

    try:
        usage_ext = cert.extensions.get_extension_for_class(x509.KeyUsage)
        usage = usage_ext.value
        digital_signature_present = usage.digital_signature
        digital_signature_only = usage.digital_signature and not any(
            [
                usage.content_commitment,
                usage.key_encipherment,
                usage.data_encipherment,
                usage.key_agreement,
                usage.key_cert_sign,
                usage.crl_sign,
            ]
        )
        key_usage_critical = usage_ext.critical
    except x509.ExtensionNotFound:
        digital_signature_present = False
        digital_signature_only = False
        key_usage_critical = False

    not_before = cert.not_valid_before_utc
    not_after = cert.not_valid_after_utc
    now = _utc_now()
    days_remaining = int((not_after - now).total_seconds() // 86400)
    curve = getattr(getattr(cert.public_key(), "curve", None), "name", "unknown")
    signature_hash = getattr(cert.signature_hash_algorithm, "name", "unknown")

    return CertificateInfo(
        cert_path=cert_path,
        key_path=key_path,
        lfdi=compute_lfdi(cert),
        not_before=not_before,
        not_after=not_after,
        days_remaining=days_remaining,
        is_expired=now >= not_after,
        key_matches=cert_pub == key_pub,
        ieee_policy_present=ieee_policy_present,
        ieee_policy_critical=ieee_policy_critical,
        digital_signature_present=digital_signature_present,
        digital_signature_only=digital_signature_only,
        key_usage_critical=key_usage_critical,
        self_signed=_is_self_signed(cert),
        signature_hash=signature_hash,
        curve=curve,
    )
