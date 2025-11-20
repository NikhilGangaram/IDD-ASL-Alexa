#!/usr/bin/env python3
"""
MQTT Module - Raspberry Pi Button State Publisher
Reads button states from MiniPiTFT buttons and publishes to MQTT when state changes
"""

import time
import digitalio
import board
import paho.mqtt.client as mqtt
import json
import uuid
import os

# MQTT Configuration
# Can be overridden with environment variables for easy switching between networks
# Default: Public Mosquitto broker (no authentication required)
# To use school network: export MQTT_BROKER='farlab.infosci.cornell.edu' MQTT_USERNAME='idd' MQTT_PASSWORD='device@theFarm'

MQTT_BROKER = os.getenv('MQTT_BROKER', 'broker.hivemq.com')  # Default: HiveMQ public broker (works with Python and browsers)
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'IDD/button/state')
MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')  # Empty for public brokers
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')  # Empty for public brokers

# Button Configuration
BUTTON_A_PIN = board.D23
BUTTON_B_PIN = board.D24

mqtt_client = None


def on_connect(client, userdata, flags, rc):
    """MQTT connection callback"""
    if rc == 0:
        print(f'[OK] MQTT connected to {MQTT_BROKER}:{MQTT_PORT}')
        print(f'[OK] Publishing to {MQTT_TOPIC}')
    else:
        print(f'[FAIL] MQTT connection failed: {rc}')


def on_publish(client, userdata, mid):
    """MQTT publish callback (optional, for confirmation)"""
    pass


def setup_buttons():
    """Setup button pins"""
    buttonA = digitalio.DigitalInOut(BUTTON_A_PIN)
    buttonB = digitalio.DigitalInOut(BUTTON_B_PIN)
    buttonA.switch_to_input(pull=digitalio.Pull.UP)
    buttonB.switch_to_input(pull=digitalio.Pull.UP)
    return buttonA, buttonB


def setup_mqtt():
    """Setup and connect MQTT client"""
    global mqtt_client
    try:
        mqtt_client = mqtt.Client(str(uuid.uuid1()))
        
        # Only set username/password if provided (public brokers don't need auth)
        if MQTT_USERNAME and MQTT_PASSWORD:
            mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        mqtt_client.on_connect = on_connect
        mqtt_client.on_publish = on_publish
        
        mqtt_client.connect(MQTT_BROKER, port=MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        
        # Wait for connection
        time.sleep(1)
        return True
    except Exception as e:
        print(f'[WARN] MQTT setup failed: {e}')
        return False


def main():
    """Main loop - read buttons and publish state only when it changes"""
    print("=" * 60)
    print("  MQTT Module - Button State Publisher")
    print("=" * 60)
    
    # Setup buttons
    try:
        buttonA, buttonB = setup_buttons()
        print("[OK] Buttons initialized (A: D23, B: D24)")
    except Exception as e:
        print(f"[FAIL] Button setup failed: {e}")
        return
    
    # Setup MQTT
    if not setup_mqtt():
        print("[FAIL] Failed to setup MQTT. Exiting.")
        return
    
    print("=" * 60)
    print("  Monitoring buttons for state changes...")
    print("  Press Ctrl+C to exit")
    print("=" * 60)
    print()
    
    # Track previous button states
    prev_button_a_state = None
    prev_button_b_state = None
    
    try:
        while True:
            # Read button states (False = pressed, True = not pressed)
            button_a_state = not buttonA.value  # Invert so True = pressed
            button_b_state = not buttonB.value  # Invert so True = pressed
            
            # Check if Button A state changed
            if button_a_state != prev_button_a_state:
                payload_a = {
                    'button_id': 'A',
                    'state': button_a_state
                }
                result = mqtt_client.publish(MQTT_TOPIC, json.dumps(payload_a))
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    state_str = "PRESSED" if button_a_state else "RELEASED"
                    print(f"[{time.strftime('%H:%M:%S')}] Button A: {state_str}")
                else:
                    print(f"[ERROR] Failed to publish Button A state: rc={result.rc}")
                prev_button_a_state = button_a_state
            
            # Check if Button B state changed
            if button_b_state != prev_button_b_state:
                payload_b = {
                    'button_id': 'B',
                    'state': button_b_state
                }
                result = mqtt_client.publish(MQTT_TOPIC, json.dumps(payload_b))
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    state_str = "PRESSED" if button_b_state else "RELEASED"
                    print(f"[{time.strftime('%H:%M:%S')}] Button B: {state_str}")
                else:
                    print(f"[ERROR] Failed to publish Button B state: rc={result.rc}")
                prev_button_b_state = button_b_state
            
            # Small delay to avoid excessive CPU usage (check every 50ms)
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        print("[OK] MQTT client disconnected")


if __name__ == '__main__':
    main()

