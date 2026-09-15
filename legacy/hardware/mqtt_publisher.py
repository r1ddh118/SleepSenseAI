"""MQTT publishing helpers for hardware data streams."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt


@dataclass
class MQTTPublisher:
    host: str = "localhost"
    port: int = 1883
    keepalive: int = 60
    client_id: str = "sleepsense_hardware"

    def __post_init__(self) -> None:
        self._client = mqtt.Client(client_id=self.client_id)
        self._connected = False

    def connect(self) -> None:
        if self._connected:
            return
        self._client.connect(self.host, self.port, self.keepalive)
        self._client.loop_start()
        self._connected = True

    def publish(self, topic: str, payload: str | bytes, qos: int = 0, retain: bool = False) -> None:
        if not self._connected:
            self.connect()
        result = self._client.publish(topic, payload=payload, qos=qos, retain=retain)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Failed to publish to {topic}: MQTT rc={result.rc}")

    def publish_json(self, topic: str, payload: dict[str, Any], qos: int = 0) -> None:
        self.publish(topic, json.dumps(payload), qos=qos)

    def close(self) -> None:
        if self._connected:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False


_default_publisher = MQTTPublisher()


def publish_sample(topic: str, payload: str) -> None:
    """Backward-compatible helper used by early Phase 1 streamer code."""
    _default_publisher.publish(topic, payload)
