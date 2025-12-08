import cv2
import time
import json
import sys
import math
import uuid
from collections import deque
import paho.mqtt.client as mqtt
from mqtt.config import MQTTConfig

# Optional display dependencies (Adafruit OLED)
DISPLAY_LIBS_AVAILABLE = False
try:
    import board
    import busio
    import adafruit_ssd1306
    from PIL import Image, ImageDraw, ImageFont
    DISPLAY_LIBS_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Display libraries not available ({e}); proceeding without screen output.")

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

class DisplayManager:
    """Minimal wrapper around the Adafruit OLED to show mode/action text."""
    def __init__(self):
        self.available = False
        self.last_lines = ()
        self.display_type = None  # "TFT" or "OLED"
        
        # Try PiTFT (1.14" ST7789) first, then fall back to the small OLED
        if self._init_pitft():
            return
        if self._init_oled():
            return
        
        print("[WARN] No display initialized; proceeding without screen output.")
    
    def _init_pitft(self):
        """Initialize Adafruit Mini PiTFT 1.14\" (ST7789 over SPI)."""
        try:
            import digitalio
            import adafruit_rgb_display.st7789 as st7789
            from PIL import Image, ImageDraw, ImageFont
            import board
        except ImportError:
            return False
        
        try:
            spi = board.SPI()
            tft_cs = digitalio.DigitalInOut(board.CE0)
            tft_dc = digitalio.DigitalInOut(board.D25)
            tft_reset = digitalio.DigitalInOut(board.D24)
            
            self.display = st7789.ST7789(
                spi,
                cs=tft_cs,
                dc=tft_dc,
                rst=tft_reset,
                baudrate=64_000_000,
                width=240,
                height=135,
                x_offset=53,
                y_offset=40,
                rotation=270,  # Matches PiTFT orientation when header is on the left
            )
            self.width = self.display.width
            self.height = self.display.height
            self.image = Image.new("RGB", (self.width, self.height))
            self.draw = ImageDraw.Draw(self.image)
            try:
                self.font = ImageFont.truetype("DejaVuSans.ttf", 20)
            except Exception:
                self.font = ImageFont.load_default()
            self.available = True
            self.display_type = "TFT"
            self.clear()
            print("[OK] PiTFT display initialized")
            return True
        except Exception as e:
            print(f"[WARN] Failed to initialize PiTFT display: {e}")
            return False
    
    def _init_oled(self):
        """Initialize 128x32 SSD1306 OLED over I2C."""
        if not DISPLAY_LIBS_AVAILABLE:
            return False
        
        try:
            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.display = adafruit_ssd1306.SSD1306_I2C(128, 32, self.i2c)
            self.width = self.display.width
            self.height = self.display.height
            self.image = Image.new("1", (self.width, self.height))
            self.draw = ImageDraw.Draw(self.image)
            try:
                self.font = ImageFont.truetype("DejaVuSans.ttf", 12)
            except Exception:
                self.font = ImageFont.load_default()
            self.available = True
            self.display_type = "OLED"
            self.clear()
            print("[OK] SSD1306 display initialized")
            return True
        except Exception as e:
            print(f"[WARN] Failed to initialize OLED display: {e}")
            self.available = False
            return False
    
    def clear(self):
        if not self.available:
            return
        if self.display_type == "TFT":
            self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
            self.display.image(self.image)
        else:
            self.display.fill(0)
            self.display.show()
        self.last_lines = ()
    
    def _format_line(self, text):
        return text.replace("_", " ")
    
    def show_lines(self, lines):
        """Render up to two lines on the OLED, skipping duplicate frames."""
        if not self.available:
            return
        
        # Normalize and deduplicate
        max_chars = 21 if self.display_type == "TFT" else 18
        norm_lines = tuple(self._format_line(line)[:max_chars] for line in lines[:2])
        if norm_lines == self.last_lines:
            return
        self.last_lines = norm_lines
        
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
        y = 0
        line_height = self.font.getbbox("A")[3] if hasattr(self.font, "getbbox") else self.font.getsize("A")[1]
        for line in norm_lines:
            self.draw.text((0, y), line, font=self.font, fill=255)
            y += line_height
        self.display.image(self.image)
        self.display.show()
    
    def show_intro(self):
        self.show_lines(["Gesture Control", "Select 1-4 fingers"])
    
    def show_mode_preview(self, mode):
        """Show the mode name while user holds up 1-4 fingers."""
        if not mode:
            return
        self.show_lines([mode.title(), "Hold to lock"])
    
    def show_mode_locked(self, mode):
        if not mode:
            return
        self.show_lines([f"Mode: {mode.title()}", "Waiting action..."])
    
    def show_action(self, mode, value):
        if not mode or not value:
            return
        mode_line = mode.title()
        value_line = value.upper()
        self.show_lines([mode_line, value_line])
    
    def show_timeout(self):
        self.show_lines(["Mode timeout", "Select 1-4 fingers"])

