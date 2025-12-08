"""
gesture_controller_2.py

Drop-in, more robust gesture controller with explicit mode state machine and
smoothing. Keeps existing MQTT payload shape and default topic so downstream
("Batman room") consumers continue to work.
"""

import cv2
import time
import json
import sys
import math
import uuid
from collections import deque, Counter

import paho.mqtt.client as mqtt
from mqtt.config import MQTTConfig

# Optional display support (same libraries as gesture_controller.py if present)
DISPLAY_LIBS_AVAILABLE = False
try:
    import board
    import busio
    import adafruit_ssd1306
    from PIL import Image, ImageDraw, ImageFont
    DISPLAY_LIBS_AVAILABLE = True
except Exception:
    # Display is optional; continue without screen output
    pass

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    print("Error: MediaPipe is required but not installed. Exiting.")
    sys.exit(1)

# --- Tunable constants (grouped for quick tweaking) ---
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# Detection confidence
MIN_DETECTION_CONFIDENCE = 0.72
MIN_TRACKING_CONFIDENCE = 0.65

# Mode selection
MODE_HOLD_FRAMES = 5          # consecutive stable frames to lock a mode
MODE_BUFFER_SIZE = 12         # smoothing window for finger counts
MODE_TIMEOUT = 5.0            # seconds before returning to selection
MODE_EXIT_PINCH_HOLD = 1.0    # seconds pinch must be held to exit mode

# Action handling
ACTION_BUFFER_SIZE = 7
ACTION_STABLE_MIN = 3
ACTION_STABLE_FRACTION = 0.6
ACTION_COOLDOWN = 0.4
SLIDE_REPEAT_INTERVAL = 0.55  # allow repeated LEFT/RIGHT while held

# Gesture thresholds
THUMB_INDEX_PINCH_DIST = 0.045
POINT_X_THRESH = 0.025
# Require fingers to be farther above the PIP to count as "up" to avoid false positives
FINGER_TIP_ABOVE_DELTA = -0.06
# Stricter thumb extension to prevent phantom counts
THUMB_EXTENDED_X_MIN = 0.035
THUMB_INDEX_BASE_DIST = 0.08

# Frame pacing
FRAME_SLEEP = 0.05


class DisplayManager:
    """Minimal OLED helper; safe to use when libs/hardware are absent."""

    def __init__(self):
        self.available = False
        self.width = 0
        self.height = 0
        self.last_lines = ()

        if not DISPLAY_LIBS_AVAILABLE:
            return

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
            self.clear()
            print("[OK] SSD1306 display initialized")
        except Exception as e:
            print(f"[WARN] Display unavailable: {e}")
            self.available = False

    def clear(self):
        if not self.available:
            return
        self.display.fill(0)
        self.display.show()
        self.last_lines = ()

    def show_lines(self, lines):
        if not self.available:
            return
        norm = tuple(str(line)[:18] for line in lines[:2])
        if norm == self.last_lines:
            return
        self.last_lines = norm
        self.draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
        y = 0
        line_height = self.font.getbbox("A")[3] if hasattr(self.font, "getbbox") else self.font.getsize("A")[1]
        for line in norm:
            self.draw.text((0, y), line, font=self.font, fill=255)
            y += line_height
        self.display.image(self.image)
        self.display.show()

    def show_intro(self):
        self.show_lines(["Gesture Control", "Select 1-4 fingers"])

    def show_mode_preview(self, mode):
        if mode:
            self.show_lines([mode.title(), "Hold to lock"])

    def show_mode_locked(self, mode):
        if mode:
            self.show_lines([f"Mode: {mode.title()}", "Ready for action"])

    def show_action(self, mode, value):
        if mode and value:
            self.show_lines([mode.title(), value.upper()])

    def show_timeout(self):
        self.show_lines(["Mode timeout", "Select 1-4 fingers"])


class RollingValue:
    """Utility for temporal smoothing."""

    def __init__(self, maxlen):
        self.buffer = deque(maxlen=maxlen)

    def add(self, value):
        self.buffer.append(value)

    def stable_value(self, min_samples=3, min_fraction=0.6):
        values = [v for v in self.buffer if v is not None]
        if len(values) < min_samples:
            return None
        counts = Counter(values)
        val, freq = counts.most_common(1)[0]
        if freq / len(values) >= min_fraction:
            return val
        return None


