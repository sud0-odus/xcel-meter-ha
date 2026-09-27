from __future__ import annotations

import json
import logging
import os
import ssl
import threading
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import paho.mqtt.client as mqtt

from .certificate import CertificateInfo
from .models import MeterSnapshot
from .mqtt_discovery import (
    MqttDeviceDefinition,
    build_device_definition,
    build_state_payload,
)


LOGGER = logging.getLogger("xcel_meter.mqtt")


@dataclass(frozen=True)
class SupervisorMqttSettings:
    host: str
    port: int
    username: str
    password: str
    ssl_enabled: bool
    protocol: str | None = None


def load_supervisor_mqtt_settings() -> SupervisorMqttSettings:
    token = os.environ.get("SUPERVISOR_TOKEN", "").strip()

    if not token:
        raise RuntimeError(
            "SUPERVISOR_TOKEN is unavailable; "
            "Home Assistant MQTT service cannot be queried"
        )

    request = Request(
        "http://supervisor/services/mqtt",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(
            f"Unable to query Home Assistant MQTT service: {exc}"
        ) from exc

    if isinstance(payload, dict) and "data" in payload:
        data = payload["data"]
    else:
        data = payload

    if not isinstance(data, dict):
        raise RuntimeError(
            "Home Assistant MQTT service returned an unexpected response"
        )

    host = str(data.get("host") or "").strip()
    username = str(data.get("username") or "")
    password = str(data.get("password") or "")

    if not host:
        raise RuntimeError(
            "No Home Assistant MQTT service is available"
        )

    try:
        port = int(data.get("port"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            "Home Assistant MQTT service returned an invalid port"
        ) from exc

    return SupervisorMqttSettings(
        host=host,
        port=port,
        username=username,
        password=password,
        ssl_enabled=bool(data.get("ssl")),
        protocol=(
            str(data["protocol"])
            if data.get("protocol") is not None
            else None
        ),
    )


class MqttPublisher:
    def __init__(
        self,
        settings: SupervisorMqttSettings,
        definition: MqttDeviceDefinition,
        include_received: bool = True,
    ) -> None:
        self.settings = settings
        self.definition = definition
        self.include_received = include_received
        self._connected = threading.Event()

        client_id = (
            "xcel-meter-ha-"
            + definition.discovery_topic.split("/")[-2][-12:]
        )

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )

        if settings.username:
            self._client.username_pw_set(
                settings.username,
                settings.password,
            )

        if settings.ssl_enabled:
            self._client.tls_set(
                cert_reqs=ssl.CERT_REQUIRED,
            )

        self._client.will_set(
            definition.availability_topic,
            payload="offline",
            qos=1,
            retain=True,
        )

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    @classmethod
    def from_snapshot(
        cls,
        snapshot: MeterSnapshot,
        include_received: bool = True,
    ) -> MqttPublisher:
        settings = load_supervisor_mqtt_settings()
        definition = build_device_definition(
            snapshot,
            include_received=include_received,
        )

        return cls(
            settings,
            definition,
            include_received=include_received,
        )

    def _on_connect(
        self,
        client,
        userdata,
        flags,
        reason_code,
        properties,
    ) -> None:
        if reason_code == 0:
            self._connected.set()
            LOGGER.info(
                "MQTT connection: CONNECTED to %s:%s",
                self.settings.host,
                self.settings.port,
            )
        else:
            LOGGER.error(
                "MQTT broker rejected connection: %s",
                reason_code,
            )

    def _on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties,
    ) -> None:
        self._connected.clear()

        if reason_code != 0:
            LOGGER.warning(
                "MQTT connection lost: %s",
                reason_code,
            )

    def connect(self) -> None:
        LOGGER.info(
            "MQTT broker: %s:%s SSL=%s",
            self.settings.host,
            self.settings.port,
            self.settings.ssl_enabled,
        )

        self._client.connect(
            self.settings.host,
            self.settings.port,
            keepalive=60,
        )
        self._client.loop_start()

        if not self._connected.wait(timeout=10):
            self._client.loop_stop()
            raise RuntimeError(
                "Timed out waiting for MQTT broker connection"
            )

    def _publish(
        self,
        topic: str,
        payload: str,
        *,
        retain: bool,
    ) -> None:
        info = self._client.publish(
            topic,
            payload=payload,
            qos=1,
            retain=retain,
        )

        info.wait_for_publish(timeout=10)

        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(
                f"MQTT publish failed for {topic}: rc={info.rc}"
            )

    def publish_discovery(self) -> None:
        if self.definition.removed_components:
            cleanup_payload = dict(
                self.definition.payload
            )
            cleanup_components = dict(
                self.definition.payload["components"]
            )

            for component_id in (
                self.definition.removed_components
            ):
                cleanup_components[component_id] = {
                    "platform": "sensor",
                }

            cleanup_payload["components"] = (
                cleanup_components
            )

            self._publish(
                self.definition.discovery_topic,
                json.dumps(
                    cleanup_payload,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                retain=True,
            )

            LOGGER.info(
                "MQTT discovery cleanup published for: %s",
                ", ".join(
                    self.definition.removed_components
                ),
            )

        self._publish(
            self.definition.discovery_topic,
            json.dumps(
                self.definition.payload,
                separators=(",", ":"),
                sort_keys=True,
            ),
            retain=True,
        )

        component_count = len(
            self.definition.payload["components"]
        )

        LOGGER.info(
            "MQTT discovery published: %s Home Assistant entities",
            component_count,
        )

    def publish_snapshot(
        self,
        snapshot: MeterSnapshot,
        certificate_info: CertificateInfo | None = None,
    ) -> None:
        self._publish(
            self.definition.state_topic,
            json.dumps(
                build_state_payload(
                    snapshot,
                    include_received=self.include_received,
                    certificate_info=certificate_info,
                ),
                separators=(",", ":"),
                sort_keys=True,
            ),
            retain=True,
        )

        self._publish(
            self.definition.availability_topic,
            "online",
            retain=True,
        )

        self._publish(
            self.definition.meter_availability_topic,
            "online",
            retain=True,
        )

        self._publish(
            self.definition.health_topic,
            "Healthy",
            retain=True,
        )

        if self.include_received:
            LOGGER.info(
                "MQTT state published: power=%s W delivered=%s Wh "
                "received=%s Wh",
                snapshot.instantaneous_power_w,
                snapshot.energy_delivered_wh,
                snapshot.energy_received_wh,
            )
        else:
            LOGGER.info(
                "MQTT state published: power=%s W delivered=%s Wh",
                snapshot.instantaneous_power_w,
                snapshot.energy_delivered_wh,
            )

    def publish_meter_problem(self) -> None:
        """Mark meter data unavailable without marking the app offline."""
        if not self._connected.is_set():
            return

        self._publish(
            self.definition.health_topic,
            "Problem",
            retain=True,
        )

        self._publish(
            self.definition.meter_availability_topic,
            "offline",
            retain=True,
        )

        LOGGER.warning(
            "MQTT meter status published: Problem"
        )

    def publish_offline(self) -> None:
        if not self._connected.is_set():
            return

        try:
            self._publish(
                self.definition.availability_topic,
                "offline",
                retain=True,
            )
        except RuntimeError:
            LOGGER.warning(
                "Unable to publish MQTT offline availability"
            )

    def close(self) -> None:
        self.publish_offline()
        self._client.disconnect()
        self._client.loop_stop()
