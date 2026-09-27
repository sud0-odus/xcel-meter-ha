from xcel_meter.http import parse_http_response


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
