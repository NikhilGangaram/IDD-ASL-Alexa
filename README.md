# IDD-ASL-Alexa

Viha Srinivas, Arya Prasad, Sachin Jojode, Nikhil Gangaram

A gesture-controlled smart home system that uses hand gestures to control devices via MQTT, with real-time dashboard updates.

1. Project plan: 

Big idea: ASL Alexa is a gesture-controlled smart home assistant that lets users control household devices using American Sign Language inspired hand gestures. Instead of voice commands, the system uses a camera and computer vision to recognize hand gestures and translate them into real-time smart home actions. This makes smart home technology more accessible for Deaf and hard-of-hearing users while also exploring hands-free interaction for everyone. 

Week 1: Define gestures and map them to smart home actions, Set up Python environment and MediaPipe hand tracking, Test basic gesture recognition with webcam

Week 2: Implement MQTT messaging with JSON commands, Connect gesture outputs to smart home modes (lights, temperature, etc.), Build basic web dashboard layout

Week 3: Add real-time dashboard updates using WebSockets, Refine gesture accuracy and reduce false triggers, User testing and debugging

Week 4: Final polish and documentation, Prepare demo flow and fallback options, Final presentation and submission

Parts needed: 
Hardware: Raspberry Pi (used as the smart-home controller), MicroSD card (for Raspberry Pi OS), Power supply for Raspberry Pi, USB webcam (for hand gesture recognition), Laptop (for development, testing, and running the dashboard), Monitor, HDMI cable, keyboard, and mouse (for Raspberry Pi setup)

Prototyping & Build Materials: Cardboard (to build the physical housing for the device), Clay (to secure components and shape the enclosure), Tape or glue (to hold structure together)

