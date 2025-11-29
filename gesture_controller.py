import cv2
import time
import json
import sys
import math
import uuid
from collections import deque
import paho.mqtt.client as mqtt
from mqtt.config import MQTTConfig

try:
    # We keep MediaPipe import as it is necessary for the core functionality
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    # If MediaPipe isn't available, we cannot proceed, as mock mode is removed.
    print("Error: MediaPipe is required but not installed. Exiting.")
    sys.exit(1)

# Constants
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

class GestureRecognizer:
    # Simplified __init__ - no arguments needed
    def __init__(self):
        # Camera mode is the only mode
        
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        # 0 is usually the default camera index
        self.cap = cv2.VideoCapture(0) 
        if not self.cap.isOpened():
            # Fatal error if camera fails to open
            raise IOError("Cannot open webcam. Ensure camera module is connected and enabled.")

        self.cap.set(3, CAMERA_WIDTH)
        self.cap.set(4, CAMERA_HEIGHT)
        
        self.last_gesture = None
        self.gesture_buffer = deque(maxlen=5)  # For smoothing

    def get_finger_count(self):
        """Detect and return the number of fingers held up (0-5)"""
        success, img = self.cap.read()
        if not success:
            return None

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands.process(img_rgb) 
        
        if not results.multi_hand_landmarks:
            return None
        
        # Process first hand detected
        hand_lms = results.multi_hand_landmarks[0]
        lms = hand_lms.landmark
        
        # Check which fingers are open
        fingers = []
        
        # Index - check if tip is above middle joint
        fingers.append(1 if lms[8].y < lms[6].y else 0)
        # Middle
        fingers.append(1 if lms[12].y < lms[10].y else 0)
        # Ring
        fingers.append(1 if lms[16].y < lms[14].y else 0)
        # Pinky
        fingers.append(1 if lms[20].y < lms[18].y else 0)
        
        total_fingers = sum(fingers)
        
        # Check thumb
        thumb_extended = False
        if math.hypot(lms[4].x - lms[17].x, lms[4].y - lms[17].y) > 0.2:
            thumb_extended = True
        
        # If thumb is extended, add it to count
        if thumb_extended:
            total_fingers += 1
        
        return total_fingers

    # Removed _get_mock_input
    
    def close(self):
        # No mock check needed
        self.cap.release()
        cv2.destroyAllWindows() 

# --- SmartHomeLogic class remains unchanged ---

class ModeDetector:
    """Simple mode detector - maps finger count to mode"""
    
    MODE_MAP = {
        1: "TEMPERATURE",
        2: "LIGHTS",
        3: "BLINDS",
        4: "DOOR"
    }
    
    def finger_count_to_mode(self, finger_count):
        """Convert finger count (1-4) to mode name"""
        return self.MODE_MAP.get(finger_count)

class GestureMQTTPublisher:
    """Publishes gesture commands to MQTT"""
    
    def __init__(self):
        self.mqtt_client = None
        
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            print(f'[OK] MQTT connected to {MQTTConfig.BROKER}:{MQTTConfig.PORT}')
            print(f'[OK] Publishing to {MQTTConfig.TOPIC}')
        else:
            print(f'[FAIL] MQTT connection failed: {rc}')
    
    def on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        pass
    
    def setup_mqtt(self):
        """Setup and connect MQTT client"""
        try:
            client_id = f"{MQTTConfig.CLIENT_ID_PREFIX}-gesture-{str(uuid.uuid1())}"
            self.mqtt_client = mqtt.Client(client_id)
            
            if MQTTConfig.USERNAME and MQTTConfig.PASSWORD:
                self.mqtt_client.username_pw_set(MQTTConfig.USERNAME, MQTTConfig.PASSWORD)
            
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_publish = self.on_publish
            
            self.mqtt_client.connect(MQTTConfig.BROKER, port=MQTTConfig.PORT, keepalive=MQTTConfig.KEEPALIVE)
            self.mqtt_client.loop_start()
            
            time.sleep(1)
            return True
        except Exception as e:
            print(f'[WARN] MQTT setup failed: {e}')
            return False
    
    def publish_command(self, command_data):
        """Publish gesture command to MQTT"""
        payload = {
            'type': 'gesture_command',
            'category': command_data.get('category'),
            'action': command_data.get('action'),
            'value': command_data.get('value'),
            'timestamp': command_data.get('timestamp')
        }
        result = self.mqtt_client.publish(MQTTConfig.TOPIC, json.dumps(payload))
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[{command_data.get('timestamp')}] COMMAND: {command_data.get('category')} -> {command_data.get('action')} = {command_data.get('value')}")
            return True
        else:
            print(f"[ERROR] Failed to publish command: rc={result.rc}")
            return False
    
    def cleanup(self):
        """Cleanup resources"""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()

def main():
    # Initialize components
    recognizer = GestureRecognizer() 
    mode_detector = ModeDetector()
    
    print("=" * 60)
    print("  Gesture Controller - Mode Detection Test")
    print("=" * 60)
    print("Hold up 1-4 fingers to select mode:")
    print("  1 Finger -> Temperature Mode")
    print("  2 Fingers -> Lights Mode")
    print("  3 Fingers -> Blinds Mode")
    print("  4 Fingers -> Door Mode")
    print("=" * 60)
    print("Press Ctrl+C to exit")
    print()
    
    last_mode = None
    
    # Main loop - just detect and print mode
    try:
        while True:
            finger_count = recognizer.get_finger_count()
            
            if finger_count is not None:
                # Only process mode gestures (1-4 fingers)
                if 1 <= finger_count <= 4:
                    mode = mode_detector.finger_count_to_mode(finger_count)
                    
                    # Only print if mode changed
                    if mode != last_mode:
                        print(f"[MODE] {mode} (Detected {finger_count} finger{'s' if finger_count > 1 else ''})")
                        last_mode = mode
                else:
                    # Reset if finger count is not 1-4
                    if last_mode is not None:
                        print("[MODE] None (Waiting for mode selection...)")
                        last_mode = None
            
            time.sleep(0.1) # Check every 100ms
            
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        recognizer.close()
        print("[OK] Camera released")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
        pass