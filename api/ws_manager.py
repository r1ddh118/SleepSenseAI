"""WebSocket connections and ThingSpeak → WebSocket relay."""

import asyncio
import json
import logging
import pickle
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd
from fastapi import WebSocket

from config import settings

logger = logging.getLogger("ws_manager")


class WebSocketManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._active_recording_sid: str | None = None
        self._active_csv_path: Path | None = None
        self._thingspeak_task: asyncio.Task | None = None
        self._last_feed_timestamp: str | None = None
        self._imputer = None

        imputer_path = settings.artifacts_path / "sensor_imputer.pkl"
        try:
            if imputer_path.exists():
                with open(imputer_path, "rb") as f:
                    self._imputer = pickle.load(f)
                logger.info("Loaded sensor imputer ML model")
        except Exception as e:
            logger.warning("Could not load imputer model: %s", e)

    def _predict_from_bpm(self, bpm: float) -> tuple[float, float, float]:
        """Predict EDA/TEMP/BVP from HR(BPM) using the trained imputer model."""
        if self._imputer is None:
            return 0.0, 0.0, 0.0
        try:
            preds = self._imputer.predict(pd.DataFrame({"HR": [bpm]}))
            return float(preds[0][0]), float(preds[0][1]), float(preds[0][2])
        except Exception as e:
            logger.error("HR-only imputation failed: %s", e)
            return 0.0, 0.0, 0.0

    def start_streaming(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        logger.info("ThingSpeak relay ready")

    def stop_streaming(self):
        if self._thingspeak_task and not self._thingspeak_task.done():
            self._thingspeak_task.cancel()

    def set_recording_session(self, sid: str | None):
        self._active_recording_sid = sid
        self._last_feed_timestamp = None

        if self._thingspeak_task and not self._thingspeak_task.done():
            self._thingspeak_task.cancel()
            self._thingspeak_task = None

        if sid:
            self._active_csv_path = settings.datasets_path / f"compressed_{sid}_whole_df.csv"
            if not self._active_csv_path.exists():
                settings.datasets_path.mkdir(parents=True, exist_ok=True)
                with open(self._active_csv_path, "w", encoding="utf-8") as f:
                    f.write(
                        "BVP,ACC_X,ACC_Y,ACC_Z,TEMP,EDA,HR,IBI,"
                        "EDA_raw,TEMP_raw,BVP_raw,imputed_from_hr\n"
                    )

            if self._loop:
                self._thingspeak_task = self._loop.create_task(self._poll_thingspeak(sid))
                logger.info("Started ThingSpeak polling for session %s", sid)
        else:
            self._active_csv_path = None
            logger.info("Stopped ThingSpeak polling")

    async def _poll_thingspeak(self, sid: str):
        while self._active_recording_sid == sid:
            try:
                payload = await asyncio.to_thread(self._fetch_latest_feed)
                if payload:
                    await self._handle_feed(sid, payload)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("ThingSpeak polling error: %s", e)

            await asyncio.sleep(max(1, settings.thingspeak_poll_seconds))

    def _fetch_latest_feed(self) -> dict | None:
        if not settings.thingspeak_channel_id:
            logger.warning("ThingSpeak channel is not configured")
            return None

        params = {"results": 1}
        if settings.thingspeak_read_api_key:
            params["api_key"] = settings.thingspeak_read_api_key

        url = (
            f"https://api.thingspeak.com/channels/{settings.thingspeak_channel_id}/feeds.json?"
            f"{urlencode(params)}"
        )

        try:
            with urlopen(url, timeout=10) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
                feeds = data.get("feeds") or []
                if not feeds:
                    return None
                return feeds[-1]
        except URLError as e:
            logger.warning("ThingSpeak request failed: %s", e)
            return None

    async def _handle_feed(self, sid: str, feed: dict):
        feed_ts = feed.get("created_at")
        if not feed_ts or feed_ts == self._last_feed_timestamp:
            return
        self._last_feed_timestamp = feed_ts

        bpm = float(feed.get(settings.thingspeak_hr_field, 0.0) or 0.0)
        eda_raw = float(feed.get(settings.thingspeak_eda_field, 0.0) or 0.0)
        temp_raw = float(feed.get(settings.thingspeak_temp_field, 0.0) or 0.0)
        bvp_raw = float(feed.get(settings.thingspeak_bvp_field, 0.0) or 0.0)

        # HR(BPM)-only real-time prediction path.
        pred_eda, pred_temp, pred_bvp = self._predict_from_bpm(bpm) if bpm > 0 else (0.0, 0.0, 0.0)

        # Store predicted values in core columns so downstream processing always has EDA/TEMP/BVP.
        # If model is unavailable, gracefully fall back to raw values from ThingSpeak.
        eda_val = pred_eda if pred_eda != 0.0 else eda_raw
        temp_val = pred_temp if pred_temp != 0.0 else temp_raw
        bvp_val = pred_bvp if pred_bvp != 0.0 else bvp_raw
        imputed_from_hr = int(pred_eda != 0.0 and pred_temp != 0.0 and pred_bvp != 0.0)

        acc_x, acc_y, acc_z = 0.5, 0.5, 0.5
        ibi_val = 60000.0 / bpm if bpm > 0 else 0.0

        if self._active_recording_sid == sid and self._active_csv_path:
            with open(self._active_csv_path, "a", encoding="utf-8") as f:
                f.write(
                    f"{bvp_val},{acc_x},{acc_y},{acc_z},{temp_val},{eda_val},{bpm},{ibi_val},"
                    f"{eda_raw},{temp_raw},{bvp_raw},{imputed_from_hr}\n"
                )

        ws_payload = json.dumps(
            {
                "HR": bpm,
                "EDA": eda_val,
                "TEMP": temp_val,
                "BVP": bvp_val,
                "ts": feed_ts,
                "source": "thingspeak",
            }
        )
        await self._broadcast(sid, ws_payload)

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