Connectivity: Wi-Fi connection, MQTT broker access (HiveMQ public broke

Fall-Back Plan:
- If gesture recognition becomes unreliable, switch to keyboard controls that simulate gestures
- If MQTT broker fails, log commands locally and display them only on the dashboard
- If WebSocket live updates break, refresh dashboard manually to show latest state
- If camera fails, use pre-recorded gesture inputs for demo purposes

2. Documentation of design process
- Identified the problem that most smart home assistants rely on voice input, which limits accessibility for Deaf and hard-of-hearing users
- Defined the main goal as creating a gesture-based smart home assistant inspired by ASL
- Brainstormed and sketched different hand gestures and mapped them to common smart home actions
- Chose simple, distinct gestures to reduce confusion and improve recognition accuracy
- Built an early technical prototype using a webcam and MediaPipe to test real-time hand tracking
- Tested multiple gestures and adjusted or removed ones that were frequently misclassified
- Set up the system architecture using a Raspberry Pi as the controller and MQTT for messaging
- Developed a web dashboard to visualize commands and device states in real time
- Used the dashboard to debug gesture recognition and system communication
- Created a low-fidelity physical enclosure using cardboard and clay
- Iterated on camera placement and component layout to improve stability and gesture detection
- Conducted end-to-end testing of the full system
- Documented failures and defined fallback plans to ensure the demo would still work

3. Archive
The following files together represent the complete archive of the final design. Each file is documented such that the project could be fully recreated from scratch.

### Gesture Recognition & Control Logic
- **View this:** `gesture_controller.py`  
  Core hand gesture detection logic using MediaPipe. Maps recognized gestures to smart home modes and actions.
- **View this:** `gesture_controller_2.py`  
  Iterated version of the gesture controller with refined logic and bug fixes.

### MQTT Messaging & Command Publishing
- **View this:** `publish.py`  
  Merges gesture recognition with MQTT publishing and sends structured JSON commands to the MQTT broker.

### Dashboard & System Visualization
- **View this:** `dashboard.py`  
  Web-based dashboard that subscribes to MQTT messages and displays real-time smart home state updates.

### 3D / Visual Room Representation
- **View this:** `batman_room_3d.py`  
  Controls the interactive 3D room environment and applies gesture-triggered updates.
- **View this:** `batman_room_3d.html`  
  Frontend visualization for the 3D room.
- **View this:** `README_3d_room.md`  
  Documentation explaining how the 3D room is configured and executed.

### Environment & Dependencies
- **View this:** `requirements.txt`  
  Lists all Python libraries required to install and run the project.

### Reproducibility Note
Together, these files document the full system pipeline—from gesture input and computer vision processing

## Features

- **Gesture Control**: Use hand gestures to control temperature, lights, blinds, and doors
- **MQTT Integration**: Commands published as JSON to MQTT broker
- **Real-time Dashboard**: Web dashboard updates instantly via WebSocket
- **Camera-based**: Uses MediaPipe for hand gesture recognition

### Prerequisites

- Python 3.8 - 3.11 (MediaPipe requirement)
- Webcam
- MQTT broker access (default: public HiveMQ broker)

### Installation

```bash
# Clone repository
git clone <repository-url>
cd IDD-ASL-Alexa

# Create virtual environment (recommended)
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Run

**Terminal 1 - Start Dashboard:**
```bash
python3 dashboard.py
```
Open browser to `http://localhost:8080`

**Terminal 2 - Start Gesture Controller:**
```bash
python3 publish.py
```

## Gestures

### Mode Selection (Hold up fingers)
- **1 Finger** → Temperature 🌡️
- **2 Fingers** → Lights 💡
- **3 Fingers** → Blinds 🪟
- **4 Fingers** → Door 🚪

### Actions (After selecting mode)
- **Open Hand** 🖐️ → Turn On / Open / Unlock
- **Fist** ✊ → Turn Off / Close / Lock
- **Point Right** 👉 → Increase / Brighten
- **Point Left** 👈 → Decrease / Dim

## Configuration

### MQTT Settings

Set environment variables or edit `mqtt/config.py`:

```bash
export MQTT_BROKER='broker.hivemq.com'
export MQTT_PORT='1883'
export MQTT_TOPIC='IDD/button/state'
export MQTT_USERNAME=''  # Optional
export MQTT_PASSWORD=''  # Optional
```

### School Network (Cornell)

```bash
export MQTT_BROKER='farlab.infosci.cornell.edu'
export MQTT_USERNAME='idd'
export MQTT_PASSWORD='device@theFarm'
```

### Web Server Port

```bash
export PORT='8080'  # Default: 8080
```

## Project Structure

```
IDD-ASL-Alexa/
├── gesture_controller.py    # Gesture recognition & MQTT publisher
├── publish.py                # Entry point for gesture controller
├── dashboard.py              # Entry point for web dashboard
├── mqtt/
│   ├── config.py            # MQTT configuration
│   ├── publisher.py         # Legacy button publisher
│   ├── subscriber.py        # MQTT subscriber & state manager
│   ├── web_server.py        # Flask web server
│   └── templates/
│       └── dashboard.html   # Web dashboard UI
└── requirements.txt         # Python dependencies
```

## How It Works

1. **Gesture Recognition**: Camera captures hand gestures using MediaPipe
2. **Command Processing**: Gestures mapped to category (temp/lights/blinds/door) and action (on/off/up/down)
3. **MQTT Publishing**: Commands packaged as JSON and published to MQTT topic
4. **Dashboard Display**: Web dashboard subscribes to MQTT, receives commands, and updates UI in real-time

## Troubleshooting

**Camera not working:**
- Check camera permissions
- Ensure camera is not in use by another application

**Gestures not recognized:**
- Ensure good lighting
- Keep hand visible and well-lit
- Try adjusting distance from camera

**MQTT connection failed:**
- Check broker hostname and port
- Verify network connectivity
- Check firewall settings

**Port already in use:**
```bash
PORT=8081 python3 dashboard.py
```

Design Patterns:
### Physical Form Exploration

Early: 
<img width="507" height="410" alt="Screen Shot 2025-12-14 at 12 25 12 PM" src="https://github.com/user-attachments/assets/dba5b53b-ca12-48db-aa24-12de9cbb2f08" />

Final: 
![IMG_5254](https://github.com/user-attachments/assets/a59d0c44-cc42-4ed9-bfc9-afc4b40417d3)
![IMG_5255](https://github.com/user-attachments/assets/ed4d81df-efd6-4898-8229-0d0597f01668)
![IMG_5256](https://github.com/user-attachments/assets/1e8b259f-814b-4a13-bc17-e156e1077e38)

In the early stages of the project, we imagined ASL Alexa as something extremely soft and approachable. Our initial idea was to use felt as the primary material so the device would be lightweight, flexible, and easy for users to place anywhere on their wall. The felt concept emphasized comfort and accessibility, and it aligned with the idea that assistive technology should feel friendly rather than intimidating.

As the project evolved, however, we realized that the physical form also needed to communicate function and reliability. We wanted the device to feel less like a craft object and more like a purposeful piece of home technology—something users would intuitively treat the way they treat a thermostat or control panel. This shift led us toward a more rustic, device-like aesthetic that still felt warm but more intentional.

We moved toward a structured enclosure design that could be mounted on a wall and visually signal that it was an interactive system. The final form prioritizes clarity and stability: a fixed camera position for accurate gesture recognition, visible hardware elements that suggest how the system works, and a physical presence that fits naturally into a home environment. This evolution reflects a broader design pattern in the project—starting with softness and accessibility, then refining toward clarity, durability, and everyday usability.

5. Video of someone using our project:

6. Reflection

## Project Reflection

Working on ASL Alexa pushed us to think beyond technical implementation and focus on how accessibility, interaction, and physical form come together in a real-world system. What started as a technical experiment in hand gesture recognition gradually became a broader exploration of how non-voice interfaces can feel intuitive, trustworthy, and integrated into everyday life.

One of the biggest lessons from this project was how much iteration mattered. Early ideas that felt strong on paper—such as softer, more flexible materials or more complex gesture sets—often revealed limitations once we began testing them in practice. Gesture recognition required us to simplify interactions and prioritize reliability over novelty, while the physical prototype needed to communicate purpose and stability rather than just approachability.

We also learned the importance of designing across multiple layers at once. Decisions made in the computer vision pipeline affected MQTT messaging, which in turn influenced the dashboard design and physical enclosure. Seeing the system work end-to-end helped us better understand how small design choices compound across hardware, software, and user experience.

Finally, this project reinforced the value of accessibility-driven design. By centering Deaf and hard-of-hearing users from the start, we were able to question default assumptions about smart home technology and explore alternative interaction models. While the current prototype is not a complete consumer product, it demonstrates how gesture-based control can serve as a viable and inclusive interface when thoughtfully designed.

Overall, ASL Alexa represents both a functional prototype and a learning process—one that emphasized iteration, cross-disciplinary thinking, and the importance of designing technology that adapts to users rather than expecting users to adapt to technology.

## Team Contributions

### Viha Srinivas
- Led product development and experience framing with a focus on accessibility for Deaf and hard-of-hearing users  
- Defined the core interaction model, including gesture vocabulary, mode selection, and user flow  
- Guided design tradeoffs between gesture expressiveness and system reliability  
- Led final polish, demo preparation, and presentation structure  
- Shaped documentation and overall project narrative  

### Nikhil Gangaram
- Set up the initial project codebase and technical pipeline  
- Implemented the first working gesture recognition and control flow  
- Established early end-to-end functionality from camera input to system response  
- Provided the technical foundation for later iteration and refinement  

### Arya Prasad
- Fine-tuned gesture recognition logic to improve accuracy and reduce false triggers  
- Integrated gesture processing with MQTT messaging and system state updates  
- Co-developed the 3D room visualization to make system state changes visible and legible  
- Focused on end-to-end integration, testing, and system robustness  

### Sachin Jojode
- Collaborated on refining gesture-to-action mappings and interaction behavior  
- Co-implemented the 3D visualization layer with real-time response to gestures  
- Assisted with improving system responsiveness and feedback clarity  
- Testing and iteration across interaction scenarios
- Final documentation of backend and system architecture
