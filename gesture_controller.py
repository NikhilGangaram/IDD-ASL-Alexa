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
            min_detection_confidence=0.5,  # Lowered for better detection
            min_tracking_confidence=0.3    # Lowered for better tracking
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
        self.finger_count_buffer = deque(maxlen=40)  # Support up to 2 seconds at 20 FPS
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
        """Calculate hand scale based on palm dimensions for dynamic thresholds"""
        if not self.hand_landmarks:
            return 0.15

        lms = self.hand_landmarks.landmark

        # More robust hand scale calculation
        # Use distance from wrist to middle finger MCP (palm height)
        wrist = np.array([lms[0].x, lms[0].y])
        middle_mcp = np.array([lms[9].x, lms[9].y])
        palm_height = np.linalg.norm(middle_mcp - wrist)

        # Use distance between index and pinky MCPs (palm width)
        index_mcp = np.array([lms[5].x, lms[5].y])
        pinky_mcp = np.array([lms[17].x, lms[17].y])
        palm_width = np.linalg.norm(pinky_mcp - index_mcp)

        # Also consider the span from thumb to pinky
        thumb_cmc = np.array([lms[1].x, lms[1].y])
        pinky_cmc = np.array([lms[17].x, lms[17].y])
        hand_span = np.linalg.norm(pinky_cmc - thumb_cmc)

        # Return average of these measurements for more stable scaling
        return (palm_height + palm_width + hand_span) / 3

    def get_finger_count(self):
        """Detect and return the stabilized number of fingers held up (0-5)"""
        if not self.hand_landmarks:
            self.finger_count_buffer.append(None)
            return self._get_stable_finger_count()

        lms = self.hand_landmarks.landmark
        fingers = []

        # Robust finger detection using vector-based approach
        # Check if fingertip is extended beyond the middle joint (works with different orientations)
        finger_indices = [
            (8, 7, 6, 5),   # Index: tip, DIP, PIP, MCP
            (12, 11, 10, 9), # Middle: tip, DIP, PIP, MCP
            (16, 15, 14, 13), # Ring: tip, DIP, PIP, MCP
            (20, 19, 18, 17)  # Pinky: tip, DIP, PIP, MCP
        ]

        for tip_idx, dip_idx, pip_idx, mcp_idx in finger_indices:
            # Calculate vectors from MCP to PIP and PIP to tip
            mcp_to_pip_x = lms[pip_idx].x - lms[mcp_idx].x
            mcp_to_pip_y = lms[pip_idx].y - lms[mcp_idx].y
            pip_to_tip_x = lms[tip_idx].x - lms[pip_idx].x
            pip_to_tip_y = lms[tip_idx].y - lms[pip_idx].y

            # Calculate the angle between the two vectors
            dot_product = mcp_to_pip_x * pip_to_tip_x + mcp_to_pip_y * pip_to_tip_y
            mag1 = math.hypot(mcp_to_pip_x, mcp_to_pip_y)
            mag2 = math.hypot(pip_to_tip_x, pip_to_tip_y)

            if mag1 > 0 and mag2 > 0:
                cos_angle = dot_product / (mag1 * mag2)
                cos_angle = max(-1, min(1, cos_angle))  # Clamp to avoid numerical issues
                angle = math.acos(cos_angle)

                # Finger is extended if the angle is small (finger is relatively straight)
                finger_extended = angle < math.pi / 3  # ~60 degrees
            else:
                # Fallback to simple distance check if vectors are too small
                tip_to_pip_dist = math.hypot(pip_to_tip_x, pip_to_tip_y)
                finger_extended = tip_to_pip_dist > 0.05  # Arbitrary threshold

            fingers.append(1 if finger_extended else 0)

        total_fingers = sum(fingers)

        # Improved thumb detection - more reliable approach
        thumb_extended = False

        # Method 1: Check if thumb tip is far from thumb base (simplified)
        thumb_base_to_tip = math.hypot(lms[4].x - lms[2].x, lms[4].y - lms[2].y)
        hand_scale = self.get_hand_scale()
        thumb_threshold = hand_scale * 0.6  # More reasonable threshold

        # Method 2: Check if thumb tip is positioned away from palm center
        palm_center_x = (lms[0].x + lms[9].x) / 2
        palm_center_y = (lms[0].y + lms[9].y) / 2
        thumb_to_palm_center = math.hypot(lms[4].x - palm_center_x, lms[4].y - palm_center_y)

        # Method 3: Check relative position to index finger
        thumb_vs_index = math.hypot(lms[4].x - lms[5].x, lms[4].y - lms[5].y)

        # Thumb is extended if ANY of these conditions are met (more lenient)
        if (thumb_base_to_tip > thumb_threshold or
            thumb_to_palm_center > hand_scale * 0.8 or
            thumb_vs_index > hand_scale * 0.4):
            thumb_extended = True

        if thumb_extended:
            total_fingers += 1

        self.finger_count_buffer.append(total_fingers)
        return self._get_stable_finger_count()
    
    def _get_stable_finger_count(self):
        """Get stabilized finger count from buffer with different timing requirements"""
        valid_counts = [c for c in self.finger_count_buffer if c is not None]
        if not valid_counts:
            return None
        
        # Get the most recent stable count for analysis
        count_freq = Counter(valid_counts)
        most_common = count_freq.most_common(1)[0]
        detected_count = most_common[0]

        # Same stability requirements for all finger counts (0.5 seconds)
        stability_window = 10  # 0.5 seconds at 20 FPS
        max_stable_frames = 10
        min_frames_required = 8  # Require at least 8 valid frames

        if len(valid_counts) < min_frames_required:
            return None

        # Check if recent frames are consistent
        recent_counts = valid_counts[-stability_window:]
        if len(set(recent_counts)) == 1 and len(recent_counts) >= stability_window:
            self.finger_count_stable_frames = min(self.finger_count_stable_frames + 1, max_stable_frames)
        else:
            self.finger_count_stable_frames = 0
        
        return detected_count
    
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
                stability_required = 8  # Same for all fingers now
                stability_percent = min(100, int((self.finger_count_stable_frames / stability_required) * 100))
                stability_indicator = "*" * min(self.finger_count_stable_frames, 10)  # Limit display length

                # Add hand scale info for debugging
                hand_scale = self.get_hand_scale()
                cv2.putText(img, f"Fingers: {detected_fingers} {stability_indicator} ({stability_percent}%)",
                           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                y_offset += 30
                cv2.putText(img, f"Scale: {hand_scale:.3f} | Conf: {self.detection_confidence:.2f}",
                           (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
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
    
    def reset_camera(self):
        """Reset camera state and clear buffers for fresh detection"""
        print("[CAMERA] Resetting camera state...")

        # Clear all detection buffers and state
        self.finger_count_buffer.clear()
        self.action_buffer.clear()
        self.finger_count_stable_frames = 0
        self.current_frame = None
        self.hand_landmarks = None
        self.last_gesture = None
        self.detection_confidence = 0.0

        # Reinitialize MediaPipe hands for fresh detection
        try:
            self.hands.close()
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.3
            )
            print("[CAMERA] MediaPipe hands reinitialized")
        except Exception as e:
            print(f"[WARN] Could not reinitialize MediaPipe: {e}")

        print("[CAMERA] Reset complete")

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

    # Stability requirements for mode locking based on finger count
    def get_stability_requirement(finger_count):
        """Get required stable frames for mode locking - same for all finger counts"""
        return 8  # All fingers require ~0.4 seconds of stability
    
    # Main loop
    try:
        while True:
            if not recognizer.process_frame():
                time.sleep(0.05)
                continue
            
            finger_count = recognizer.get_finger_count()
            action_gesture = recognizer.get_action_gesture()

            # Debug: Print detection status every few frames
            if hasattr(recognizer, '_debug_counter'):
                recognizer._debug_counter = (recognizer._debug_counter + 1) % 30  # Every ~1.5 seconds at 20 FPS
            else:
                recognizer._debug_counter = 0

            if recognizer._debug_counter == 0:
                hand_status = "DETECTED" if recognizer.hand_landmarks else "NOT DETECTED"
                print(f"[DEBUG] Hand {hand_status} | Fingers: {finger_count} | Confidence: {recognizer.detection_confidence:.2f}")
            
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
                        stability_required = get_stability_requirement(finger_count)
                        if finger_count == last_finger_count and recognizer.finger_count_stable_frames >= stability_required:
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

                    # Reset camera for fresh detection
                    recognizer.reset_camera()

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