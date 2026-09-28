import ssl

from xcel_meter.http import (
    IEEE2030_5_ACCEPT,
    IEEE2030_5_TLS_CIPHER,
    _is_transient_bad_signature,
    _is_transient_handshake_timeout,
    parse_http_response,
)


def test_parse_content_length_response():
    response = parse_http_response(
        b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nhelloignored",
        "cipher",
    )
    assert response.status == 200
    assert response.body == b"hello"
    assert response.cipher == "cipher"


def test_parse_chunked_response():
    response = parse_http_response(
        b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n5\r\nhello\r\n6\r\n world\r\n0\r\n\r\n"
    )
    assert response.body == b"hello world"


def test_bad_signature_is_transient_retry_candidate():
    error = ssl.SSLError(
        1,
        "[SSL: BAD_SIGNATURE] bad signature (_ssl.c:1082)",
    )

    assert _is_transient_bad_signature(error)


def test_other_ssl_error_is_not_bad_signature():
    error = ssl.SSLError(
        1,
        "[SSL: BAD_CERTIFICATE] bad certificate (_ssl.c:1082)",
    )

    assert not _is_transient_bad_signature(error)


def test_handshake_timeout_is_transient_retry_candidate():
    error = TimeoutError(
        "_ssl.c:1064: The handshake operation timed out"
    )

    assert _is_transient_handshake_timeout(error)


def test_normal_connection_error_is_not_handshake_timeout():
    error = ConnectionRefusedError(
        "Connection refused"
    )

    assert not _is_transient_handshake_timeout(error)


def test_sdk_aligned_http_and_tls_constants():
    assert IEEE2030_5_ACCEPT == "application/sep+xml;level=-S1"
    assert IEEE2030_5_TLS_CIPHER == "ECDHE-ECDSA-AES128-CCM8:@SECLEVEL=0"
