"""
MQTT Publisher - Raspberry Pi Button State Publisher

Reads button states from MiniPiTFT buttons and publishes to MQTT when state changes.
"""

import time
import digitalio
import board
import paho.mqtt.client as mqtt
import json
import uuid
from .config import MQTTConfig, ButtonConfig


class ButtonPublisher:
    """Publishes button state changes to MQTT"""
    
    def __init__(self):
        self.mqtt_client = None
        self.button_a = None
        self.button_b = None
        self.prev_button_a_state = None
        self.prev_button_b_state = None
        
    def setup_buttons(self):
        """Setup button pins"""
        try:
            # Use board attributes directly (D23, D24)
            self.button_a = digitalio.DigitalInOut(board.D23)
            self.button_b = digitalio.DigitalInOut(board.D24)
            self.button_a.switch_to_input(pull=digitalio.Pull.UP)
            self.button_b.switch_to_input(pull=digitalio.Pull.UP)
            return True
        except Exception as e:
            print(f"[FAIL] Button setup failed: {e}")
            return False
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            print(f'[OK] MQTT connected to {MQTTConfig.BROKER}:{MQTTConfig.PORT}')
            print(f'[OK] Publishing to {MQTTConfig.TOPIC}')
        else:
            print(f'[FAIL] MQTT connection failed: {rc}')
    
    def on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        pass
    
    def setup_mqtt(self):
        """Setup and connect MQTT client"""
        try:
            client_id = f"{MQTTConfig.CLIENT_ID_PREFIX}-{str(uuid.uuid1())}"
            self.mqtt_client = mqtt.Client(client_id)
            
            if MQTTConfig.USERNAME and MQTTConfig.PASSWORD:
                self.mqtt_client.username_pw_set(MQTTConfig.USERNAME, MQTTConfig.PASSWORD)
            
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_publish = self.on_publish
            
            self.mqtt_client.connect(MQTTConfig.BROKER, port=MQTTConfig.PORT, keepalive=MQTTConfig.KEEPALIVE)
            self.mqtt_client.loop_start()
            
            time.sleep(1)
            return True
        except Exception as e:
            print(f'[WARN] MQTT setup failed: {e}')
            return False
    
    def publish_button_state(self, button_id, state):
        """Publish button state to MQTT"""
        payload = {
            'button_id': button_id,
            'state': state
        }
        result = self.mqtt_client.publish(MQTTConfig.TOPIC, json.dumps(payload))
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            state_str = "PRESSED" if state else "RELEASED"
            print(f"[{time.strftime('%H:%M:%S')}] Button {button_id}: {state_str}")
            return True
        else:
            print(f"[ERROR] Failed to publish Button {button_id} state: rc={result.rc}")
            return False
    
    def run(self):
        """Main loop - monitor buttons and publish state changes"""
        print("=" * 60)
        print("  MQTT Publisher - Button State Publisher")
        print("=" * 60)
        
        # Setup buttons
        if not self.setup_buttons():
            return
        
        print(f"[OK] Buttons initialized (A: {ButtonConfig.BUTTON_A_PIN}, B: {ButtonConfig.BUTTON_B_PIN})")
        
        # Setup MQTT
        if not self.setup_mqtt():
            print("[FAIL] Failed to setup MQTT. Exiting.")
            return
        
        print("=" * 60)
        print("  Monitoring buttons for state changes...")
        print("  Press Ctrl+C to exit")
        print("=" * 60)
        print()
        
        try:
            while True:
                # Read button states (False = pressed, True = not pressed)
                button_a_state = not self.button_a.value  # Invert so True = pressed
                button_b_state = not self.button_b.value  # Invert so True = pressed
                
                # Check if Button A state changed
                if button_a_state != self.prev_button_a_state:
                    self.publish_button_state('A', button_a_state)
                    self.prev_button_a_state = button_a_state
                
                # Check if Button B state changed
                if button_b_state != self.prev_button_b_state:
                    self.publish_button_state('B', button_b_state)
                    self.prev_button_b_state = button_b_state
                
                # Small delay to avoid excessive CPU usage (check every 50ms)
                time.sleep(0.05)
                
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources"""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        print("[OK] MQTT client disconnected")


def main():
    """Entry point for publisher"""
    publisher = ButtonPublisher()
    publisher.run()


if __name__ == '__main__':
    main()

