from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def validate_url(url: str, allow_private_networks: bool = False) -> str:
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"Missing host in URL: {url}")

    if not allow_private_networks:
        _check_not_private(hostname)

    return url


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    normalized = (
        f"{parsed.scheme}://{parsed.hostname}"
        + (f":{parsed.port}" if parsed.port else "")
        + (parsed.path.rstrip("/") or "/")
        + (f"?{parsed.query}" if parsed.query else "")
    )
    return normalized


def _check_not_private(hostname: str) -> None:
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local:
            raise ValueError(f"Private/internal IP not allowed: {hostname}")
        return
    except ValueError:
        pass

    try:
        resolved = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in resolved:
            ip = sockaddr[0]
            addr = ipaddress.ip_address(ip)
            if addr.is_private or addr.is_loopback or addr.is_link_local:
                raise ValueError(
                    f"Host {hostname} resolves to private IP {ip}; "
                    f"not allowed by discovery policy"
                )
    except socket.gaierror:
        raise ValueError(f"Cannot resolve hostname: {hostname}") from None
