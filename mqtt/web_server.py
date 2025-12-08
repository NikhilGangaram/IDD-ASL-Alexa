#!/usr/bin/env python3
"""
Web Server with Socket.IO support for real-time updates

Serves the Batman 3D room visualization and handles MQTT<->WebSocket bridge.
"""

from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
from mqtt.subscriber import ButtonSubscriber
from mqtt.config import WebConfig, MQTTConfig
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = WebConfig.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

# Global MQTT subscriber
mqtt_subscriber = None

# Embedded HTML template for 3D room
BATMAN_3D_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Batman Smart Home - 3D Room</title>
    <style>
        body { 
            margin: 0; 
            padding: 0;
            font-family: 'Arial', sans-serif;
            overflow: hidden;
            background: linear-gradient(180deg, #0a0e27 0%, #1a1f3a 100%);
        }
        
        #canvas-container {
            width: 100vw;
            height: 100vh;
            position: relative;
        }
        
        /* Status Panel */
        #status-panel {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(0, 0, 0, 0.8);
            color: #ffd700;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #ffd700;
            font-size: 14px;
            min-width: 250px;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.3);
        }
        
        #status-panel h3 {
            margin-top: 0;
            color: #ffd700;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        
        .status-item {
            margin: 10px 0;
            padding: 8px;
            background: rgba(255, 215, 0, 0.1);
            border-radius: 5px;
            transition: all 0.3s ease;
        }
        
        .status-item.active {
            background: rgba(255, 215, 0, 0.3);
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
        }
        
        /* Finger Count Display */
        #finger-display {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(0, 0, 0, 0.9);
            color: #00ff00;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #00ff00;
            font-size: 24px;
            text-align: center;
            min-width: 200px;
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
        }
        
        #finger-count {
            font-size: 48px;
            font-weight: bold;
            margin: 10px 0;
            text-shadow: 0 0 10px rgba(0, 255, 0, 0.8);
        }
        
        .no-hand {
            color: #666;
            font-size: 18px;
        }
        
        /* Dynamic Legend */
        #legend {
            position: absolute;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #ffd700;
            max-width: 600px;
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.3);
        }
        
        #legend h3 {
            margin-top: 0;
            color: #ffd700;
            text-align: center;
        }
        
        .legend-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-top: 10px;
        }
        
        .legend-item {
            padding: 8px;
            background: rgba(255, 215, 0, 0.1);
            border-radius: 5px;
            border: 1px solid rgba(255, 215, 0, 0.3);
            transition: all 0.3s ease;
        }
        
        .legend-item.highlight {
            background: rgba(255, 215, 0, 0.4);
            border-color: #ffd700;
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.6);
            animation: pulse 0.5s ease;
        }
        
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }
        
        /* Mode Instructions */
        #mode-instructions {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.95);
            color: #ffd700;
            padding: 30px;
            border-radius: 15px;
            border: 3px solid #ffd700;
            font-size: 18px;
            text-align: center;
            max-width: 400px;
            display: none;
            box-shadow: 0 0 30px rgba(255, 215, 0, 0.5);
            animation: fadeIn 0.5s ease;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translate(-50%, -45%); }
            to { opacity: 1; transform: translate(-50%, -50%); }
        }
        
        #mode-instructions h2 {
            margin-top: 0;
            color: #ffd700;
            text-transform: uppercase;
            letter-spacing: 3px;
        }
        
        .mode-list {
            text-align: left;
            margin: 20px 0;
            font-size: 16px;
        }
        
        .mode-list div {
            margin: 10px 0;
            padding: 8px;
            background: rgba(255, 215, 0, 0.1);
            border-radius: 5px;
        }
        
        /* Connection Status */
        #connection-status {
            position: absolute;
            top: 10px;
            right: 10px;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 12px;
            font-weight: bold;
        }
        
        .connected {
            background: #00ff00;
            color: black;
        }
        
        .disconnected {
            background: #ff0000;
            color: white;
        }
    </style>
    <script src="https://cdn.socket.io/4.5.0/socket.io.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
