#!/usr/bin/env python3
"""
MQTT Hub - Web Dashboard Server
Subscribes to MQTT topic and serves a web dashboard showing button states
"""

import paho.mqtt.client as mqtt
import json
import uuid
import os
from datetime import datetime
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import threading
import time

# MQTT Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', 'broker.hivemq.com')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'IDD/button/state')
MQTT_USERNAME = os.getenv('MQTT_USERNAME', '')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', '')

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'button-dashboard-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store current button states
button_states = {
    'A': False,
    'B': False
}

# Store activity history
activity_history = []

mqtt_client = None


def on_connect(client, userdata, flags, rc):
    """MQTT connection callback"""
    if rc == 0:
        print(f'[OK] MQTT connected to {MQTT_BROKER}:{MQTT_PORT}')
        client.subscribe(MQTT_TOPIC)
        print(f'[OK] Subscribed to {MQTT_TOPIC}')
        socketio.emit('mqtt_status', {'connected': True})
    else:
        print(f'[FAIL] MQTT connection failed: {rc}')
        socketio.emit('mqtt_status', {'connected': False})


def on_message(client, userdata, msg):
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
        old_state = button_states[button_id]
        button_states[button_id] = state
        
        # Only process if state changed
        if old_state != state:
            timestamp = datetime.now().strftime('%H:%M:%S')
            state_str = "PRESSED" if state else "RELEASED"
            
            print(f"[{timestamp}] Button {button_id}: {state_str}")
            
            # Add to activity history
            activity_item = {
                'button_id': button_id,
                'state': state_str,
                'timestamp': timestamp
            }
            activity_history.insert(0, activity_item)
            if len(activity_history) > 20:
                activity_history.pop()
            
            # Broadcast to all connected web clients
            socketio.emit('button_update', {
                'button_id': button_id,
                'state': state,
                'state_str': state_str,
                'timestamp': timestamp
            })
            
            # Send current states
            socketio.emit('button_states', button_states.copy())
        
    except json.JSONDecodeError as e:
        print(f'[WARN] Failed to parse JSON: {e}')
    except Exception as e:
        print(f'[WARN] Error processing message: {e}')


