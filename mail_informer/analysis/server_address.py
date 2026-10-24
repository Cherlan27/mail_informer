"""Rule for which model server may receive mail text. Pure functions, no I/O.

The decision uses the address text only. It makes no DNS lookup, because the
answer of a lookup can change between the check and the request.
"""

import ipaddress
from urllib.parse import urlparse

LOCAL_HOSTS = ("localhost", "host.docker.internal")
SCHEMES = ("http", "https")


def is_local(url: str) -> bool:
    """Tells if a model server address is on this machine or in a private network.

    Args:
        url: Base address of the model server.

    Returns:
        True for ``localhost``, ``host.docker.internal``, and IP addresses that are
        loopback, private, or link-local. False for every other host name or address.
    """
    host = urlparse(url).hostname or ""
    if host in LOCAL_HOSTS:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private or ip.is_link_local


def check(url: str, allow_remote: bool) -> None:
    """Checks that mail text may be sent to a model server address.

    The messages do not repeat the address: it may hold a user name and password.

    Args:
        url: Base address of the model server.
        allow_remote: If True, an address outside this machine and network is allowed.

    Raises:
        ValueError: If the address does not use http or https, is remote without
            permission, or is remote without https.
    """
    scheme = urlparse(url).scheme.lower()
    if scheme not in SCHEMES:
        raise ValueError("the address must start with http:// or https://")
    if is_local(url):
        return
    if not allow_remote:
        raise ValueError("it is not a local address, so mail text would leave this network. "
                         "Set ALLOW_REMOTE_MODEL=true to allow it")
    if scheme != "https":
        raise ValueError("a remote address must start with https://")