class GestureRecognizer:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
        )
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise IOError("Cannot open webcam. Ensure camera module is connected and enabled.")

        self.cap.set(3, CAMERA_WIDTH)
        self.cap.set(4, CAMERA_HEIGHT)

        self.mode_buffer = RollingValue(MODE_BUFFER_SIZE)
        self.action_buffer = RollingValue(ACTION_BUFFER_SIZE)

    def close(self):
        self.cap.release()
        cv2.destroyAllWindows()

    def _read_frame_landmarks(self):
        success, frame = self.cap.read()
        if not success:
            return None, None
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(img_rgb)
        if not results.multi_hand_landmarks:
            return frame, None
        return frame, results.multi_hand_landmarks[0]

    # --- Finger utilities ---
    def _finger_is_up(self, lms, tip_idx, pip_idx):
        return lms[tip_idx].y - lms[pip_idx].y < FINGER_TIP_ABOVE_DELTA

    def _thumb_is_extended(self, lms):
        # Compare thumb tip to index MCP along x for direction robustness
        return (
            abs(lms[4].x - lms[3].x) > THUMB_EXTENDED_X_MIN
            and math.hypot(lms[4].x - lms[5].x, lms[4].y - lms[5].y) > THUMB_INDEX_BASE_DIST
        )

    def get_finger_count(self):
        _, hand_lms = self._read_frame_landmarks()
        if hand_lms is None:
            self.mode_buffer.add(None)
            return None

        lms = hand_lms.landmark
        fingers = [
            self._finger_is_up(lms, 8, 6),   # index
            self._finger_is_up(lms, 12, 10), # middle
            self._finger_is_up(lms, 16, 14), # ring
            self._finger_is_up(lms, 20, 18), # pinky
        ]
        total = sum(1 for f in fingers if f)
        if self._thumb_is_extended(lms):
            total += 1

        self.mode_buffer.add(total)
        return self.mode_buffer.stable_value(min_samples=3, min_fraction=0.55)

    def _detect_pinch(self, lms):
        dist = math.hypot(lms[4].x - lms[8].x, lms[4].y - lms[8].y)
        return dist < THUMB_INDEX_PINCH_DIST

    def get_action_gesture(self):
        _, hand_lms = self._read_frame_landmarks()
        if hand_lms is None:
            self.action_buffer.add(None)
            return self.action_buffer.stable_value(ACTION_STABLE_MIN, ACTION_STABLE_FRACTION)

        lms = hand_lms.landmark
        thumb_extended = self._thumb_is_extended(lms)

        finger_up = {
            "index": self._finger_is_up(lms, 8, 6),
            "middle": self._finger_is_up(lms, 12, 10),
            "ring": self._finger_is_up(lms, 16, 14),
            "pinky": self._finger_is_up(lms, 20, 18),
        }
        total = sum(1 for v in finger_up.values() if v) + (1 if thumb_extended else 0)

        detected = None

        if self._detect_pinch(lms):
            detected = "PINCH"
        elif total == 1 and thumb_extended and not any(finger_up.values()):
            # Thumb-up only to switch modes (avoids 2-finger conflict with lights)
            detected = "MODE_SWITCH"
        elif total >= 4 and thumb_extended:
            detected = "OPEN_HAND"
        elif total <= 1 and not thumb_extended:
            detected = "FIST"
        elif total == 1 and not thumb_extended:
            # pointing
            index_tip = (lms[8].x, lms[8].y)
            index_pip = (lms[6].x, lms[6].y)
            index_mcp = (lms[5].x, lms[5].y)
            wrist = (lms[0].x, lms[0].y)

            tip_to_mcp_x = index_tip[0] - index_mcp[0]
            tip_to_pip_x = index_tip[0] - index_pip[0]
            wrist_to_tip_x = index_tip[0] - wrist[0]

            # Weighted average for stability
            combined_x = (tip_to_mcp_x * 0.6) + (tip_to_pip_x * 0.3) + (wrist_to_tip_x * 0.1)
            if combined_x > POINT_X_THRESH:
                detected = "POINT_LEFT"
            elif combined_x < -POINT_X_THRESH:
                detected = "POINT_RIGHT"
            else:
                detected = "POINT_RIGHT"

        self.action_buffer.add(detected)
        return self.action_buffer.stable_value(ACTION_STABLE_MIN, ACTION_STABLE_FRACTION)