</head>
<body>
    <div id="canvas-container"></div>
    
    <!-- Connection Status -->
    <div id="connection-status" class="disconnected">DISCONNECTED</div>
    
    <!-- Status Panel -->
    <div id="status-panel">
        <h3>System Status</h3>
        <div class="status-item">
            <strong>Mode Phase:</strong> <span id="mode-phase">SELECT_MODE</span>
        </div>
        <div class="status-item">
            <strong>Locked Mode:</strong> <span id="locked-mode">None</span>
        </div>
        <div class="status-item">
            <strong>Last Action:</strong> <span id="last-action">None</span>
        </div>
        <div class="status-item">
            <strong>Confidence:</strong> <span id="confidence">0%</span>
        </div>
    </div>
    
    <!-- Finger Count Display -->
    <div id="finger-display">
        <div>Fingers Detected</div>
        <div id="finger-count" class="no-hand">-</div>
        <div id="hand-status" class="no-hand">No hand detected</div>
    </div>
    
    <!-- Dynamic Legend -->
    <div id="legend">
        <h3>Controls</h3>
        <div id="legend-content"></div>
    </div>
    
    <!-- Mode Selection Instructions (shown when ready) -->
    <div id="mode-instructions">
        <h2>Ready for Input</h2>
        <p>Hold up 1-4 fingers to select mode:</p>
        <div class="mode-list">
            <div>👆 1 Finger → Temperature</div>
            <div>✌️ 2 Fingers → Lights</div>
            <div>🤟 3 Fingers → Blinds</div>
            <div>✋ 4 Fingers → Door</div>
        </div>
    </div>
    
    <script>
        // Socket.IO connection
        const socket = io();
        
        // State tracking
        let currentModePhase = 'SELECT_MODE';
        let currentLockedMode = null;
        let lastAction = null;
        let batmanModel = null;
        
        // Three.js setup
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        document.getElementById('canvas-container').appendChild(renderer.domElement);
        
        // Lighting
        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffd700, 1);
        directionalLight.position.set(5, 10, 5);
        directionalLight.castShadow = true;
        scene.add(directionalLight);
        
        // Batman model (simplified representation)
        const batmanGeometry = new THREE.ConeGeometry(1, 3, 8);
        const batmanMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x2c2c2c,
            emissive: 0x111111,
            specular: 0xffd700,
            shininess: 30
        });
        batmanModel = new THREE.Mesh(batmanGeometry, batmanMaterial);
        batmanModel.position.set(0, 0, 0);
        batmanModel.castShadow = true;
        scene.add(batmanModel);
        
        // Add bat symbol on the model
        const batSymbolGeometry = new THREE.PlaneGeometry(0.8, 0.4);
        const batSymbolMaterial = new THREE.MeshBasicMaterial({ 
            color: 0xffd700,
            side: THREE.DoubleSide
        });
        const batSymbol = new THREE.Mesh(batSymbolGeometry, batSymbolMaterial);
        batSymbol.position.set(0, 0.5, 1.01);
        batmanModel.add(batSymbol);
        
        // Floor
        const floorGeometry = new THREE.PlaneGeometry(20, 20);
        const floorMaterial = new THREE.MeshPhongMaterial({ 
            color: 0x1a1a1a,
            side: THREE.DoubleSide
        });
        const floor = new THREE.Mesh(floorGeometry, floorMaterial);
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = -1.5;
        floor.receiveShadow = true;
        scene.add(floor);
        
        // Camera position
        camera.position.set(0, 2, 8);
        camera.lookAt(0, 0, 0);
        
        // Batman animations/states
        function setBatmanState(state) {
            if (!batmanModel) return;
            
            switch(state) {
                case 'READY':
                    // Idle/ready animation - gentle rotation
                    batmanModel.rotation.y = 0;
                    batmanMaterial.emissive = new THREE.Color(0x001100);
                    break;
                case 'POINT_LEFT':
                    batmanModel.rotation.y = Math.PI / 4;
                    batmanMaterial.emissive = new THREE.Color(0x110011);
                    break;
                case 'POINT_RIGHT':
                    batmanModel.rotation.y = -Math.PI / 4;
                    batmanMaterial.emissive = new THREE.Color(0x110011);
                    break;
                case 'OPEN_HAND':
                    batmanModel.scale.set(1.2, 1.2, 1.2);
                    batmanMaterial.emissive = new THREE.Color(0x002200);
                    setTimeout(() => batmanModel.scale.set(1, 1, 1), 500);
                    break;
                case 'FIST':
                    batmanModel.scale.set(0.8, 0.8, 0.8);
                    batmanMaterial.emissive = new THREE.Color(0x220000);
                    setTimeout(() => batmanModel.scale.set(1, 1, 1), 500);
                    break;
                default:
                    batmanMaterial.emissive = new THREE.Color(0x111111);
            }
        }
        
        // Update legend based on mode
        function updateLegend(modePhase, lockedMode) {
            const legendContent = document.getElementById('legend-content');
            
            if (modePhase === 'SELECT_MODE') {
                legendContent.innerHTML = `
                    <div class="legend-grid">
                        <div class="legend-item">👆 1 Finger → Temperature</div>
                        <div class="legend-item">✌️ 2 Fingers → Lights</div>
                        <div class="legend-item">🤟 3 Fingers → Blinds</div>
                        <div class="legend-item">✋ 4 Fingers → Door</div>
                    </div>
                `;
            } else if (modePhase === 'LOCKED_MODE' && lockedMode) {
                let actions = '';
                switch(lockedMode) {
                    case 'TEMPERATURE':
                        actions = `
                            <div class="legend-item" data-action="OPEN_HAND">✋ Open Hand → AC ON</div>
                            <div class="legend-item" data-action="FIST">✊ Fist → AC OFF</div>
                            <div class="legend-item" data-action="POINT_RIGHT">👉 Point Right → UP</div>
                            <div class="legend-item" data-action="POINT_LEFT">👈 Point Left → DOWN</div>
                        `;
                        break;
                    case 'LIGHTS':
                        actions = `
                            <div class="legend-item" data-action="OPEN_HAND">✋ Open Hand → ON</div>
                            <div class="legend-item" data-action="FIST">✊ Fist → OFF</div>
                            <div class="legend-item" data-action="POINT_RIGHT">👉 Point Right → BRIGHT</div>
                            <div class="legend-item" data-action="POINT_LEFT">👈 Point Left → DIM</div>
                        `;
                        break;
                    case 'BLINDS':
                        actions = `
                            <div class="legend-item" data-action="OPEN_HAND">✋ Open Hand → OPEN</div>
                            <div class="legend-item" data-action="FIST">✊ Fist → CLOSE</div>
                        `;
                        break;
                    case 'DOOR':
                        actions = `
                            <div class="legend-item" data-action="OPEN_HAND">✋ Open Hand → UNLOCK</div>
                            <div class="legend-item" data-action="FIST">✊ Fist → LOCK</div>
                        `;
                        break;
                }
                legendContent.innerHTML = `<div class="legend-grid">${actions}</div>`;
            }
        }
        
        // Highlight action in legend
        function highlightAction(action) {
            const items = document.querySelectorAll('.legend-item');
            items.forEach(item => {
                if (item.dataset.action === action) {
                    item.classList.add('highlight');
                    setTimeout(() => item.classList.remove('highlight'), 1000);
                }
            });
        }
        
        // Socket.IO event handlers
        socket.on('connect', () => {
            console.log('Connected to server');
            document.getElementById('connection-status').className = 'connected';
            document.getElementById('connection-status').textContent = 'CONNECTED';
        });
        
        socket.on('disconnect', () => {
            console.log('Disconnected from server');
            document.getElementById('connection-status').className = 'disconnected';
            document.getElementById('connection-status').textContent = 'DISCONNECTED';
        });
        
        socket.on('gesture_telemetry', (data) => {
            // Update mode phase
            currentModePhase = data.mode_phase || 'SELECT_MODE';
            currentLockedMode = data.locked_mode;
            
            document.getElementById('mode-phase').textContent = currentModePhase;
            document.getElementById('locked-mode').textContent = currentLockedMode || 'None';
            
            // Update finger count display
            if (data.finger_count !== null && data.finger_count !== undefined) {
                document.getElementById('finger-count').textContent = data.finger_count;
                document.getElementById('finger-count').className = '';
                document.getElementById('hand-status').textContent = `Stable for ${data.confidence ? Math.round(data.confidence * 5) : 0}/5 frames`;
                document.getElementById('hand-status').className = '';
            } else {
                document.getElementById('finger-count').textContent = '-';
                document.getElementById('finger-count').className = 'no-hand';
                document.getElementById('hand-status').textContent = 'No hand detected';
                document.getElementById('hand-status').className = 'no-hand';
            }
            
            // Update confidence
            const confidencePercent = Math.round((data.confidence || 0) * 100);
            document.getElementById('confidence').textContent = `${confidencePercent}%`;
            
            // Update action gesture
            if (data.action_gesture && currentModePhase === 'LOCKED_MODE') {
                lastAction = data.action_gesture;
                document.getElementById('last-action').textContent = data.action_gesture;
                setBatmanState(data.action_gesture);
                highlightAction(data.action_gesture);
            }
            
            // Show/hide mode instructions
            const instructions = document.getElementById('mode-instructions');
            if (currentModePhase === 'SELECT_MODE') {
                instructions.style.display = 'block';
                setBatmanState('READY');
            } else {
                instructions.style.display = 'none';
            }
            
            // Update legend
            updateLegend(currentModePhase, currentLockedMode);
        });
        
        socket.on('gesture_command', (data) => {
            console.log('Gesture command:', data);
            // Visual feedback for commands
            const statusItems = document.querySelectorAll('.status-item');
            statusItems.forEach(item => {
                item.classList.add('active');
                setTimeout(() => item.classList.remove('active'), 500);
            });
        });
        
        // Animation loop
        function animate() {
            requestAnimationFrame(animate);
            
            // Idle animation for Batman model
            if (batmanModel && currentModePhase === 'SELECT_MODE') {
                batmanModel.rotation.y += 0.005;
            }
            
            renderer.render(scene, camera);
        }
        
        // Handle window resize
        window.addEventListener('resize', () => {
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        });
        
        // Start animation
        animate();
        
        // Initialize
        setBatmanState('READY');
        updateLegend('SELECT_MODE', null);
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    """Serve main dashboard"""
    return "<h1>Batman Smart Home Control</h1><p>Visit <a href='/3d-room'>/3d-room</a> for 3D visualization</p>"


