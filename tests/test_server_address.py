import pytest

from mail_informer.analysis import server_address


@pytest.mark.parametrize("url", [
    "http://localhost:11434/v1",
    "http://LOCALHOST:11434/v1",
    "http://127.0.0.1:11434/v1",
    "http://[::1]:11434/v1",
    "http://host.docker.internal:11434/v1",
    "http://192.168.1.5:8000/v1",
    "http://10.0.0.2/v1",
    "http://172.16.0.1/v1",
    "http://169.254.1.1/v1",
    "http://[fd00::1]/v1",
])
def test_local_addresses(url):
    assert server_address.is_local(url) is True


@pytest.mark.parametrize("url", [
    "https://api.openai.com/v1",
    "http://nas.fritz.box:8000/v1",
    "http://8.8.8.8/v1",
    "http://172.32.0.1/v1",
    "https://localhost.evil.example/v1",
    "api.openai.com/v1",
    "",
])
def test_remote_addresses(url):
    assert server_address.is_local(url) is False


@pytest.mark.parametrize("url", ["http://localhost:11434/v1", "HTTP://192.168.1.5/v1"])
def test_local_http_address_passes(url):
    server_address.check(url, allow_remote=False)


@pytest.mark.parametrize("url", ["https://api.openai.com/v1", "HTTPS://api.openai.com/v1"])
def test_allowed_remote_https_address_passes(url):
    server_address.check(url, allow_remote=True)


def test_remote_address_needs_permission():
    with pytest.raises(ValueError, match="ALLOW_REMOTE_MODEL"):
        server_address.check("https://api.openai.com/v1", allow_remote=False)


def test_remote_address_needs_https():
    with pytest.raises(ValueError, match="https"):
        server_address.check("http://api.openai.com/v1", allow_remote=True)


@pytest.mark.parametrize("url", ["ftp://127.0.0.1/v1", "file://localhost/etc/passwd", "localhost:11434/v1"])
def test_address_must_be_http_or_https(url):
    with pytest.raises(ValueError, match="http"):
        server_address.check(url, allow_remote=True)


def test_error_does_not_repeat_the_address():
    with pytest.raises(ValueError) as error:
        server_address.check("https://user:pw-secret@api.example.com/v1", allow_remote=False)
    assert "pw-secret" not in str(error.value)
