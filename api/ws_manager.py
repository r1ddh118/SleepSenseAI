"""WebSocket connections and MQTT → WebSocket relay."""

import asyncio
import json
import logging
import ssl
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from fastapi import WebSocket

from config import settings

logger = logging.getLogger("ws_manager")


class WebSocketManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._mqtt_client: mqtt.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._active_recording_sid: str | None = None
        self._active_csv_path: Path | None = None

    def set_recording_session(self, sid: str | None):
        self._active_recording_sid = sid
        if sid:
            self._active_csv_path = settings.datasets_path / f"compressed_{sid}_whole_df.csv"
            # Initialize CSV if it doesn't exist
            if not self._active_csv_path.exists():
                settings.datasets_path.mkdir(parents=True, exist_ok=True)
                with open(self._active_csv_path, "w") as f:
                    # Added expected columns based on src/data_processor.py + HR 
                    f.write("BVP,ACC_X,ACC_Y,ACC_Z,TEMP,EDA,HR,IBI\n")
            # Take data from cloud ONLY when recording
            if self._mqtt_client:
                self._mqtt_client.subscribe("esp32/heartrate")
                logger.info("Subscribed to esp32/heartrate")
        else:
            self._active_csv_path = None
            if self._mqtt_client:
                self._mqtt_client.unsubscribe("esp32/heartrate")
                logger.info("Unsubscribed from esp32/heartrate")

    def start_mqtt(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        client = mqtt.Client(client_id="ws_relay_backend")
        client.on_message = self._on_mqtt_message
        
        # HiveMQ requires TLS and Auth
        if settings.mqtt_username and settings.mqtt_password:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
            client.tls_set(cert_reqs=ssl.CERT_NONE)
            client.tls_insecure_set(True)

        try:
            client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
            client.loop_start()
            self._mqtt_client = client
            logger.info(f"MQTT relay client connected to {settings.mqtt_broker_host}:{settings.mqtt_broker_port} with TLS")
        except Exception as e:
            logger.error("Failed to connect MQTT: %s", e)

    def stop_mqtt(self):
        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            if msg.topic == "esp32/heartrate":
                payload_str = msg.payload.decode("utf-8")
                data = json.loads(payload_str)
                bpm = float(data.get("bpm", 0.0))
                
                # Mock missing sensors via heuristics so the pipeline doesn't choke completely
                # EDA: 1.0 - 5.0 µS
                # TEMP: 32.0 - 36.0 °C
                # BVP: random fluctuation around standard values
                bvp_val = 20.0 + (bpm % 10)
                acc_x, acc_y, acc_z = 0.5, 0.5, 0.5
                temp_val = 33.0 + (bpm % 2)
                eda_val = 2.0 + (bpm % 3)
                ibi_val = 60000.0 / bpm if bpm > 0 else 0.0
                
                # If we have an active recording session, save to CSV
                if self._active_recording_sid and self._active_csv_path:
                    with open(self._active_csv_path, "a") as f:
                        f.write(f"{bvp_val},{acc_x},{acc_y},{acc_z},{temp_val},{eda_val},{bpm},{ibi_val}\n")
                
                # Broadcast the BPM to all active websockets under the current active sid or any
                if self._loop:
                    for sid in list(self._connections.keys()):
                        ws_payload = json.dumps({
                            "HR": bpm,
                            "EDA": eda_val,
                            "TEMP": temp_val,
                            "BVP": bvp_val,
                            "ts": datetime.utcnow().isoformat()
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