@app.route('/3d-room')
def room_3d():
    """Serve the 3D Batman room visualization"""
    return render_template_string(BATMAN_3D_HTML)


@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print('[WebSocket] Client connected')
    
    # Send initial state
    if mqtt_subscriber:
        emit('button_states', mqtt_subscriber.get_states())
        emit('gesture_states', mqtt_subscriber.get_gesture_states())
        emit('current_mode', {'mode': mqtt_subscriber.get_current_mode()})
        emit('gesture_telemetry', mqtt_subscriber.get_telemetry())
        emit('activity_history', {'history': mqtt_subscriber.get_history()})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print('[WebSocket] Client disconnected')


@socketio.on('request_state')
def handle_request_state():
    """Handle state request from client"""
    if mqtt_subscriber:
        emit('button_states', mqtt_subscriber.get_states())
        emit('gesture_states', mqtt_subscriber.get_gesture_states())
        emit('current_mode', {'mode': mqtt_subscriber.get_current_mode()})
        emit('gesture_telemetry', mqtt_subscriber.get_telemetry())
        emit('activity_history', {'history': mqtt_subscriber.get_history()})


def main():
    """Main entry point"""
    global mqtt_subscriber
    
    print("=" * 60)
    print("  Batman Smart Home Web Server")
    print("=" * 60)
    
    # Setup MQTT subscriber with SocketIO
    mqtt_subscriber = ButtonSubscriber(socketio)
    if not mqtt_subscriber.setup():
        print("[WARN] MQTT setup failed, continuing without MQTT")
    
    # Print access info
    print(f"[OK] Web server starting on http://{WebConfig.HOST}:{WebConfig.PORT}")
    print(f"[OK] 3D Room available at http://{WebConfig.HOST}:{WebConfig.PORT}/3d-room")
    print("=" * 60)
    
    # Run server
    try:
        socketio.run(app, host=WebConfig.HOST, port=WebConfig.PORT, debug=WebConfig.DEBUG)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if mqtt_subscriber:
            mqtt_subscriber.cleanup()


if __name__ == '__main__':
    main()