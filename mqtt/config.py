"""
MQTT Configuration

Centralized configuration for MQTT broker settings.
Can be overridden with environment variables.
"""

import os


class MQTTConfig:
    """MQTT broker configuration"""
    
    # Broker settings
    BROKER = os.getenv('MQTT_BROKER', 'broker.hivemq.com')
    PORT = int(os.getenv('MQTT_PORT', '1883'))
    TOPIC = os.getenv('MQTT_TOPIC', 'IDD/button/state')
    USERNAME = os.getenv('MQTT_USERNAME', '')
    PASSWORD = os.getenv('MQTT_PASSWORD', '')
    
    # Connection settings
    KEEPALIVE = 60
    CLIENT_ID_PREFIX = 'button-monitor'
    
    @classmethod
    def get_broker_info(cls):
        """Get broker connection info"""
        return {
            'broker': cls.BROKER,
            'port': cls.PORT,
            'topic': cls.TOPIC,
            'has_auth': bool(cls.USERNAME and cls.PASSWORD)
        }


class ButtonConfig:
    """Button hardware configuration (Raspberry Pi only)"""
    
    # GPIO pins for buttons
    BUTTON_A_PIN = 'D23'
    BUTTON_B_PIN = 'D24'


class WebConfig:
    """Web server configuration"""
    
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', '8080'))
    SECRET_KEY = os.getenv('SECRET_KEY', 'button-dashboard-secret-key')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

