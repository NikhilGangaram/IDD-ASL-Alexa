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

    def get_gesture(self):
        # Always use camera (no mock check)
        success, img = self.cap.read()
        if not success:
            return None

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands.process(img_rgb) 
        
        gesture = "NONE"
        
        if results.multi_hand_landmarks:
            for hand_lms in results.multi_hand_landmarks:
                # No drawing needed for headless operation
                gesture = self._analyze_hand(hand_lms)
        
        # No display code here (fully headless)
        
        return gesture

    def _analyze_hand(self, landmarks):
        lms = landmarks.landmark
        
        # Check which fingers are open
        fingers = []
        
        # Index
        fingers.append(1 if lms[8].y < lms[6].y else 0)
        # Middle
        fingers.append(1 if lms[12].y < lms[10].y else 0)
        # Ring
        fingers.append(1 if lms[16].y < lms[14].y else 0)
        # Pinky
        fingers.append(1 if lms[20].y < lms[18].y else 0)
        
        total_fingers = sum(fingers)
        
        # Thumb check for "Open Hand" vs "Point"
        thumb_extended = False
        # Simple check: distance from tip to pinky knuckle (17) is large
        if math.hypot(lms[4].x - lms[17].x, lms[4].y - lms[17].y) > 0.2:
            thumb_extended = True

        # Gesture Logic
        
        # Mode Selection Gestures (Holding up fingers)
        if total_fingers == 1 and not thumb_extended: # Index only
            return "ONE_FINGER"
        if total_fingers == 2 and not thumb_extended: # Index + Middle
            return "TWO_FINGERS"
        if total_fingers == 3 and not thumb_extended: # Index + Middle + Ring
            return "THREE_FINGERS"
        if total_fingers == 4: # 4 fingers
            return "FOUR_FINGERS"
            
        # Action Gestures
        
        # Open Hand (5 fingers)
        if total_fingers == 4 and thumb_extended:
            return "OPEN_HAND"
            
        # Fist (0 fingers)
        if total_fingers == 0 and not thumb_extended:
            return "FIST"
            
        # Pointing (Index finger only, but check direction)
        if total_fingers == 1:
            # Check x direction of index finger
            # If tip is significantly to the right/left of the knuckle
            if lms[8].x > lms[6].x + 0.05: # Pointing Left (from camera view, it's user's left)
                return "POINT_LEFT"
            if lms[8].x < lms[6].x - 0.05: # Pointing Right
                return "POINT_RIGHT"
                
        return "UNKNOWN"

    # Removed _get_mock_input
    
    def close(self):
        # No mock check needed
        self.cap.release()
        cv2.destroyAllWindows() 

# --- SmartHomeLogic class remains unchanged ---

class SmartHomeLogic:
    def __init__(self):
        self.mode = None # 'TEMPERATURE', 'LIGHTS', 'BLINDS', 'DOOR'
        self.last_action_time = 0
        self.cooldown = 1.0 # Seconds between actions

    def process_gesture(self, gesture):
        current_time = time.time()
        
        # Mode Selection
        if gesture == "ONE_FINGER":
            self.mode = "TEMPERATURE"
            return "MODE_CHANGED", {"category": "TEMPERATURE", "message": "Temperature Mode Selected"}
        elif gesture == "TWO_FINGERS":
            self.mode = "LIGHTS"
            return "MODE_CHANGED", {"category": "LIGHTS", "message": "Lights Mode Selected"}
        elif gesture == "THREE_FINGERS":
            self.mode = "BLINDS"
            return "MODE_CHANGED", {"category": "BLINDS", "message": "Blinds Mode Selected"}
        elif gesture == "FOUR_FINGERS":
            self.mode = "DOOR"
            return "MODE_CHANGED", {"category": "DOOR", "message": "Door Mode Selected"}
            
        # Actions (with cooldown)
        if current_time - self.last_action_time < self.cooldown:
            return None, None

        if not self.mode:
            return None, None

        # Map gestures to actions and values
        action = None
        value = None

        if gesture == "OPEN_HAND":
            if self.mode == "LIGHTS": 
                action = "LIGHTS"
                value = "ON"
            elif self.mode == "BLINDS": 
                action = "BLINDS"
                value = "OPEN"
            elif self.mode == "DOOR": 
                action = "DOOR"
                value = "UNLOCK"
            
        elif gesture == "FIST":
            if self.mode == "LIGHTS": 
                action = "LIGHTS"
                value = "OFF"
            elif self.mode == "BLINDS": 
                action = "BLINDS"
                value = "CLOSE"
            elif self.mode == "DOOR": 
                action = "DOOR"
                value = "LOCK"
            
        elif gesture == "POINT_RIGHT": # Increase / Up
            if self.mode == "TEMPERATURE": 
                action = "TEMPERATURE"
                value = "UP"
            elif self.mode == "LIGHTS": 
                action = "LIGHTS"
                value = "BRIGHT"
            
        elif gesture == "POINT_LEFT": # Decrease / Down
            if self.mode == "TEMPERATURE": 
                action = "TEMPERATURE"
                value = "DOWN"
            elif self.mode == "LIGHTS": 
                action = "LIGHTS"
                value = "DIM"
            
        if action and value:
            self.last_action_time = current_time
            return "COMMAND", {
                "category": self.mode,
                "action": action,
                "value": value,
                "timestamp": time.strftime('%H:%M:%S')
            }
            
        return None, None

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
    logic = SmartHomeLogic()
    mqtt_publisher = GestureMQTTPublisher()
    
    print("=" * 60)
    print("  Gesture Controller - MQTT Publisher")
    print("=" * 60)
    
    # Setup MQTT
    if not mqtt_publisher.setup_mqtt():
        print("[FAIL] Failed to setup MQTT. Exiting.")
        return
    
    print("=" * 60)
    print("System Ready! (Running Camera in Headless Mode)")
    print("Controls:")
    print("  1 Finger: Temperature Mode")
    print("  2 Fingers: Lights Mode")
    print("  3 Fingers: Blinds Mode")
    print("  4 Fingers: Door Mode")
    print("  Open Hand: Turn On / Open / Unlock")
    print("  Fist: Turn Off / Close / Lock")
    print("  Point Right: Increase / Brighten")
    print("  Point Left: Decrease / Dim")
    print("=" * 60)
    print("Press Ctrl+C to exit")
    print()
    
    # Main loop (Camera only)
    try:
        while True:
            gesture = recognizer.get_gesture()
            if gesture and gesture != "NONE" and gesture != "UNKNOWN":
                event_type, data = logic.process_gesture(gesture)
                
                if event_type == "MODE_CHANGED":
                    # Use sys.stdout.write for smooth, single-line printing without print() overhead
                    sys.stdout.write(f"\rMode: {logic.mode}             ")
                    sys.stdout.flush()
                elif event_type == "COMMAND":
                    mqtt_publisher.publish_command(data)
            
            time.sleep(0.05) # Loop speed control
            
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        recognizer.close()
        mqtt_publisher.cleanup()
        print("[OK] MQTT client disconnected")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass