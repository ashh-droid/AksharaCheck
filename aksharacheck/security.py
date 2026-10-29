"""Conservative network controls for user-supplied URLs."""
import ipaddress
import socket
from urllib.parse import urlsplit

ALLOWED_SCHEMES = {"http", "https"}
LOCAL_HOSTS = {"localhost", "localhost.localdomain", "127.0.0.1", "::1"}

class UnsafeURL(ValueError):
    pass


def validate_url(url: str, *, allow_local: bool = False) -> str:
    """Block credentials, unexpected ports and non-public addresses, including DNS answers."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise UnsafeURL("Malformed URL") from exc
    if parsed.scheme not in ALLOWED_SCHEMES or not host:
        raise UnsafeURL("Only HTTP(S) URLs with a hostname are allowed")
    if parsed.username or parsed.password:
        raise UnsafeURL("Credentials in URLs are not allowed")
    if port not in {None, 80, 443} and not (allow_local and host in LOCAL_HOSTS):
        raise UnsafeURL("Non-standard ports are disabled")
    if host in LOCAL_HOSTS and allow_local:
        return url
    if host in LOCAL_HOSTS or host.endswith((".local", ".internal", ".localhost")):
        raise UnsafeURL("Local hostnames are blocked")
    try:
        infos = socket.getaddrinfo(host, port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as exc:
        raise UnsafeURL("Hostname could not be resolved") from exc
    if not infos:
        raise UnsafeURL("Hostname has no IP addresses")
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if not addr.is_global:
            raise UnsafeURL("Private, reserved or metadata IP addresses are blocked")
    return url
