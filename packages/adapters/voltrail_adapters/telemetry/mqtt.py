import json
import paho.mqtt.client as mqtt
from typing import Callable, Optional
from voltrail_core.models import Coordinate
from voltrail_core.telemetry.protocols import TelemetrySubscriber, TelemetryMessage

class MQTTTelemetrySubscriber(TelemetrySubscriber):
    def __init__(self, broker_host: str, broker_port: int = 1883, topic: str = "voltrail/telemetry/#"):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topic = topic
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._callback: Optional[Callable[[TelemetryMessage], None]] = None
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_mqtt_message

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"Connected to MQTT Broker at {self.broker_host}:{self.broker_port}")
            self.client.subscribe(self.topic)
        else:
            print(f"Failed to connect, return code {reason_code}")

    def _on_mqtt_message(self, client, userdata, msg):
        if not self._callback:
            return
            
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            telemetry = TelemetryMessage(
                vehicle_id=payload["vehicle_id"],
                location=Coordinate(payload["lat"], payload["lon"]),
                speed_mps=payload.get("speed_mps", 0.0),
                soc_pct=payload["soc_pct"],
                ambient_temp_c=payload.get("ambient_temp_c", 25.0),
                instant_power_kw=payload.get("instant_power_kw", 0.0),
                timestamp=payload.get("timestamp", 0.0)
            )
            self._callback(telemetry)
        except Exception as e:
            print(f"Failed to parse telemetry message: {e}")

    def connect(self) -> None:
        self.client.connect(self.broker_host, self.broker_port, 60)
        self.client.loop_start()

    def disconnect(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def on_message(self, callback: Callable[[TelemetryMessage], None]) -> None:
        self._callback = callback
