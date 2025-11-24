# ASL Smart Home Dashboard

A gesture-controlled smart home dashboard using Raspberry Pi (or Mac/PC) and a webcam.

## Features
- **Gesture Control**: Use hand gestures to control lights, temperature, blinds, and doors.
- **Real-time Dashboard**: Updates instantly via WebSockets.
- **Mock Mode**: Test without a camera using keyboard input.

## Installation

1.  **Install Python Dependencies**:
    > [!IMPORTANT]
    > MediaPipe requires Python 3.8 - 3.11. Python 3.13 is NOT supported.
    > Please create a virtual environment with a supported version:
    > `python3.11 -m venv venv`
    
    ```bash
    pip install opencv-python mediapipe websockets asyncio
    ```

2.  **Hardware**:
    -   Webcam (Logitech recommended)
    -   Computer (Mac/PC/Raspberry Pi)

## Usage

### 1. Start the Gesture Controller
Run the Python script to start the backend server and camera recognition.

**Normal Mode (Camera):**
```bash
python gesture_controller.py
```

**Mock Mode (Keyboard Testing):**
```bash
python gesture_controller.py --mock
```

### 2. Open the Dashboard
Open `asl-dashboard.html` in your web browser. It will automatically connect to the controller.

## Gestures

### Mode Selection
Hold up fingers to select a device category:
-   **1 Finger**: Temperature 🌡️
-   **2 Fingers**: Lights 💡
-   **3 Fingers**: Blinds 🪟
-   **4 Fingers**: Door 🚪

### Actions
Perform gestures to control the selected device:
-   **Open Hand** 🖐️: Turn On / Open / Unlock
-   **Fist** ✊: Turn Off / Close / Lock
-   **Point Right** 👉: Increase / Brighten / Up
-   **Point Left** 👈: Decrease / Dim / Down

## Troubleshooting
-   **Connection Failed**: Ensure `gesture_controller.py` is running.
-   **Camera not working**: Check camera permissions.
-   **Gestures not recognized**: Ensure good lighting and hand is visible.