class ModeDetector:
    MODE_MAP = {
        1: "TEMPERATURE",
        2: "LIGHTS",
        3: "BLINDS",
        4: "DOOR",
    }

    def finger_count_to_mode(self, count):
        return self.MODE_MAP.get(count)


class CommandMapper:
    def map_to_command(self, mode, action):
        if mode == "TEMPERATURE":
            if action == "OPEN_HAND":
                return ("TEMPERATURE", "AC_ON")
            if action == "FIST":
                return ("TEMPERATURE", "AC_OFF")
            if action == "POINT_RIGHT":
                return ("TEMPERATURE", "UP")
            if action == "POINT_LEFT":
                return ("TEMPERATURE", "DOWN")

        elif mode == "LIGHTS":
            if action == "OPEN_HAND":
                return ("LIGHTS", "ON")
            if action == "FIST":
                return ("LIGHTS", "OFF")
            if action == "POINT_RIGHT":
                return ("LIGHTS", "BRIGHT")
            if action == "POINT_LEFT":
                return ("LIGHTS", "DIM")

        elif mode == "BLINDS":
            if action == "OPEN_HAND":
                return ("BLINDS", "OPEN")
            if action == "FIST":
                return ("BLINDS", "CLOSE")
            if action == "POINT_RIGHT":
                return ("BLINDS", "OPEN")  # slide right to open more
            if action == "POINT_LEFT":
                return ("BLINDS", "CLOSE") # slide left to close more

        elif mode == "DOOR":
            if action == "OPEN_HAND":
                return ("DOOR", "UNLOCK")
            if action == "FIST":
                return ("DOOR", "LOCK")

        return (None, None)


class GestureMQTTPublisher:
    def __init__(self):
        self.mqtt_client = None

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f'[OK] MQTT connected to {MQTTConfig.BROKER}:{MQTTConfig.PORT}')
            print(f'[OK] Publishing to {MQTTConfig.TOPIC}')
        else:
            print(f'[FAIL] MQTT connection failed: {rc}')

    def on_publish(self, client, userdata, mid):
        pass

    def setup_mqtt(self):
        try:
            client_id = f"{MQTTConfig.CLIENT_ID_PREFIX}-gesture2-{str(uuid.uuid1())}"
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
        payload = {
            'type': 'gesture_command',
            'category': command_data.get('category'),
            'action': command_data.get('action'),
            'value': command_data.get('value'),
            'timestamp': command_data.get('timestamp'),
            'finger_count': command_data.get('finger_count'),
        }
        result = self.mqtt_client.publish(MQTTConfig.TOPIC, json.dumps(payload))
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[{command_data.get('timestamp')}] COMMAND: {payload['category']} -> {payload['action']} = {payload['value']}")
            return True
        else:
            print(f"[ERROR] Failed to publish command: rc={result.rc}")
            return False

    def cleanup(self):
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()


