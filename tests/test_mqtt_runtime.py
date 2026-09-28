from urllib.error import HTTPError

import json

import pytest

from xcel_meter import mqtt_runtime


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_load_supervisor_mqtt_settings(monkeypatch):
    monkeypatch.setenv(
        "SUPERVISOR_TOKEN",
        "test-token",
    )

    payload = {
        "data": {
            "host": "core-mosquitto",
            "port": 1883,
            "username": "addons",
            "password": "secret",
            "ssl": False,
            "protocol": "mqtt",
        }
    }

    monkeypatch.setattr(
        mqtt_runtime,
        "urlopen",
        lambda request, timeout: FakeResponse(payload),
    )

    settings = mqtt_runtime.load_supervisor_mqtt_settings()

    assert settings.host == "core-mosquitto"
    assert settings.port == 1883
    assert settings.username == "addons"
    assert settings.password == "secret"
    assert settings.ssl_enabled is False
    assert settings.protocol == "mqtt"


def test_load_supervisor_mqtt_settings_requires_token(
    monkeypatch,
):
    monkeypatch.delenv(
        "SUPERVISOR_TOKEN",
        raising=False,
    )

    with pytest.raises(
        RuntimeError,
        match="SUPERVISOR_TOKEN",
    ):
        mqtt_runtime.load_supervisor_mqtt_settings()


def test_load_supervisor_mqtt_settings_requires_host(
    monkeypatch,
):
    monkeypatch.setenv(
        "SUPERVISOR_TOKEN",
        "test-token",
    )

    payload = {
        "data": {
            "port": 1883,
            "username": "addons",
            "password": "secret",
            "ssl": False,
        }
    }

    monkeypatch.setattr(
        mqtt_runtime,
        "urlopen",
        lambda request, timeout: FakeResponse(payload),
    )

    with pytest.raises(
        RuntimeError,
        match="No Home Assistant MQTT service",
    ):
        mqtt_runtime.load_supervisor_mqtt_settings()


def test_supervisor_http_error_is_temporary_mqtt_unavailable(
    monkeypatch,
):
    monkeypatch.setenv(
        "SUPERVISOR_TOKEN",
        "test-token",
    )

    def fail_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            400,
            "Bad Request",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(
        mqtt_runtime,
        "urlopen",
        fail_urlopen,
    )

    with pytest.raises(
        mqtt_runtime.MqttUnavailableError,
        match="MQTT service is not ready",
    ):
        mqtt_runtime.load_supervisor_mqtt_settings()

def test_supervisor_auth_http_error_is_not_temporary(
    monkeypatch,
):
    monkeypatch.setenv(
        "SUPERVISOR_TOKEN",
        "test-token",
    )

    def fail_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(
        mqtt_runtime,
        "urlopen",
        fail_urlopen,
    )

    with pytest.raises(
        RuntimeError,
        match="HTTP 401 Unauthorized",
    ) as exc_info:
        mqtt_runtime.load_supervisor_mqtt_settings()

    assert not isinstance(
        exc_info.value,
        mqtt_runtime.MqttUnavailableError,
    )