class GestureRecognizer:
    # Simplified __init__ - no arguments needed
    def __init__(self):
        # Camera mode is the only mode
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.72,
            min_tracking_confidence=0.65
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
        self.mode_buffer = deque(maxlen=9)  # Additional smoothing for mode selection
        self.action_buffer = deque(maxlen=5)  # Buffer for action gestures

    def _stable_from_buffer(self, buffer, min_samples=2, min_fraction=0.6):
        """Return the most common non-None value if it is stable enough."""
        from collections import Counter
        values = [v for v in buffer if v is not None]
        if len(values) < min_samples:
            return None

        counts = Counter(values)
        value, freq = counts.most_common(1)[0]
        if freq / len(values) >= min_fraction:
            return value
        return None

    def get_finger_count(self):
        """Detect and return the number of fingers held up (0-5)"""
        success, img = self.cap.read()
        if not success:
            return None

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands.process(img_rgb) 
        
        if not results.multi_hand_landmarks:
            self.mode_buffer.append(None)
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

        self.mode_buffer.append(total_fingers)
        stable_count = self._stable_from_buffer(self.mode_buffer, min_samples=3, min_fraction=0.55)
        return stable_count
    
    def get_action_gesture(self):
        """Detect action gestures: POINT_LEFT, POINT_RIGHT, OPEN_HAND, FIST
        Uses buffering to smooth out detection and reduce flickering
        """
        success, img = self.cap.read()
        if not success:
            return None

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands.process(img_rgb) 
        
        if not results.multi_hand_landmarks:
            self.action_buffer.append(None)
            return self._stable_from_buffer(self.action_buffer, min_samples=3, min_fraction=0.55)
        
        # Process first hand detected
        hand_lms = results.multi_hand_landmarks[0]
        lms = hand_lms.landmark
        
        # Check which fingers are open
        fingers = []
        fingers.append(1 if lms[8].y < lms[6].y else 0)   # Index
        fingers.append(1 if lms[12].y < lms[10].y else 0) # Middle
        fingers.append(1 if lms[16].y < lms[14].y else 0) # Ring
        fingers.append(1 if lms[20].y < lms[18].y else 0) # Pinky
        
        total_fingers = sum(fingers)
        
        # Check thumb
        thumb_extended = False
        if math.hypot(lms[4].x - lms[17].x, lms[4].y - lms[17].y) > 0.2:
            thumb_extended = True
        
        detected_gesture = None
        
        # Open Hand (5 fingers)
        if total_fingers == 4 and thumb_extended:
            detected_gesture = "OPEN_HAND"
        
        # Fist (0-1 fingers, thumb not extended)
        elif total_fingers <= 1 and not thumb_extended:
            detected_gesture = "FIST"
        
        # Pointing gestures (index finger extended)
        elif total_fingers == 1 and not thumb_extended:
            # Use multiple reference points for more robust detection
            index_tip = (lms[8].x, lms[8].y)
            index_pip = (lms[6].x, lms[6].y)  # Middle joint
            index_mcp = (lms[5].x, lms[5].y)  # Base knuckle
            wrist = (lms[0].x, lms[0].y)  # Wrist

            # Calculate direction vectors for stability checks
            tip_to_mcp_x = index_tip[0] - index_mcp[0]
            tip_to_mcp_y = index_tip[1] - index_mcp[1]
            tip_to_pip_x = index_tip[0] - index_pip[0]
            tip_to_pip_y = index_tip[1] - index_pip[1]
            wrist_to_tip_x = index_tip[0] - wrist[0]

            # Finger is extended when tip is clearly above its base
            finger_extended = tip_to_mcp_y < -0.04 and tip_to_pip_y < -0.02
            
            if finger_extended:
                # Weighted average of two direction measurements
                avg_delta_x = (tip_to_mcp_x * 0.6) + (tip_to_pip_x * 0.4)
                combined_x = (avg_delta_x * 0.65) + (wrist_to_tip_x * 0.35)
                
                # Pointing Left (from camera view, user's left)
                if combined_x > 0.025:
                    detected_gesture = "POINT_LEFT"
                # Pointing Right
                elif combined_x < -0.025:
                    detected_gesture = "POINT_RIGHT"
                # Neutral pointing defaults to right to keep behavior predictable
                elif abs(combined_x) < 0.025:
                    detected_gesture = "POINT_RIGHT"
        
        # Add to buffer
        self.action_buffer.append(detected_gesture)
        
        return self._stable_from_buffer(self.action_buffer, min_samples=3, min_fraction=0.6)
    
    def _get_most_common_gesture(self):
        """Get the most common gesture from the buffer, ignoring None values"""
        # Filter out None values
        valid_gestures = [g for g in self.action_buffer if g is not None]
        
        if not valid_gestures:
            return None
        
        # Return the most common gesture
        from collections import Counter
        gesture_counts = Counter(valid_gestures)
        most_common = gesture_counts.most_common(1)
        
        if most_common:
            return most_common[0][0]
        
        return None

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

