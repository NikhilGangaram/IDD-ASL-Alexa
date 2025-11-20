instructions to take out camera pin: https://www.youtube.com/watch?v=bWz1-wV8AU4

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
