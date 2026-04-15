"""WebSocket connections and MQTT → WebSocket relay."""

import asyncio
import logging
from collections import defaultdict

import paho.mqtt.client as mqtt
from fastapi import WebSocket

from config import settings

logger = logging.getLogger("ws_manager")


class WebSocketManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._mqtt_client: mqtt.Client | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start_mqtt(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        client = mqtt.Client(client_id="ws_relay")
        client.on_message = self._on_mqtt_message
        client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
        client.loop_start()
        self._mqtt_client = client
        logger.info("MQTT relay client connected")

    def stop_mqtt(self):
        if self._mqtt_client:
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            parts = msg.topic.split("/")
            if len(parts) < 3:
                return
            sid = parts[1]
            payload = msg.payload.decode("utf-8")

            if sid in self._connections and self._connections[sid] and self._loop:
                asyncio.run_coroutine_threadsafe(
                    self._broadcast(sid, payload),
                    self._loop,
                )
        except Exception as e:
            logger.error("MQTT → WS relay error: %s", e)

    async def _broadcast(self, sid: str, message: str):
        disconnected = set()
        for ws in self._connections[sid]:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.add(ws)
        self._connections[sid] -= disconnected

    async def connect(self, sid: str, websocket: WebSocket):
        await websocket.accept()
        self._connections[sid].add(websocket)

        if len(self._connections[sid]) == 1 and self._mqtt_client:
            self._mqtt_client.subscribe(f"sleepsense/{sid}/#")
            logger.info("MQTT subscribed: sleepsense/%s/#", sid)

    async def disconnect(self, sid: str, websocket: WebSocket):
        self._connections[sid].discard(websocket)

        if not self._connections[sid] and self._mqtt_client:
            self._mqtt_client.unsubscribe(f"sleepsense/{sid}/#")
            logger.info("MQTT unsubscribed: sleepsense/%s/#", sid)


ws_manager = WebSocketManager()
