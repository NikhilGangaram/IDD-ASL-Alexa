#!/usr/bin/env python3
"""
Entry point for the Batman cave 3D room server.

Runs the existing Flask + Socket.IO MQTT hub and serves the immersive
3D visualization at `/3d-room`, keeping it in sync with gesture commands
from the Pi and dashboard.
"""

from mqtt.web_server import main as run_server


def main():
    """Launch the shared web server with the 3D room endpoint enabled."""
    run_server()


if __name__ == '__main__':
    main()

