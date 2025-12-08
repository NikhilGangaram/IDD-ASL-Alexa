import cv2
import time
import json
import sys
import math
import uuid
from collections import deque, Counter
import paho.mqtt.client as mqtt
from mqtt.config import MQTTConfig
import numpy as np
import os

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    print("Error: MediaPipe is required but not installed. Exiting.")
    sys.exit(1)

# Constants
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# Auto-detect if we can display GUI (disable if running headless/SSH)
def check_display_available():
    """Check if we can display GUI windows"""
    if os.environ.get('SSH_CONNECTION'):
        return False
    if not os.environ.get('DISPLAY'):
        return False
    return True

DEBUG_OVERLAY = check_display_available()  # Auto-detect based on environment

class GestureRecognizer:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils
        
        self.cap = cv2.VideoCapture(0) 
        if not self.cap.isOpened():
            raise IOError("Cannot open webcam. Ensure camera module is connected and enabled.")

        self.cap.set(3, CAMERA_WIDTH)
        self.cap.set(4, CAMERA_HEIGHT)
        
        # State management
        self.current_frame = None
        self.hand_landmarks = None
        self.last_gesture = None
        self.finger_count_buffer = deque(maxlen=5)
        self.action_buffer = deque(maxlen=3)
        
        # Confidence tracking
        self.detection_confidence = 0.0
        self.finger_count_stable_frames = 0
        self.debug_enabled = DEBUG_OVERLAY  # Instance variable instead of global

    def process_frame(self):
        """Read and process a single frame, storing results for all detection methods"""
        success, img = self.cap.read()
        if not success:
            self.current_frame = None
            self.hand_landmarks = None
            return False
        
        self.current_frame = img
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands.process(img_rgb)
        
        if results.multi_hand_landmarks and len(results.multi_hand_landmarks) > 0:
            self.hand_landmarks = results.multi_hand_landmarks[0]
            if results.multi_handedness:
                self.detection_confidence = results.multi_handedness[0].classification[0].score
            else:
                self.detection_confidence = 0.7
        else:
            self.hand_landmarks = None
            self.detection_confidence = 0.0
        
        return True

    def get_hand_scale(self):
        """Calculate hand scale based on palm width for dynamic thresholds"""
        if not self.hand_landmarks:
            return 0.15
        
        lms = self.hand_landmarks.landmark
        wrist = (lms[0].x, lms[0].y)
        middle_mcp = (lms[9].x, lms[9].y)
        palm_height = math.hypot(middle_mcp[0] - wrist[0], middle_mcp[1] - wrist[1])
        
        index_mcp = (lms[5].x, lms[5].y)
        pinky_mcp = (lms[17].x, lms[17].y)
        palm_width = math.hypot(pinky_mcp[0] - index_mcp[0], pinky_mcp[1] - index_mcp[1])
        
        return (palm_height + palm_width) / 2

    def get_finger_count(self):
        """Detect and return the stabilized number of fingers held up (0-5)"""
        if not self.hand_landmarks:
            self.finger_count_buffer.append(None)
            return self._get_stable_finger_count()
        
        lms = self.hand_landmarks.landmark
        fingers = []
        
        # Check which fingers are open
        fingers.append(1 if lms[8].y < lms[7].y else 0)   # Index
        fingers.append(1 if lms[12].y < lms[11].y else 0) # Middle
        fingers.append(1 if lms[16].y < lms[15].y else 0) # Ring
        fingers.append(1 if lms[20].y < lms[19].y else 0) # Pinky
        
        total_fingers = sum(fingers)
        
        # Dynamic thumb detection using hand scale
        hand_scale = self.get_hand_scale()
        thumb_threshold = hand_scale * 1.3
        
        thumb_extended = False
        thumb_distance = math.hypot(lms[4].x - lms[17].x, lms[4].y - lms[17].y)
        if thumb_distance > thumb_threshold:
            thumb_extended = True
        
        if thumb_extended:
            total_fingers += 1
        
        self.finger_count_buffer.append(total_fingers)
        return self._get_stable_finger_count()
    
    def _get_stable_finger_count(self):
        """Get stabilized finger count from buffer"""
        valid_counts = [c for c in self.finger_count_buffer if c is not None]
        if not valid_counts:
            return None
        
        if len(valid_counts) < 3:
            return None
        
        count_freq = Counter(valid_counts)
        most_common = count_freq.most_common(1)[0]
        
        if len(set(valid_counts[-3:])) == 1:
            self.finger_count_stable_frames = min(self.finger_count_stable_frames + 1, 5)
        else:
            self.finger_count_stable_frames = 0
        
        return most_common[0]
    
    def get_action_gesture(self):
        """Detect action gestures with fixed logic order"""
        if not self.hand_landmarks:
            self.action_buffer.append(None)
            return self._get_most_common_gesture()
        
        lms = self.hand_landmarks.landmark
        
        fingers = []
        fingers.append(1 if lms[8].y < lms[7].y else 0)   # Index
        fingers.append(1 if lms[12].y < lms[11].y else 0) # Middle
        fingers.append(1 if lms[16].y < lms[15].y else 0) # Ring
        fingers.append(1 if lms[20].y < lms[19].y else 0) # Pinky
        
        total_fingers = sum(fingers)
        
        hand_scale = self.get_hand_scale()
        thumb_threshold = hand_scale * 1.3
        
        thumb_extended = False
        thumb_distance = math.hypot(lms[4].x - lms[17].x, lms[4].y - lms[17].y)
        if thumb_distance > thumb_threshold:
            thumb_extended = True
        
        detected_gesture = None
        
        # Check in correct order
        if total_fingers == 4 and thumb_extended:
            detected_gesture = "OPEN_HAND"
        elif total_fingers == 1 and fingers[0] == 1 and not thumb_extended:
            # Only index finger is up
            index_tip = lms[8]
            index_mcp = lms[5]
            wrist = lms[0]
            
            tip_to_mcp_x = index_tip.x - index_mcp.x
            tip_to_wrist_x = index_tip.x - wrist.x
            avg_delta_x = (tip_to_mcp_x * 0.6 + tip_to_wrist_x * 0.4)
            
            point_threshold = hand_scale * 0.2
            
            if avg_delta_x > point_threshold:
                detected_gesture = "POINT_RIGHT"
            elif avg_delta_x < -point_threshold:
                detected_gesture = "POINT_LEFT"
            else:
                detected_gesture = "POINT_RIGHT"
        elif total_fingers == 0:
            detected_gesture = "FIST"
        
        self.action_buffer.append(detected_gesture)
        return self._get_most_common_gesture()
    
    def _get_most_common_gesture(self):
        """Get the most common gesture from the buffer"""
        valid_gestures = [g for g in self.action_buffer if g is not None]
        if not valid_gestures:
            return None
        
        gesture_counts = Counter(valid_gestures)
        most_common = gesture_counts.most_common(1)
        
        if most_common:
            return most_common[0][0]
        return None

    def draw_debug_overlay(self, mode_phase, locked_mode, detected_fingers, detected_action):
        """Draw debug information on the frame"""
        if self.current_frame is None or not self.debug_enabled:
            return
        
        try:
            img = self.current_frame.copy()
            
            if self.hand_landmarks:
                self.mp_draw.draw_landmarks(img, self.hand_landmarks, 
                                           self.mp_hands.HAND_CONNECTIONS)
            
            y_offset = 30
            
            cv2.putText(img, f"Mode: {mode_phase}", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            y_offset += 30
            
            if locked_mode:
                cv2.putText(img, f"Locked: {locked_mode}", (10, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                y_offset += 30
            
            if detected_fingers is not None:
                stability_indicator = "*" * self.finger_count_stable_frames
                cv2.putText(img, f"Fingers: {detected_fingers} {stability_indicator}", 
                           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            else:
                cv2.putText(img, "Fingers: None", (10, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
            y_offset += 30
            
            if detected_action:
                cv2.putText(img, f"Action: {detected_action}", (10, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            y_offset += 30
            
            conf_percent = int(self.detection_confidence * 100)
            cv2.putText(img, f"Confidence: {conf_percent}%", (10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
            
            cv2.imshow('Gesture Control Debug', img)
            cv2.waitKey(1)
        except Exception as e:
            # If display fails, disable debug overlay for this instance
            self.debug_enabled = False
            print(f"[INFO] Debug overlay disabled: {e}")
    
    def close(self):
        self.cap.release()
        if self.debug_enabled:
            try:
                cv2.destroyAllWindows()
            except:
                pass


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


class CommandMapper:
    """Maps mode + action to MQTT command"""
    
    def map_to_command(self, mode, action):
        """Map mode and action to command value"""
        if mode == "TEMPERATURE":
            if action == "OPEN_HAND":
                return ("TEMPERATURE", "AC_ON")
            elif action == "FIST":
                return ("TEMPERATURE", "AC_OFF")
            elif action == "POINT_RIGHT":
                return ("TEMPERATURE", "UP")
            elif action == "POINT_LEFT":
                return ("TEMPERATURE", "DOWN")
        
        elif mode == "LIGHTS":
            if action == "OPEN_HAND":
                return ("LIGHTS", "ON")
            elif action == "FIST":
                return ("LIGHTS", "OFF")
            elif action == "POINT_RIGHT":
                return ("LIGHTS", "BRIGHT")
            elif action == "POINT_LEFT":
                return ("LIGHTS", "DIM")
        
        elif mode == "BLINDS":
            if action == "OPEN_HAND":
                return ("BLINDS", "OPEN")
            elif action == "FIST":
                return ("BLINDS", "CLOSE")
        
        elif mode == "DOOR":
            if action == "OPEN_HAND":
                return ("DOOR", "UNLOCK")
            elif action == "FIST":
                return ("DOOR", "LOCK")
        
        return (None, None)


class GestureMQTTPublisher:
    """Publishes gesture commands and telemetry to MQTT"""
    
    def __init__(self):
        self.mqtt_client = None
        self.last_telemetry_time = 0
        self.telemetry_interval = 0.1
        
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
    
    def publish_telemetry(self, telemetry_data):
        """Publish gesture telemetry to MQTT"""
        current_time = time.time()
        if current_time - self.last_telemetry_time < self.telemetry_interval:
            return False
        
        self.last_telemetry_time = current_time
        
        payload = {
            'type': 'gesture_telemetry',
            'mode_phase': telemetry_data.get('mode_phase'),
            'locked_mode': telemetry_data.get('locked_mode'),
            'finger_count': telemetry_data.get('finger_count'),
            'action_gesture': telemetry_data.get('action_gesture'),
            'confidence': telemetry_data.get('confidence'),
            'timestamp': telemetry_data.get('timestamp')
        }
        
        result = self.mqtt_client.publish(MQTTConfig.TOPIC, json.dumps(payload))
        return result.rc == mqtt.MQTT_ERR_SUCCESS
    
    def cleanup(self):
        """Cleanup resources"""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


def main():
    # Initialize components
    recognizer = GestureRecognizer() 
    mode_detector = ModeDetector()
    command_mapper = CommandMapper()
    mqtt_publisher = GestureMQTTPublisher()
    
    print("=" * 60)
    print("  Gesture Controller - MQTT Publisher")
    print("=" * 60)
    
    # Setup MQTT
    if not mqtt_publisher.setup_mqtt():
        print("[FAIL] Failed to setup MQTT. Exiting.")
        return
    
    print("=" * 60)
    print("STEP 1: Hold up 1-4 fingers to select mode:")
    print("  1 Finger -> Temperature Mode")
    print("  2 Fingers -> Lights Mode")
    print("  3 Fingers -> Blinds Mode")
    print("  4 Fingers -> Door Mode")
    print()
    print("STEP 2: Once mode is locked, use action gestures:")
    print("  Point Left -> Decrease/Dim/Down")
    print("  Point Right -> Increase/Brighten/Up")
    print("  Open Hand (5 fingers) -> On/Open/Unlock/AC On")
    print("  Fist (0 fingers) -> Off/Close/Lock/AC Off")
    print("=" * 60)
    print("Debug overlay: " + ("ENABLED" if recognizer.debug_enabled else "DISABLED (no display)"))
    print("Press Ctrl+C to exit")
    print()
    
    # State variables
    mode_phase = "SELECT_MODE"
    locked_mode = None
    mode_lock_frames = 0
    mode_lock_threshold = 5
    last_finger_count = None
    last_action = None
    last_action_time = 0
    mode_lock_time = 0
    action_cooldown = 0.5
    mode_timeout = 5.0
    
    # Main loop
    try:
        while True:
            if not recognizer.process_frame():
                time.sleep(0.05)
                continue
            
            finger_count = recognizer.get_finger_count()
            action_gesture = recognizer.get_action_gesture()
            
            # Send telemetry
            telemetry = {
                'mode_phase': mode_phase,
                'locked_mode': locked_mode,
                'finger_count': finger_count,
                'action_gesture': action_gesture if mode_phase == "LOCKED_MODE" else None,
                'confidence': recognizer.detection_confidence,
                'timestamp': time.strftime('%H:%M:%S')
            }
            mqtt_publisher.publish_telemetry(telemetry)
            
            # Draw debug overlay (will skip if no display)
            recognizer.draw_debug_overlay(
                mode_phase, 
                locked_mode,
                finger_count,
                action_gesture if mode_phase == "LOCKED_MODE" else None
            )
            
            if mode_phase == "SELECT_MODE":
                if finger_count is not None:
                    if 1 <= finger_count <= 4:
                        if finger_count == last_finger_count and recognizer.finger_count_stable_frames >= 3:
                            mode_lock_frames += 1
                            
                            if mode_lock_frames >= mode_lock_threshold:
                                mode = mode_detector.finger_count_to_mode(finger_count)
                                mode_phase = "LOCKED_MODE"
                                locked_mode = mode
                                mode_lock_time = time.time()
                                print(f"\n[MODE LOCKED] {mode}")
                                print("[READY] Waiting for action gesture...")
                                mode_lock_frames = 0
                        else:
                            mode_lock_frames = 0
                            last_finger_count = finger_count
                    else:
                        mode_lock_frames = 0
                        last_finger_count = None
                        
            elif mode_phase == "LOCKED_MODE":
                current_time = time.time()
                
                if (current_time - mode_lock_time) >= mode_timeout:
                    print(f"\n[TIMEOUT] Resetting to mode selection...")
                    mode_phase = "SELECT_MODE"
                    locked_mode = None
                    last_action = None
                    mode_lock_frames = 0
                    last_finger_count = None
                    print("[READY] Hold up 1-4 fingers to select mode...")
                    continue
                
                if action_gesture is not None:
                    if action_gesture != last_action and (current_time - last_action_time) >= action_cooldown:
                        print(f"[ACTION] {action_gesture}")
                        
                        cmd_action, cmd_value = command_mapper.map_to_command(locked_mode, action_gesture)
                        
                        if cmd_action and cmd_value:
                            command_data = {
                                "category": locked_mode,
                                "action": cmd_action,
                                "value": cmd_value,
                                "timestamp": time.strftime('%H:%M:%S')
                            }
                            
                            if mqtt_publisher.publish_command(command_data):
                                print(f"[MQTT] Published: {locked_mode} -> {cmd_action} = {cmd_value}")
                                last_action_time = current_time
                                mode_lock_time = current_time
                        else:
                            print(f"[WARN] Invalid action '{action_gesture}' for mode '{locked_mode}'")
                        
                        last_action = action_gesture
                else:
                    if last_action is not None:
                        last_action = None
            
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n\nStopping...")
    finally:
        recognizer.close()
        mqtt_publisher.cleanup()
        print("[OK] Camera released")
        print("[OK] MQTT client disconnected")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass