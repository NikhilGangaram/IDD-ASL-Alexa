# Batman Cave 3D Room Visualization

## Overview
A fully interactive 3D room visualization that responds to your MQTT gesture controls in real-time. This runs as a **separate** visualization alongside your existing dashboard, providing an immersive 3D view of your smart home controls.

## Features

### 🦇 3D Environment
- **Realistic Room Model**: Full 3D room with walls, floor, ceiling
- **Dynamic Camera**: Mouse-controlled camera rotation and scroll zoom
- **Batman Cave Aesthetic**: Dark theme with gold accents (#FFC107)
- **Furniture & Details**: Desk, monitors, chair, and more

### 🎮 Interactive Elements

#### Temperature Display
- Floating holographic orb that changes color:
  - **Normal (68-75°F)**: Golden glow
  - **Hot (>75°F)**: Red glow
  - **Cold (<68°F)**: Green glow
- Animated rotation and hovering effect

#### Lighting System
- Main room light with smooth intensity transitions
- **OFF**: Complete darkness (ambient only)
- **DIM**: 50% intensity warm lighting
- **ON/BRIGHT**: Full brightness
- Additional accent lights from monitors

#### Window Blinds
- Animated slat-by-slat movement
- **OPEN**: Clear window view
- **PARTIAL/HALF**: Half coverage
- **CLOSED**: Full blind coverage with sequential animation

#### Security Door
- Realistic door swing animation
- **LOCKED**: Closed with red lock indicator
- **UNLOCKED/OPEN**: Door swings open with green indicator
- Smooth rotation animations

## Setup Instructions

### Running the 3D Room

1. **Keep your existing dashboard running**:
   ```bash
   # Terminal 1 - Dashboard server
   python3 dashboard.py
   ```

2. **Open the 3D room in a new browser window**:
   ```bash
   # Open in browser
   http://localhost:8080
   ```
   Then open the 3D room file directly in another tab/window

3. **Start gesture controller** (if not already running):
   ```bash
   # Terminal 2 - Gesture controller
   python3 publish.py
   ```

### Alternative: Serve 3D Room from Same Server

To serve the 3D room from the same Flask server, add this route to your `web_server.py`:

```python
@app.route('/3d-room')
def room_3d():
    return send_from_directory('templates', 'batman_room_3d.html')
```

Then copy the file:
```bash
cp batman_room_3d.html mqtt/templates/
```

Access at: `http://localhost:8080/3d-room`

## Usage

### Camera Controls
- **Mouse Move**: Rotate camera view around the room
- **Scroll Wheel**: Zoom in/out
- **Auto-follow**: Camera smoothly follows mouse movement

### HUD Elements
- **Top Left**: Real-time system status panel
- **Top Right**: Connection status indicator
- **Center**: Mode selection overlay (appears when changing modes)
- **Bottom**: Control instructions

### Gesture Control Integration
The 3D room listens to the same MQTT messages as your dashboard:

1. **Select Mode** (hold up fingers):
   - 1 finger → Temperature control
   - 2 fingers → Lights control
   - 3 fingers → Blinds control
   - 4 fingers → Door control

2. **Execute Action**:
   - Open hand → Turn ON / Open / Unlock
   - Fist → Turn OFF / Close / Lock
   - Point right → Increase / Brighten
   - Point left → Decrease / Dim

## Technical Details

### Technologies Used
- **Three.js**: 3D graphics rendering
- **Socket.IO**: Real-time WebSocket communication
- **WebGL**: Hardware-accelerated 3D graphics

### Room Coordinates
- Room size: 20x12x20 units
- Camera position: (0, 5, 15) looking at origin
- Door: Back wall center
- Window: Right wall
- Desk: Against back wall

### Performance
- Optimized shadows and lighting
- Smooth 60fps animations
- Responsive to all screen sizes

## Customization

### Colors
Edit the CSS variables in the HTML:
```javascript
// Main light color (line ~370)
mainLight = new THREE.PointLight(0xFFC107, 0, 20);  // Gold

// Temperature colors (lines ~730-740)
color = 0xFF5252; // Red for hot
color = 0x00E676; // Green for cold
color = 0xFFC107; // Yellow for normal
```

### Room Size
Modify geometry dimensions in `createRoom()` function:
```javascript
const floorGeometry = new THREE.PlaneGeometry(20, 20);  // Width, Depth
```

### Camera View
Adjust initial camera position:
```javascript
camera.position.set(0, 5, 15);  // X, Y, Z
```

## Troubleshooting

### Black Screen
- Check browser console for WebGL errors
- Ensure WebGL is enabled in browser
- Try refreshing the page

### No Response to Gestures
- Verify MQTT connection (top right indicator)
- Check that gesture controller is running
- Ensure both dashboard and 3D room are on same MQTT topic

### Performance Issues
- Close other GPU-intensive applications
- Reduce browser window size
- Disable shadows by commenting out:
  ```javascript
  renderer.shadowMap.enabled = true;
  ```

## Browser Compatibility
- **Best**: Chrome, Edge (Chromium)
- **Good**: Firefox, Safari
- **Required**: WebGL support

## Multi-Display Setup
For the ultimate Batman cave experience:
1. Run dashboard on one monitor
2. Run 3D room on another monitor
3. Both update simultaneously from gesture controls

Enjoy your immersive Batman cave control center! 🦇✨
