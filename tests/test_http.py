import ssl

from xcel_meter.http import _is_transient_bad_signature, parse_http_response


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