class CommandMapper:
    """Maps mode + action to MQTT command"""
    
    def map_to_command(self, mode, action):
        """
        Map mode and action to command value.
        Returns: (action_name, value) or (None, None) if invalid combination
        """
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
    command_mapper = CommandMapper()
    mqtt_publisher = GestureMQTTPublisher()
    display = DisplayManager()
    display.show_intro()
    
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
    print("  Fist (0-1 fingers) -> Off/Close/Lock/AC Off")
    print("=" * 60)
    print("Press Ctrl+C to exit")
    print()
    
    # State variables
    mode_locked = False
    locked_mode = None
    latest_finger_count = None
    mode_lock_frames = 0
    mode_lock_threshold = 3  # Need consecutive frames to lock mode
    last_finger_count = None
    last_action = None
    last_action_time = 0
    mode_lock_time = 0  # Time when mode was locked
    action_cooldown = 0.45  # Seconds between distinct action commands
    slide_repeat_interval = 0.55  # How often to repeat LEFT/RIGHT while held
    slide_actions = {"POINT_LEFT", "POINT_RIGHT"}
    mode_timeout = 3.5  # Seconds before resetting to mode selection
    mode_relock_candidate = None
    mode_relock_frames = 0
    mode_relock_threshold = 3
    mode_relock_cooldown = 0.8
    last_mode_change_time = 0
    loop_tick = 0
    
    # Main loop
    try:
        while True:
            loop_tick += 1
            if not mode_locked:
                # MODE SELECTION PHASE
                finger_count = recognizer.get_finger_count()
                if finger_count is not None:
                    latest_finger_count = finger_count
                
                if finger_count is not None:
                    # Check if valid mode gesture (1-4 fingers)
                    if 1 <= finger_count <= 4:
                        # Show live preview of the mode on the display
                        preview_mode = mode_detector.finger_count_to_mode(finger_count)
                        display.show_mode_preview(preview_mode)
                        
                        # If same finger count as last frame, increment counter
                        if finger_count == last_finger_count:
                            mode_lock_frames += 1
                        else:
                            # New stable count detected
                            last_finger_count = finger_count
                            mode_lock_frames = 1

                        # Lock mode if held for enough frames
                        if mode_lock_frames >= mode_lock_threshold:
                            mode = mode_detector.finger_count_to_mode(finger_count)
                            mode_locked = True
                            locked_mode = mode
                            mode_lock_time = time.time()
                            print(f"\n[MODE LOCKED] {mode}")
                            print("[READY] Waiting for action gesture...")
                            display.show_mode_locked(mode)
                            mode_lock_frames = 0
                    else:
                        # Invalid finger count, reset
                        mode_lock_frames = 0
                        last_finger_count = None
                else:
                    # No hand detected; allow quick recovery without clearing preview
                    mode_lock_frames = 0
                    last_finger_count = None
            else:
                # ACTION DETECTION PHASE
                current_time = time.time()
                
                # Check for timeout - reset to mode selection after 2 seconds
                if (current_time - mode_lock_time) >= mode_timeout:
                    print(f"\n[TIMEOUT] Resetting to mode selection...")
                    mode_locked = False
                    locked_mode = None
                    last_action = None
                    mode_lock_frames = 0
                    last_finger_count = None
                    display.show_timeout()
                    print("[READY] Hold up 1-4 fingers to select mode...")
                    continue

                # Allow quick re-selection of mode without waiting for timeout
                if loop_tick % 3 == 0:
                    finger_count = recognizer.get_finger_count()
                    if finger_count is not None and 1 <= finger_count <= 4:
                        latest_finger_count = finger_count
                        if finger_count == mode_relock_candidate:
                            mode_relock_frames += 1
                        else:
                            mode_relock_candidate = finger_count
                            mode_relock_frames = 1

                        if (
                            mode_relock_frames >= mode_relock_threshold
                            and (current_time - last_mode_change_time) >= mode_relock_cooldown
                            and (current_time - last_action_time) >= 0.35
                        ):
                            new_mode = mode_detector.finger_count_to_mode(finger_count)
                            if new_mode and new_mode != locked_mode:
                                locked_mode = new_mode
                                mode_lock_time = current_time
                                last_mode_change_time = current_time
                                last_action = None
                                print(f"\n[MODE SWITCH] {new_mode}")
                                display.show_mode_locked(new_mode)
                                mode_relock_frames = 0
                                mode_relock_candidate = None
                                continue
                    else:
                        mode_relock_frames = 0
                        mode_relock_candidate = None
                
                action = recognizer.get_action_gesture()
                
                if action is not None:
                    is_slide = action in slide_actions
                    time_since_last = current_time - last_action_time
                    
                    should_fire = False
                    if last_action is None or action != last_action:
                        # Allow quick switching between different gestures
                        should_fire = time_since_last >= 0.12
                    elif is_slide and time_since_last >= slide_repeat_interval:
                        # Re-fire while holding LEFT/RIGHT for slider behavior
                        should_fire = True
                    
                    # Prevent spamming identical non-slide actions
                    if not is_slide and action == last_action:
                        should_fire = False

                    if should_fire:
                        print(f"[ACTION] {action}")
                        
                        # Map action to command
                        cmd_action, cmd_value = command_mapper.map_to_command(locked_mode, action)
                        
                        if cmd_action and cmd_value:
                            # Create command payload
                            command_data = {
                                "category": locked_mode,
                                "action": cmd_action,
                                "value": cmd_value,
                                "timestamp": time.strftime('%H:%M:%S'),
                                "finger_count": latest_finger_count
                            }
                            
                            # Publish to MQTT
                            if mqtt_publisher.publish_command(command_data):
                                print(f"[MQTT] Published: {locked_mode} -> {cmd_action} = {cmd_value}")
                                display.show_action(locked_mode, cmd_value)
                                last_action_time = current_time
                                # Reset timeout timer when action is detected
                                mode_lock_time = current_time
                        else:
                            print(f"[WARN] Invalid action '{action}' for mode '{locked_mode}'")
                        
                        last_action = action
                else:
                    # No action detected, reset last action
                    if last_action is not None:
                        last_action = None
            
            time.sleep(0.05) # Check every 50ms
            
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
        pass