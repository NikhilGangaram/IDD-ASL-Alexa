instructions to take out camera pin: https://www.youtube.com/watch?v=bWz1-wV8AU4

## Quick Start - Terminal Commands

### On Raspberry Pi

```bash
# Navigate to project directory
cd ~/IDD-ASL-Alexa

# Install dependencies (first time only)
pip install -r requirements.txt

# Run the button publisher
python3 mqtt_module.py
```

### On Laptop

```bash
# Navigate to project directory
cd ~/IDD-ASL-Alexa

# Install dependencies (first time only)
pip install -r requirements.txt

# Run the web dashboard server
python3 mqtt_hub.py

# The dashboard will be available at:
# http://localhost:5000
```

## Running the Scripts

### Setup

1. **Install dependencies** (on both Raspberry Pi and laptop):

```bash
pip install -r requirements.txt
```

**Note**: On your laptop, you can skip the Raspberry Pi hardware libraries. Install only MQTT:
```bash
pip install "paho-mqtt<2.0"
```

### Running on Raspberry Pi (`mqtt_module.py`)

This script reads button states from the MiniPiTFT and publishes them to MQTT.

```bash
python3 mqtt_module.py
```

**What it does:**
- Connects to the MQTT broker (default: `broker.hivemq.com`)
- Monitors button A (D23) and button B (D24) states continuously
- Publishes button states to the topic `IDD/button/state` only when state changes
- Press Ctrl+C to stop

### Running on Laptop (`mqtt_hub.py`)

This script runs a web server that subscribes to MQTT and displays button states in a web dashboard.

```bash
python3 mqtt_hub.py
```

**What it does:**
- Connects to the MQTT broker (default: `broker.hivemq.com`)
- Subscribes to the topic `IDD/button/state`
- Starts a web server on `http://localhost:5000`
- Serves a real-time dashboard showing button states
- Press Ctrl+C to stop

### Running Both Together

1. **Start the web dashboard on your laptop**:
   ```bash
   python3 mqtt_hub.py
   ```
   Then open your browser to: `http://localhost:5000`

2. **Start the module on Raspberry Pi** (to send messages):
   ```bash
   python3 mqtt_module.py
   ```

3. Press buttons on the Raspberry Pi and watch the state updates appear in real-time on the web dashboard!

## Web Dashboard

The `mqtt_hub.py` script includes a built-in web dashboard that visualizes button states in real-time.

**Features:**
- Real-time button state visualization
- Visual indicators (ON/OFF, PRESSED/RELEASED)
- Activity feed showing button event history
- Connection status indicator
- Responsive design for mobile and desktop
- No external dependencies - everything runs through the Python script

## MQTT Configuration for Home WiFi

The MQTT configuration now supports environment variables for easy switching between school and home networks.

### Option 1: Use a Public MQTT Broker (Easiest)

Set these environment variables before running:

```bash
export MQTT_BROKER='test.mosquitto.org'
export MQTT_USERNAME=''
export MQTT_PASSWORD=''
```

Or use HiveMQ's public broker:
```bash
export MQTT_BROKER='broker.hivemq.com'
export MQTT_USERNAME=''
export MQTT_PASSWORD=''
```

### Option 2: Use a Local MQTT Broker

If you have a Raspberry Pi or another device running Mosquitto on your home network:

1. Find the IP address of your MQTT broker (e.g., `192.168.1.100`)
2. Set the environment variable:
```bash
export MQTT_BROKER='192.168.1.100'
export MQTT_USERNAME='your_username'  # If authentication is required
export MQTT_PASSWORD='your_password'  # If authentication is required
```

### Option 3: Edit the Code Directly

You can also modify the default values in `mqtt_module.py` and `mqtt_hub.py` directly.

### Switching Back to School Network

Simply unset the environment variables or use:
```bash
export MQTT_BROKER='farlab.infosci.cornell.edu'
export MQTT_USERNAME='idd'
export MQTT_PASSWORD='device@theFarm'
```
