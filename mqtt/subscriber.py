"""
MQTT Subscriber - Receives and processes button state messages

Handles MQTT message reception and state management for the web dashboard.
"""

import paho.mqtt.client as mqtt
import json
import uuid
from datetime import datetime
from .config import MQTTConfig


class ButtonSubscriber:
    """Subscribes to MQTT topic and manages button states"""
    
    def __init__(self, socketio=None):
        self.mqtt_client = None
        self.socketio = socketio
        self.button_states = {
            'A': False,
            'B': False
        }
        self.activity_history = []
        self.max_history = 20
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            print(f'[OK] MQTT connected to {MQTTConfig.BROKER}:{MQTTConfig.PORT}')
            client.subscribe(MQTTConfig.TOPIC)
            print(f'[OK] Subscribed to {MQTTConfig.TOPIC}')
            if self.socketio:
                self.socketio.emit('mqtt_status', {'connected': True})
        else:
            print(f'[FAIL] MQTT connection failed: {rc}')
            if self.socketio:
                self.socketio.emit('mqtt_status', {'connected': False})
    
    def on_message(self, client, userdata, msg):
        """MQTT message received - update state and broadcast to web clients"""
        try:
            data = json.loads(msg.payload.decode('UTF-8'))
            button_id = data.get('button_id')
            state = data.get('state', False)
            
            # Validate button_id
            if button_id not in ['A', 'B']:
                print(f'[WARN] Unknown button_id: {button_id}')
                return
            
            # Update state
            old_state = self.button_states[button_id]
            self.button_states[button_id] = state
            
            # Only process if state changed
            if old_state != state:
                timestamp = datetime.now().strftime('%H:%M:%S')
                state_str = "PRESSED" if state else "RELEASED"
                
                print(f"[{timestamp}] Button {button_id}: {state_str}")
                
                # Add to activity history
                self.add_to_history(button_id, state_str, timestamp)
                
                # Broadcast to web clients if available
                if self.socketio:
                    self.socketio.emit('button_update', {
                        'button_id': button_id,
                        'state': state,
                        'state_str': state_str,
                        'timestamp': timestamp
                    })
                    self.socketio.emit('button_states', self.button_states.copy())
        
        except json.JSONDecodeError as e:
            print(f'[WARN] Failed to parse JSON: {e}')
        except Exception as e:
            print(f'[WARN] Error processing message: {e}')
    
    def add_to_history(self, button_id, state_str, timestamp):
        """Add event to activity history"""
        activity_item = {
            'button_id': button_id,
            'state': state_str,
            'timestamp': timestamp
        }
        self.activity_history.insert(0, activity_item)
        if len(self.activity_history) > self.max_history:
            self.activity_history.pop()
    
    def setup(self):
        """Setup and connect MQTT client"""
        try:
            client_id = f"{MQTTConfig.CLIENT_ID_PREFIX}-sub-{str(uuid.uuid1())}"
            self.mqtt_client = mqtt.Client(client_id)
            
            if MQTTConfig.USERNAME and MQTTConfig.PASSWORD:
                self.mqtt_client.username_pw_set(MQTTConfig.USERNAME, MQTTConfig.PASSWORD)
            
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_message = self.on_message
            
            self.mqtt_client.connect(MQTTConfig.BROKER, port=MQTTConfig.PORT, keepalive=MQTTConfig.KEEPALIVE)
            self.mqtt_client.loop_start()
            
            import time
            time.sleep(1)
            return True
        except Exception as e:
            print(f'[WARN] MQTT setup failed: {e}')
            return False
    
    def get_states(self):
        """Get current button states"""
        return self.button_states.copy()
    
    def get_history(self):
        """Get activity history"""
        return self.activity_history.copy()
    
    def cleanup(self):
        """Cleanup resources"""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

