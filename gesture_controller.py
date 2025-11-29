import cv2
import time
import asyncio
import websockets
import json
import argparse
import sys
import math
from collections import deque

try:
    # We keep MediaPipe import as it is necessary for the core functionality
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    # If MediaPipe isn't available, we cannot proceed, as mock mode is removed.
    print("Error: MediaPipe is required but not installed. Exiting.")
    sys.exit(1)

# Constants
WEBSOCKET_PORT = 8765
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
        self.mode = None # 'TEMPERATURE', 'LIGHTS', 'BLINDS', 'DOOR', 'SECURITY'
        self.last_action_time = 0
        self.cooldown = 1.0 # Seconds between actions

    def process_gesture(self, gesture):
        current_time = time.time()
        
        # Mode Selection
        if gesture == "ONE_FINGER":
            self.mode = "TEMPERATURE"
            return "MODE_CHANGED", "Temperature Mode Selected"
        elif gesture == "TWO_FINGERS":
            self.mode = "LIGHTS"
            return "MODE_CHANGED", "Lights Mode Selected"
        elif gesture == "THREE_FINGERS":
            self.mode = "BLINDS"
            return "MODE_CHANGED", "Blinds Mode Selected"
        elif gesture == "FOUR_FINGERS":
            self.mode = "DOOR"
            return "MODE_CHANGED", "Door Mode Selected"
            
        # Actions (with cooldown)
        if current_time - self.last_action_time < self.cooldown:
            return None, None

        if not self.mode:
            return None, "Select a mode first (1-3 fingers)"

        action = None
        cmd_key = None

        if gesture == "OPEN_HAND":
            if self.mode == "LIGHTS": cmd_key = "LIGHTS_ON"
            elif self.mode == "BLINDS": cmd_key = "BLINDS_OPEN"
            elif self.mode == "DOOR": cmd_key = "DOOR_UNLOCK"
            
        elif gesture == "FIST":
            if self.mode == "LIGHTS": cmd_key = "LIGHTS_OFF"
            elif self.mode == "BLINDS": cmd_key = "BLINDS_CLOSE"
            elif self.mode == "DOOR": cmd_key = "DOOR_LOCK"
            
        elif gesture == "POINT_RIGHT": # Increase / Up
            if self.mode == "TEMPERATURE": cmd_key = "TEMPERATURE_UP"
            elif self.mode == "LIGHTS": cmd_key = "LIGHTS_BRIGHT"
            
        elif gesture == "POINT_LEFT": # Decrease / Down
            if self.mode == "TEMPERATURE": cmd_key = "TEMPERATURE_DOWN"
            elif self.mode == "LIGHTS": cmd_key = "LIGHTS_DIM"
            
        if cmd_key:
            self.last_action_time = current_time
            return "COMMAND", cmd_key
            
        return None, None

# --- broadcast function remains unchanged ---

async def broadcast(connected_clients, message):
    if connected_clients:
        await asyncio.gather(*[client.send(message) for client in connected_clients])

async def main():
    # Removed all argparse setup and mock checks
    
    # Initialize components
    recognizer = GestureRecognizer() 
    logic = SmartHomeLogic()
    
    connected_clients = set()

    async def ws_handler(websocket):
        connected_clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            connected_clients.remove(websocket)

    print(f"Starting WebSocket server on port {WEBSOCKET_PORT}...")
    server = await websockets.serve(ws_handler, "localhost", WEBSOCKET_PORT)

    print("System Ready! (Running Camera in Headless Mode)")
    print("Controls:")
    print("  1 Finger: Temperature Mode")
    print("  2 Fingers: Lights Mode")
    print("  3 Fingers: Blinds Mode")
    print("  4 Fingers: Door Mode")
    print("  Open Hand: Turn On / Open")
    print("  Fist: Turn Off / Close")
    print("  Point Right: Increase")
    print("  Point Left: Decrease")
    
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
                    print(f"\nCOMMAND SENT: {data}")
                    msg = json.dumps({"type": "asl_command", "gesture": data})
                    await broadcast(connected_clients, msg)
            
            await asyncio.sleep(0.05) # Loop speed control
            
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        recognizer.close()
        server.close()
        await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass