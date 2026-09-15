"""WebSocket connections. MQTT relay is optional — only active when paho-mqtt is installed
and hardware mode is enabled. Import 'requirements-hardware.txt' to enable the MQTT path."""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
    import ssl as _ssl
    _PAHO_AVAILABLE = True
except ImportError:
    mqtt = None  # type: ignore[assignment]
    _ssl = None  # type: ignore[assignment]
    _PAHO_AVAILABLE = False

from fastapi import WebSocket

from config import settings

logger = logging.getLogger("ws_manager")


class WebSocketManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._mqtt_client = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._active_recording_sid: str | None = None
        self._active_csv_path: Path | None = None

    def set_recording_session(self, sid: str | None):
        self._active_recording_sid = sid
        if sid:
            self._active_csv_path = settings.datasets_path / f"compressed_{sid}_whole_df.csv"
            if not self._active_csv_path.exists():
                settings.datasets_path.mkdir(parents=True, exist_ok=True)
                with open(self._active_csv_path, "w") as f:
                    f.write("BVP,ACC_X,ACC_Y,ACC_Z,TEMP,EDA,HR,IBI\n")
            if self._mqtt_client and _PAHO_AVAILABLE:
                self._mqtt_client.subscribe("esp32/heartrate")
                logger.info("Subscribed to esp32/heartrate")
        else:
            self._active_csv_path = None
            if self._mqtt_client and _PAHO_AVAILABLE:
                self._mqtt_client.unsubscribe("esp32/heartrate")
                logger.info("Unsubscribed from esp32/heartrate")

    def start_mqtt(self, loop: asyncio.AbstractEventLoop):
        """Start MQTT relay — only works when paho-mqtt is installed (requirements-hardware.txt)."""
        if not _PAHO_AVAILABLE:
            logger.info("paho-mqtt not installed; MQTT relay disabled (hardware mode off)")
            return

        self._loop = loop
        client = mqtt.Client(client_id="ws_relay_backend")
        client.on_message = self._on_mqtt_message

        if settings.mqtt_username and settings.mqtt_password:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
            client.tls_set(cert_reqs=_ssl.CERT_NONE)
            client.tls_insecure_set(True)

        try:
            client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
            client.loop_start()
            self._mqtt_client = client
            logger.info(
                "MQTT relay connected to %s:%s",
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
            )
        except Exception as e:
            logger.error("Failed to connect MQTT: %s", e)

    def stop_mqtt(self):
        if self._mqtt_client and _PAHO_AVAILABLE:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()

    def _on_mqtt_message(self, client, userdata, msg):
        if not _PAHO_AVAILABLE:
            return
        try:
            if msg.topic == "esp32/heartrate":
                data = json.loads(msg.payload.decode("utf-8"))
                bpm = float(data.get("bpm", 0.0))

                bvp_val = 20.0 + (bpm % 10)
                acc_x, acc_y, acc_z = 0.5, 0.5, 0.5
                temp_val = 33.0 + (bpm % 2)
                eda_val = 2.0 + (bpm % 3)
                ibi_val = 60000.0 / bpm if bpm > 0 else 0.0

                if self._active_recording_sid and self._active_csv_path:
                    with open(self._active_csv_path, "a") as f:
                        f.write(f"{bvp_val},{acc_x},{acc_y},{acc_z},{temp_val},{eda_val},{bpm},{ibi_val}\n")

                if self._loop:
                    for sid in list(self._connections.keys()):
                        ws_payload = json.dumps({
                            "HR": bpm,
                            "EDA": eda_val,
                            "TEMP": temp_val,
                            "BVP": bvp_val,
                            "ts": datetime.utcnow().isoformat(),
                        })
                        asyncio.run_coroutine_threadsafe(
                            self._broadcast(sid, ws_payload),
                            self._loop,
                        )
        except Exception as e:
            logger.error("MQTT relay error: %s", e)

    async def _broadcast(self, sid: str, message: str):
        disconnected = set()
        for ws in self._connections.get(sid, []):
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)
        self._connections[sid] -= disconnected

    async def connect(self, sid: str, websocket: WebSocket):
        await websocket.accept()
        self._connections[sid].add(websocket)

    async def disconnect(self, sid: str, websocket: WebSocket):
        self._connections[sid].discard(websocket)


ws_manager = WebSocketManager()
