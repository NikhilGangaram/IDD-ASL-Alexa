# MQTT Button State Monitor

A professional MQTT-based system for monitoring button states from a Raspberry Pi and displaying them in a real-time web dashboard.

## Project Structure

```
IDD-ASL-Alexa/
├── mqtt/                    # MQTT package
│   ├── __init__.py         # Package initialization
│   ├── config.py           # Configuration settings
│   ├── publisher.py        # Raspberry Pi button publisher
│   ├── subscriber.py       # MQTT message subscriber
│   ├── web_server.py       # Flask web server
│   └── templates/          # HTML templates
│       └── dashboard.html   # Web dashboard template
├── publish.py              # Entry point for publisher (Raspberry Pi)
├── dashboard.py            # Entry point for web server (Laptop)
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## Features

- **Real-time Updates**: WebSocket-based real-time button state updates
- **Event-Driven**: Only publishes when button states change
- **Web Dashboard**: Beautiful, responsive web interface
- **Activity Feed**: History of button events
- **MQTT Support**: Works with any MQTT broker
- **Modular Design**: Clean separation of concerns

## Installation

### Prerequisites

- Python 3.7+
- Raspberry Pi with MiniPiTFT (for publisher)
- MQTT broker access (default: public HiveMQ broker)

### Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd IDD-ASL-Alexa
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   **Note**: On your laptop, you can skip Raspberry Pi hardware libraries:
   ```bash
   pip install "paho-mqtt<2.0" flask flask-socketio
   ```

## Usage

### On Raspberry Pi (Publisher)

Run the button publisher to monitor buttons and publish state changes:

```bash
python3 publish.py
```

**What it does:**
- Connects to MQTT broker (default: `broker.hivemq.com`)
- Monitors button A (D23) and button B (D24) continuously
- Publishes button states to topic `IDD/button/state` only when state changes
- Press Ctrl+C to stop

### On Laptop (Web Dashboard)

Run the web dashboard server:

```bash
python3 dashboard.py
```

**What it does:**
- Connects to MQTT broker (default: `broker.hivemq.com`)
- Subscribes to topic `IDD/button/state`
- Starts web server on `http://localhost:8080`
- Serves real-time dashboard showing button states
- Press Ctrl+C to stop

### Running Both Together

1. **Start the web dashboard on your laptop**:
   ```bash
   python3 dashboard.py
   ```
   Then open your browser to: `http://localhost:8080`

2. **Start the publisher on Raspberry Pi**:
   ```bash
   python3 publish.py
   ```

3. Press buttons on the Raspberry Pi and watch the state updates appear in real-time on the web dashboard!

## Configuration

Configuration is centralized in `mqtt/config.py` and can be overridden with environment variables:

### MQTT Configuration

```bash
export MQTT_BROKER='broker.hivemq.com'  # MQTT broker hostname
export MQTT_PORT='1883'                  # MQTT broker port
export MQTT_TOPIC='IDD/button/state'     # MQTT topic
export MQTT_USERNAME=''                  # Optional: MQTT username
export MQTT_PASSWORD=''                  # Optional: MQTT password
```

### Web Server Configuration

```bash
export PORT='8080'                       # Web server port (default: 8080)
export HOST='0.0.0.0'                    # Web server host (default: 0.0.0.0)
```

### School Network Configuration

To use the school network broker:

```bash
export MQTT_BROKER='farlab.infosci.cornell.edu'
export MQTT_USERNAME='idd'
export MQTT_PASSWORD='device@theFarm'
```

## Architecture

### Components

1. **Publisher** (`mqtt/publisher.py`): 
   - Runs on Raspberry Pi
   - Monitors GPIO buttons
   - Publishes state changes to MQTT

2. **Subscriber** (`mqtt/subscriber.py`):
   - Receives MQTT messages
   - Manages button state
   - Maintains activity history

3. **Web Server** (`mqtt/web_server.py`):
   - Flask application
   - Serves dashboard HTML
   - WebSocket communication for real-time updates

4. **Configuration** (`mqtt/config.py`):
   - Centralized configuration
   - Environment variable support

## Development

### Project Structure

- **`mqtt/`**: Core MQTT package with modular components
- **`publish.py`**: Entry point for Raspberry Pi publisher
- **`dashboard.py`**: Entry point for web dashboard server
- **`mqtt/templates/`**: HTML templates for web interface

### Adding New Features

1. **New MQTT topics**: Update `mqtt/config.py`
2. **New buttons**: Update `mqtt/config.py` ButtonConfig
3. **UI changes**: Edit `mqtt/templates/dashboard.html`

## Troubleshooting

### Port Already in Use

If port 8080 is in use, set a different port:
```bash
PORT=8081 python3 dashboard.py
```

### MQTT Connection Issues

- Check broker hostname and port
- Verify network connectivity
- Check firewall settings
- Review MQTT broker logs

### Button Not Detected

- Verify GPIO pin configuration in `mqtt/config.py`
- Check hardware connections
- Ensure proper permissions for GPIO access

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]
