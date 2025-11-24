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
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("Warning: MediaPipe not found. Only Mock Mode will be available.")

# Constants
WEBSOCKET_PORT = 8765
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

class GestureRecognizer:
    def __init__(self, mock_mode=False):
        self.mock_mode = mock_mode
        
        if not self.mock_mode and not MEDIAPIPE_AVAILABLE:
            print("Error: MediaPipe is required for camera mode but not installed.")
            print("Switching to Mock Mode automatically.")
            self.mock_mode = True

        if not self.mock_mode:
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.5
            )
            self.mp_draw = mp.solutions.drawing_utils
            self.cap = cv2.VideoCapture(0)
            self.cap.set(3, CAMERA_WIDTH)
            self.cap.set(4, CAMERA_HEIGHT)
        
        self.last_gesture = None
        self.gesture_buffer = deque(maxlen=5)  # For smoothing

    def get_gesture(self):
        if self.mock_mode:
            return self._get_mock_input()
        
        success, img = self.cap.read()
        if not success:
            return None

        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.hands.process(img_rgb)
        
        gesture = "NONE"
        
        if results.multi_hand_landmarks:
            for hand_lms in results.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(img, hand_lms, self.mp_hands.HAND_CONNECTIONS)
                gesture = self._analyze_hand(hand_lms)
        
        # Show camera feed with debug info
        cv2.putText(img, f"Gesture: {gesture}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.imshow("Smart Home Camera", img)
        cv2.waitKey(1)
        
        return gesture

    def _analyze_hand(self, landmarks):
        # Extract key landmarks
        # Tips: 4 (Thumb), 8 (Index), 12 (Middle), 16 (Ring), 20 (Pinky)
        # PIPs (Knuckles): 6, 10, 14, 18
        
        lms = landmarks.landmark
        
        # Check which fingers are open
        fingers = []
        
        # Thumb (check x coordinate relative to IP joint for simplicity in right hand, 
        # but for general use, checking if tip is far from palm center is better. 
        # Here we use a simple heuristic: is tip to the right of the knuckle? 
        # Assuming right hand facing camera: thumb is left of hand. 
        # Let's use a simpler distance based approach or y-check for other fingers)
        
        # Thumb is tricky, let's stick to 4 other fingers for counting first
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
        # If thumb is extended
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

    def _get_mock_input(self):
        # Non-blocking input check is hard in pure python console without curses
        # We'll rely on the main loop to handle mock input via separate thread or just random for now?
        # Actually, let's make it interactive in the console if possible, 
        # but for simplicity in this loop, we might just return None and handle input in the main loop
        return None

    def close(self):
        if not self.mock_mode:
            self.cap.release()
            cv2.destroyAllWindows()

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



async def broadcast(connected_clients, message):
    if connected_clients:
        await asyncio.gather(*[client.send(message) for client in connected_clients])

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Run in mock mode (keyboard input)")
    args = parser.parse_args()

    recognizer = GestureRecognizer(mock_mode=args.mock)
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

    print("System Ready!")
    print("Controls:")
    print("  1 Finger: Temperature Mode")
    print("  2 Fingers: Lights Mode")
    print("  3 Fingers: Blinds Mode")
    print("  4 Fingers: Door Mode")
    print("  Open Hand: Turn On / Open")
    print("  Fist: Turn Off / Close")
    print("  Point Right: Increase")
    print("  Point Left: Decrease")
    if args.mock:
        print("\nMOCK MODE ACTIVE. Type commands in console:")
        print("  '1', '2', '3', '4' for modes")
        print("  'o' (open), 'f' (fist), 'r' (right), 'l' (left) for actions")

    # Main loop
    # Since we need to run the camera loop and the websocket server, 
    # and input() is blocking, we have to be careful in mock mode.
    # For simplicity, we'll use a non-blocking loop for camera, 
    # but for mock mode input, we might need a separate thread or just use async input if possible.
    # To keep it simple and robust:
    
    try:
        if args.mock:
            # Simple input loop for mock mode
            loop = asyncio.get_running_loop()
            while True:
                cmd = await loop.run_in_executor(None, input, "Enter Mock Gesture (1-4, o, f, r, l): ")
                gesture = "UNKNOWN"
                if cmd == '1': gesture = "ONE_FINGER"
                elif cmd == '2': gesture = "TWO_FINGERS"
                elif cmd == '3': gesture = "THREE_FINGERS"
                elif cmd == '4': gesture = "FOUR_FINGERS"
                elif cmd == 'o': gesture = "OPEN_HAND"
                elif cmd == 'f': gesture = "FIST"
                elif cmd == 'r': gesture = "POINT_RIGHT"
                elif cmd == 'l': gesture = "POINT_LEFT"
                
                print(f"Detected Gesture: {gesture}")
                
                event_type, data = logic.process_gesture(gesture)
                
                if event_type == "MODE_CHANGED":
                    print(f"System: {data}")
                elif event_type == "COMMAND":
                    print(f"Action: {data}")
                    msg = json.dumps({"type": "asl_command", "gesture": data})
                    await broadcast(connected_clients, msg)
                    
        else:
            # Camera loop
            while True:
                gesture = recognizer.get_gesture()
                if gesture and gesture != "NONE" and gesture != "UNKNOWN":
                    # Simple debouncing could be added here
                    event_type, data = logic.process_gesture(gesture)
                    
                    if event_type == "MODE_CHANGED":
                        print(f"\rMode: {logic.mode}             ", end="")
                    elif event_type == "COMMAND":
                        print(f"\nCOMMAND SENT: {data}")
                        msg = json.dumps({"type": "asl_command", "gesture": data})
                        await broadcast(connected_clients, msg)
                
                await asyncio.sleep(0.05)
                
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
