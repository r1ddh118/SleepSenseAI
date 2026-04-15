"""
Phase 1 — E4 live streaming (stub).

Streams Empatica E4 data to a local CSV (e.g. datasets/live_{session_id}.csv) and to MQTT
for the API WebSocket relay. See PHASE_1_HARDWARE.md for the full specification.
"""

def main():
    raise NotImplementedError(
        "Implement e4_streamer per PHASE_1_HARDWARE.md — "
        "write CSV under datasets/ and publish to sleepsense/{sid}/<stream>."
    )


if __name__ == "__main__":
    main()
