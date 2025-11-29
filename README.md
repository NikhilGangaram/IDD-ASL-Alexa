# IDD-ASL-Alexa

A gesture-controlled smart home system that uses hand gestures to control devices via MQTT, with real-time dashboard updates.

## Features

- **Gesture Control**: Use hand gestures to control temperature, lights, blinds, and doors
- **MQTT Integration**: Commands published as JSON to MQTT broker
- **Real-time Dashboard**: Web dashboard updates instantly via WebSocket
- **Camera-based**: Uses MediaPipe for hand gesture recognition

## Quick Start

### Prerequisites

- Python 3.8 - 3.11 (MediaPipe requirement)
- Webcam
- MQTT broker access (default: public HiveMQ broker)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd IDD-ASL-Alexa

# Create virtual environment (recommended)
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run

**Terminal 1 - Start Dashboard:**
```bash
python3 dashboard.py
```
Open browser to `http://localhost:8080`

**Terminal 2 - Start Gesture Controller:**
```bash
python3 publish.py
```

## Gestures

### Mode Selection (Hold up fingers)
- **1 Finger** → Temperature 🌡️
- **2 Fingers** → Lights 💡
- **3 Fingers** → Blinds 🪟
- **4 Fingers** → Door 🚪

### Actions (After selecting mode)
- **Open Hand** 🖐️ → Turn On / Open / Unlock
- **Fist** ✊ → Turn Off / Close / Lock
- **Point Right** 👉 → Increase / Brighten
- **Point Left** 👈 → Decrease / Dim

## Configuration

### MQTT Settings

Set environment variables or edit `mqtt/config.py`:

```bash
export MQTT_BROKER='broker.hivemq.com'
export MQTT_PORT='1883'
export MQTT_TOPIC='IDD/button/state'
export MQTT_USERNAME=''  # Optional
export MQTT_PASSWORD=''  # Optional
```

### School Network (Cornell)

```bash
export MQTT_BROKER='farlab.infosci.cornell.edu'
export MQTT_USERNAME='idd'
export MQTT_PASSWORD='device@theFarm'
```

### Web Server Port

```bash
export PORT='8080'  # Default: 8080
```

## Project Structure

```
IDD-ASL-Alexa/
├── gesture_controller.py    # Gesture recognition & MQTT publisher
├── publish.py                # Entry point for gesture controller
├── dashboard.py              # Entry point for web dashboard
├── mqtt/
│   ├── config.py            # MQTT configuration
│   ├── publisher.py         # Legacy button publisher
│   ├── subscriber.py        # MQTT subscriber & state manager
│   ├── web_server.py        # Flask web server
│   └── templates/
│       └── dashboard.html   # Web dashboard UI
└── requirements.txt         # Python dependencies
```

## How It Works

1. **Gesture Recognition**: Camera captures hand gestures using MediaPipe
2. **Command Processing**: Gestures mapped to category (temp/lights/blinds/door) and action (on/off/up/down)
3. **MQTT Publishing**: Commands packaged as JSON and published to MQTT topic
4. **Dashboard Display**: Web dashboard subscribes to MQTT, receives commands, and updates UI in real-time

## Troubleshooting

**Camera not working:**
- Check camera permissions
- Ensure camera is not in use by another application

**Gestures not recognized:**
- Ensure good lighting
- Keep hand visible and well-lit
- Try adjusting distance from camera

**MQTT connection failed:**
- Check broker hostname and port
- Verify network connectivity
- Check firewall settings

**Port already in use:**
```bash
PORT=8081 python3 dashboard.py
```

## License

[Add your license here]
