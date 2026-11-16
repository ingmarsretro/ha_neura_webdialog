"""Blocking MQTT publish compatible with php-mqtt (QoS 0, retain false)."""

from __future__ import annotations

import time


def publish_messages(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    client_id: str,
    messages: list[tuple[str, str]],
) -> None:
    """Publish all payloads on one connection, then disconnect."""

    if not messages:
        return

    import paho.mqtt.client as mqtt
    import paho.mqtt.publish as mqtt_publish

    auth = None
    if username:
        auth = {"username": username, "password": password}
    mqtt_publish.multiple(
        [
            {"topic": topic, "payload": payload, "qos": 0, "retain": False}
            for topic, payload in messages
        ],
        hostname=host,
        port=int(port),
        client_id=client_id or "neura",
        keepalive=30,
        auth=auth,
        protocol=mqtt.MQTTv311,
    )


def check_connection(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    client_id: str,
) -> None:
    """Open a short MQTT session. Raises if the broker cannot be reached."""

    import paho.mqtt.client as mqtt

    result: dict[str, int] = {}
    callback_api = getattr(mqtt, "CallbackAPIVersion", None)
    if callback_api is not None:
        client = mqtt.Client(
            callback_api.VERSION1,
            client_id=client_id or "neura",
            protocol=mqtt.MQTTv311,
        )
    else:
        client = mqtt.Client(client_id=client_id or "neura", protocol=mqtt.MQTTv311)

    def _on_connect(unused_client, unused_userdata, unused_flags, reason_code, unused_properties=None):
        result["rc"] = int(getattr(reason_code, "value", reason_code))

    client.on_connect = _on_connect
    if username:
        client.username_pw_set(username, password or None)
    client.connect(host, int(port), keepalive=10)
    client.loop_start()
    try:
        deadline = time.monotonic() + 8
        while "rc" not in result and time.monotonic() < deadline:
            time.sleep(0.1)
    finally:
        client.loop_stop()
        try:
            client.disconnect()
        except Exception:
            pass
    if "rc" not in result:
        raise TimeoutError(f"MQTT timeout for {host}:{port}")
    if result["rc"] != 0:
        raise ConnectionError(f"MQTT connection refused ({result['rc']})")