def main():
    recognizer = GestureRecognizer()
    mode_detector = ModeDetector()
    command_mapper = CommandMapper()
    mqtt_publisher = GestureMQTTPublisher()
    display = DisplayManager()
    display.show_intro()

    print("=" * 60)
    print("  Gesture Controller 2 - Robust Mode Locking")
    print("=" * 60)

    if not mqtt_publisher.setup_mqtt():
        print("[FAIL] Failed to setup MQTT. Exiting.")
        return

    mode_locked = False
    locked_mode = None
    last_action = None
    last_action_time = 0
    mode_lock_frames = 0
    last_finger_count = None
    mode_lock_time = 0
    pinch_start_time = None

    try:
        while True:
            if not mode_locked:
                finger_count = recognizer.get_finger_count()
                if finger_count is None:
                    mode_lock_frames = 0
                    last_finger_count = None
                    time.sleep(FRAME_SLEEP)
                    continue

                if 1 <= finger_count <= 4:
                    preview_mode = mode_detector.finger_count_to_mode(finger_count)
                    display.show_mode_preview(preview_mode)

                    if finger_count == last_finger_count:
                        mode_lock_frames += 1
                    else:
                        mode_lock_frames = 1
                        last_finger_count = finger_count

                    if mode_lock_frames >= MODE_HOLD_FRAMES:
                        locked_mode = mode_detector.finger_count_to_mode(finger_count)
                        if locked_mode:
                            mode_locked = True
                            mode_lock_time = time.time()
                            print(f"\n[MODE LOCKED] {locked_mode}")
                            print("[READY] Waiting for action gesture...")
                            display.show_mode_locked(locked_mode)
                        mode_lock_frames = 0
                else:
                    mode_lock_frames = 0
                    last_finger_count = None

            else:
                current_time = time.time()
                # Timeout back to selection
                if (current_time - mode_lock_time) >= MODE_TIMEOUT:
                    print(f"\n[TIMEOUT] Resetting to mode selection...")
                    display.show_timeout()
                    mode_locked = False
                    locked_mode = None
                    last_action = None
                    pinch_start_time = None
                    time.sleep(FRAME_SLEEP)
                    continue

                action = recognizer.get_action_gesture()

                # Exit / switch via pinch held
                if action == "PINCH":
                    if pinch_start_time is None:
                        pinch_start_time = current_time
                    elif (current_time - pinch_start_time) >= MODE_EXIT_PINCH_HOLD:
                        print("[EXIT] Pinch detected, returning to mode selection.")
                        mode_locked = False
                        locked_mode = None
                        last_action = None
                        pinch_start_time = None
                        display.show_intro()
                        time.sleep(FRAME_SLEEP)
                        continue
                else:
                    pinch_start_time = None

                # Explicit mode switch gesture (two fingers up)
                if action == "MODE_SWITCH":
                    print("[EXIT] Two-finger switch gesture, returning to mode selection.")
                    mode_locked = False
                    locked_mode = None
                    last_action = None
                    pinch_start_time = None
                    display.show_intro()
                    time.sleep(FRAME_SLEEP)
                    continue

                if action is not None and action != "PINCH":
                    is_slide = action in {"POINT_LEFT", "POINT_RIGHT"}
                    time_since_last = current_time - last_action_time

                    should_fire = False
                    if last_action is None or action != last_action:
                        should_fire = time_since_last >= ACTION_COOLDOWN
                    elif is_slide and time_since_last >= SLIDE_REPEAT_INTERVAL:
                        should_fire = True

                    if should_fire:
                        cmd_action, cmd_value = command_mapper.map_to_command(locked_mode, action)
                        if cmd_action and cmd_value:
                            payload = {
                                "category": locked_mode,
                                "action": cmd_action,
                                "value": cmd_value,
                                "timestamp": time.strftime('%H:%M:%S'),
                                "finger_count": recognizer.mode_buffer.stable_value()  # best-effort info
                            }
                            if mqtt_publisher.publish_command(payload):
                                display.show_action(locked_mode, cmd_value)
                                last_action_time = current_time
                                mode_lock_time = current_time  # keep session alive when actions occur
                        else:
                            print(f"[WARN] Invalid action '{action}' for mode '{locked_mode}'")

                        last_action = action

            time.sleep(FRAME_SLEEP)

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

# Gesture set:
#   - Mode selection: hold 1/2/3/4 fingers steady (stable frames) to lock TEMPERATURE/LIGHTS/BLINDS/DOOR.
#   - Actions: OPEN_HAND (on/open/unlock), FIST (off/close/lock), POINT_LEFT/RIGHT (down/dim/close vs up/bright/open),
#              PINCH (thumb-index pinch) held for exit/switch.
# Mode logic:
#   - Mode locks after MODE_HOLD_FRAMES stable readings; stays locked until explicit pinch exit or inactivity timeout.
#   - Actions are debounced with temporal smoothing and cooldown; slide actions can repeat while held.
# Assumptions/limits:
#   - Single hand, front-facing camera. Good lighting improves landmark stability.
#   - Pinch exit chosen to avoid collisions with existing open/fist actions.

