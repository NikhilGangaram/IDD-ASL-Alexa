#!/usr/bin/env python3
"""
Entry point for button publisher (Raspberry Pi)

Run this script on the Raspberry Pi to publish button states to MQTT.
"""

from mqtt.publisher import main

if __name__ == '__main__':
    main()

