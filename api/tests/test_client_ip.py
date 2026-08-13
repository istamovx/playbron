"""`client_ip` — XFF soxtalashga chidamlilik."""

from fastapi import Request

from playbron.core.http import client_ip


def _request(
    headers: dict[str, str] | None = None,
    client: tuple[str, int] | None = ("10.0.0.5", 12345),
) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    scope = {"type": "http", "method": "GET", "path": "/", "headers": raw_headers, "client": client}
    return Request(scope)


def test_no_proxy_returns_peer_ip() -> None:
    assert client_ip(_request()) == "10.0.0.5"


def test_single_forwarded_ip() -> None:
    req = _request({"x-forwarded-for": "203.0.113.7"})
    assert client_ip(req) == "203.0.113.7"


def test_spoofed_left_element_ignored() -> None:
    # Mijoz o'zi yozgan chap element emas, LB qo'shgan o'ng element olinadi
    req = _request({"x-forwarded-for": "1.2.3.4, 203.0.113.7"})
    assert client_ip(req) == "203.0.113.7"


def test_whitespace_stripped() -> None:
    req = _request({"x-forwarded-for": " 1.2.3.4 ,  203.0.113.7 "})
    assert client_ip(req) == "203.0.113.7"


def test_empty_header_falls_back_to_none() -> None:
    req = _request({"x-forwarded-for": "1.2.3.4,"}, client=None)
    assert client_ip(req) is None


def test_no_client_no_header() -> None:
    assert client_ip(_request(client=None)) is None
