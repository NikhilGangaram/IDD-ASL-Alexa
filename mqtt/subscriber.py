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
    """Subscribes to MQTT topic and manages gesture commands and button states"""
    
    def __init__(self, socketio=None):
        self.mqtt_client = None
        self.socketio = socketio
        self.button_states = {
            'A': False,
            'B': False
        }
        # Gesture command state
        self.current_mode = None
        self.gesture_states = {
            'TEMPERATURE': None,
            'LIGHTS': None,
            'BLINDS': None,
            'DOOR': None
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
            
            # Handle gesture commands
            if data.get('type') == 'gesture_command':
                category = data.get('category')
                action = data.get('action')
                value = data.get('value')
                timestamp = data.get('timestamp', datetime.now().strftime('%H:%M:%S'))
                
                if category and action and value:
                    # Update current mode if it's a mode change
                    if category in ['TEMPERATURE', 'LIGHTS', 'BLINDS', 'DOOR']:
                        self.current_mode = category
                    
                    # Update gesture state
                    if action in self.gesture_states:
                        self.gesture_states[action] = value
                    
                    print(f"[{timestamp}] Gesture Command: {category} -> {action} = {value}")
                    
                    # Add to activity history
                    self.add_gesture_to_history(category, action, value, timestamp)
                    
                    # Broadcast to web clients if available
                    if self.socketio:
                        self.socketio.emit('gesture_command', {
                            'category': category,
                            'action': action,
                            'value': value,
                            'timestamp': timestamp
                        })
                        self.socketio.emit('current_mode', {'mode': self.current_mode})
                        self.socketio.emit('gesture_states', self.gesture_states.copy())
                
                return
            
            # Handle legacy button states (for backward compatibility)
            button_id = data.get('button_id')
            state = data.get('state', False)
            
            # Validate button_id
            if button_id not in ['A', 'B']:
                print(f'[WARN] Unknown message type: {data.get("type", "unknown")}')
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
        """Add button event to activity history"""
        activity_item = {
            'type': 'button',
            'button_id': button_id,
            'state': state_str,
            'timestamp': timestamp
        }
        self.activity_history.insert(0, activity_item)
        if len(self.activity_history) > self.max_history:
            self.activity_history.pop()
    
    def add_gesture_to_history(self, category, action, value, timestamp):
        """Add gesture command to activity history"""
        activity_item = {
            'type': 'gesture',
            'category': category,
            'action': action,
            'value': value,
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
    
    def get_gesture_states(self):
        """Get current gesture states"""
        return self.gesture_states.copy()
    
    def get_current_mode(self):
        """Get current mode"""
        return self.current_mode
    
    def get_history(self):
        """Get activity history"""
        return self.activity_history.copy()
    
    def cleanup(self):
        """Cleanup resources"""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

