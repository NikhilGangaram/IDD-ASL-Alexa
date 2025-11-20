#!/usr/bin/env python3
"""
MQTT Hub - Laptop Button State Receiver
Subscribes to MQTT topic and displays button states from Raspberry Pi module
"""

import paho.mqtt.client as mqtt
import json
import uuid
import os
from datetime import datetime

# MQTT Configuration
# Can be overridden with environment variables for easy switching between networks
# Default: Public Mosquitto broker (no authentication required)
# To use school network: export MQTT_BROKER='farlab.infosci.cornell.edu' MQTT_USERNAME='idd' MQTT_PASSWORD='device@theFarm'

MQTT_BROKER = os.getenv('MQTT_BROKER', 'test.mosquitto.org')  # Default: public Mosquitto broker
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'IDD/button/state')
MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')  # Empty for public brokers
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')  # Empty for public brokers

mqtt_client = None

# Store current button states
button_states = {
    'A': False,
    'B': False
}


def on_connect(client, userdata, flags, rc):
    """MQTT connection callback"""
    if rc == 0:
        print(f'✓ MQTT connected to {MQTT_BROKER}:{MQTT_PORT}')
        client.subscribe(MQTT_TOPIC)
        print(f'✓ Subscribed to {MQTT_TOPIC}')
    else:
        print(f'✗ MQTT connection failed: {rc}')


def on_message(client, userdata, msg):
    """MQTT message received - update and display button state"""
    try:
        data = json.loads(msg.payload.decode('UTF-8'))
        button_id = data.get('button_id')
        state = data.get('state', False)
        
        # Validate button_id
        if button_id not in ['A', 'B']:
            print(f'⚠️  Unknown button_id: {button_id}')
            return
        
        # Update state
        old_state = button_states[button_id]
        button_states[button_id] = state
        
        # Display update
        timestamp = datetime.now().strftime('%H:%M:%S')
        state_str = "PRESSED" if state else "RELEASED"
        
        # Only print if state changed or first time
        if old_state != state or old_state is None:
            print(f"[{timestamp}] Button {button_id}: {state_str}")
        
        # Display current state summary
        display_state_summary()
        
    except json.JSONDecodeError as e:
        print(f'⚠️  Failed to parse JSON: {e}')
        print(f'   Raw payload: {msg.payload.decode("UTF-8", errors="replace")}')
    except Exception as e:
        print(f'⚠️  Error processing message: {e}')


def display_state_summary():
    """Display current state of all buttons"""
    states = []
    for btn_id in sorted(button_states.keys()):
        state_str = "PRESSED" if button_states[btn_id] else "RELEASED"
        states.append(f"Button {btn_id}: {state_str}")
    
    # Print summary on same line (overwrite previous)
    summary = " | ".join(states)
    print(f"\r{summary}", end='', flush=True)


def setup_mqtt():
    """Setup and connect MQTT client"""
    global mqtt_client
    try:
        mqtt_client = mqtt.Client(str(uuid.uuid1()))
        
        # Only set username/password if provided (public brokers don't need auth)
        if MQTT_USERNAME and MQTT_PASSWORD:
            mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        
        mqtt_client.connect(MQTT_BROKER, port=MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        
        # Wait for connection
        import time
        time.sleep(1)
        return True
    except Exception as e:
        print(f'⚠️  MQTT setup failed: {e}')
        return False


def main():
    """Main function - keep running and receiving messages"""
    print("=" * 60)
    print("  MQTT Hub - Button State Receiver")
    print("=" * 60)
    
    if not setup_mqtt():
        print("✗ Failed to setup MQTT. Exiting.")
        return
    
    print("=" * 60)
    print("  Listening for button state updates...")
    print("  Press Ctrl+C to exit")
    print("=" * 60)
    print()
    
    try:
        # Keep running
        import time
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        print("✓ MQTT client disconnected")


if __name__ == '__main__':
    main()