def setup_mqtt():
    """Setup and connect MQTT client"""
    global mqtt_client
    try:
        mqtt_client = mqtt.Client(str(uuid.uuid1()))
        
        if MQTT_USERNAME and MQTT_PASSWORD:
            mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        
        mqtt_client.connect(MQTT_BROKER, port=MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        
        time.sleep(1)
        return True
    except Exception as e:
        print(f'[WARN] MQTT setup failed: {e}')
        return False


@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return render_template_string(DASHBOARD_HTML)


@socketio.on('connect')
def handle_connect():
    """Handle web client connection"""
    print('[OK] Web client connected')
    # Send current states to newly connected client
    emit('button_states', button_states.copy())
    emit('mqtt_status', {'connected': mqtt_client is not None and mqtt_client.is_connected()})
    # Send activity history
    if activity_history:
        emit('activity_history', activity_history)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle web client disconnection"""
    print('[OK] Web client disconnected')


def main():
    """Main function - start Flask server and MQTT client"""
    print("=" * 60)
    print("  MQTT Hub - Web Dashboard Server")
    print("=" * 60)
    
    if not setup_mqtt():
        print("[FAIL] Failed to setup MQTT. Exiting.")
        return
    
    print("=" * 60)
    print("  Starting web server on http://localhost:5000")
    print("  Press Ctrl+C to exit")
    print("=" * 60)
    print()
    
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        print("[OK] MQTT client disconnected")


# Embedded HTML dashboard
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Button State Dashboard</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        :root {
            --primary: #2563eb;
            --success: #16a34a;
            --warning: #ca8a04;
            --danger: #dc2626;
            --background: #000000;
            --surface: #1a1a1a;
            --text-primary: #ffffff;
            --text-secondary: #a3a3a3;
            --border: #404040;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--background);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .header {
            background: var(--surface);
            padding: 1rem 2rem;
            border-bottom: 2px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            font-size: 1.5rem;
            font-weight: bold;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .connection-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            background: rgba(255, 255, 255, 0.1);
            font-size: 1.125rem;
        }

        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        .status-indicator.connected {
            background: var(--success);
        }

        .status-indicator.disconnected {
            background: var(--danger);
            animation: none;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .main-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
            width: 100%;
        }

        .dashboard-title {
            font-size: 2rem;
            margin-bottom: 3rem;
            text-align: center;
        }

        .button-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
            width: 100%;
            max-width: 800px;
        }

        .button-card {
            background: var(--surface);
            border: 2px solid var(--border);
            border-radius: 1rem;
            padding: 2rem;
            text-align: center;
            transition: all 0.3s ease;
        }

        .button-card.pressed {
            border-color: var(--success);
            box-shadow: 0 0 30px rgba(22, 163, 74, 0.4);
            background: rgba(22, 163, 74, 0.1);
        }

        .button-card.released {
            border-color: var(--border);
        }

        .button-label {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--text-secondary);
        }

        .button-state {
            font-size: 4rem;
            font-weight: bold;
            margin: 1.5rem 0;
            transition: all 0.3s ease;
        }

        .button-state.pressed {
            color: var(--success);
            transform: scale(1.1);
        }

        .button-state.released {
            color: var(--text-secondary);
        }

        .button-status-text {
            font-size: 1.25rem;
            margin-top: 1rem;
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            display: inline-block;
        }

        .button-status-text.pressed {
            background: rgba(22, 163, 74, 0.2);
            color: var(--success);
        }

        .button-status-text.released {
            background: rgba(163, 163, 163, 0.1);
            color: var(--text-secondary);
        }

        .activity-section {
            width: 100%;
            max-width: 800px;
            margin-top: 3rem;
        }

        .section-title {
            font-size: 1.5rem;
            margin-bottom: 1.5rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--border);
        }

        .activity-feed {
            background: var(--surface);
            border: 2px solid var(--border);
            border-radius: 1rem;
            padding: 1.5rem;
            max-height: 400px;
            overflow-y: auto;
        }

        .activity-item {
            padding: 1rem;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 0.5rem;
            margin-bottom: 0.75rem;
            animation: slideIn 0.3s ease;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateX(20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }

        .activity-button {
            font-weight: 600;
            font-size: 1.125rem;
        }

        .activity-state {
            padding: 0.5rem 1rem;
            border-radius: 0.5rem;
            font-size: 0.875rem;
            font-weight: 600;
        }

        .activity-state.pressed {
            background: rgba(22, 163, 74, 0.2);
            color: var(--success);
        }

        .activity-state.released {
            background: rgba(163, 163, 163, 0.1);
            color: var(--text-secondary);
        }

        .activity-time {
            color: var(--text-secondary);
            font-size: 0.875rem;
        }

        @media (max-width: 768px) {
            .button-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">
            <span>BUTTON</span>
            <span>State Dashboard</span>
        </div>
        <div class="connection-status">
            <span class="status-indicator disconnected" id="statusIndicator"></span>
            <span id="connectionText">Connecting...</span>
        </div>
    </header>

    <div class="main-container">
        <h1 class="dashboard-title">Raspberry Pi Button States</h1>
        
        <div class="button-grid">
            <div class="button-card released" id="buttonACard">
                <div class="button-label">Button A</div>
                <div class="button-state released" id="buttonAState">OFF</div>
                <div class="button-status-text released" id="buttonAStatus">RELEASED</div>
            </div>

            <div class="button-card released" id="buttonBCard">
                <div class="button-label">Button B</div>
                <div class="button-state released" id="buttonBState">OFF</div>
                <div class="button-status-text released" id="buttonBStatus">RELEASED</div>
            </div>
        </div>

        <div class="activity-section">
            <h2 class="section-title">Activity Feed</h2>
            <div class="activity-feed" id="activityFeed">
                <div class="activity-item">
                    <div>
                        <div class="activity-button">Waiting for button events...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        
        socket.on('connect', function() {
            console.log('Connected to server');
            updateConnectionStatus(true);
        });

        socket.on('disconnect', function() {
            console.log('Disconnected from server');
            updateConnectionStatus(false);
        });

        socket.on('mqtt_status', function(data) {
            if (data.connected) {
                updateConnectionStatus(true);
            } else {
                updateConnectionStatus(false);
            }
        });

        socket.on('button_update', function(data) {
            updateButtonState(data.button_id, data.state);
            addActivityItem(data.button_id, data.state_str, data.timestamp);
        });

        socket.on('button_states', function(states) {
            updateButtonState('A', states.A);
            updateButtonState('B', states.B);
        });

        socket.on('activity_history', function(history) {
            const feed = document.getElementById('activityFeed');
            feed.innerHTML = '';
            history.forEach(function(item) {
                addActivityItem(item.button_id, item.state, item.timestamp);
            });
        });

        function updateButtonState(buttonId, state) {
            const card = document.getElementById(`button${buttonId}Card`);
            const stateElement = document.getElementById(`button${buttonId}State`);
            const statusElement = document.getElementById(`button${buttonId}Status`);

            if (state) {
                card.className = 'button-card pressed';
                stateElement.className = 'button-state pressed';
                stateElement.textContent = 'ON';
                statusElement.className = 'button-status-text pressed';
                statusElement.textContent = 'PRESSED';
            } else {
                card.className = 'button-card released';
                stateElement.className = 'button-state released';
                stateElement.textContent = 'OFF';
                statusElement.className = 'button-status-text released';
                statusElement.textContent = 'RELEASED';
            }
        }

        function addActivityItem(buttonId, stateStr, timestamp) {
            const feed = document.getElementById('activityFeed');
            
            const waitingMsg = feed.querySelector('.activity-item:first-child');
            if (waitingMsg && waitingMsg.textContent.includes('Waiting')) {
                waitingMsg.remove();
            }

            const item = document.createElement('div');
            item.className = 'activity-item';
            
            const stateClass = stateStr === 'PRESSED' ? 'pressed' : 'released';

            item.innerHTML = `
                <div>
                    <div class="activity-button">Button ${buttonId}</div>
                </div>
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <span class="activity-state ${stateClass}">${stateStr}</span>
                    <span class="activity-time">${timestamp}</span>
                </div>
            `;

            feed.insertBefore(item, feed.firstChild);

            while (feed.children.length > 20) {
                feed.removeChild(feed.lastChild);
            }
        }

        function updateConnectionStatus(connected) {
            const indicator = document.getElementById('statusIndicator');
            const text = document.getElementById('connectionText');

            if (connected) {
                indicator.className = 'status-indicator connected';
                text.textContent = 'MQTT Connected';
            } else {
                indicator.className = 'status-indicator disconnected';
                text.textContent = 'MQTT Disconnected';
            }
        }
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    main()
