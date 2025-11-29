"""
Web Server - Flask application for button state dashboard

Serves the web dashboard and handles WebSocket connections for real-time updates.
"""

import os
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from .config import WebConfig
from .subscriber import ButtonSubscriber


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = WebConfig.SECRET_KEY
    socketio = SocketIO(app, cors_allowed_origins="*")
    
    # Initialize MQTT subscriber
    subscriber = ButtonSubscriber(socketio=socketio)
    
    @app.route('/')
    def index():
        """Serve the dashboard HTML"""
        return render_template('dashboard.html')
    
    @socketio.on('connect')
    def handle_connect():
        """Handle web client connection"""
        print('[OK] Web client connected')
        # Send current states to newly connected client
        emit('button_states', subscriber.get_states())
        emit('gesture_states', subscriber.get_gesture_states())
        emit('current_mode', {'mode': subscriber.get_current_mode()})
        emit('mqtt_status', {
            'connected': subscriber.mqtt_client is not None and subscriber.mqtt_client.is_connected()
        })
        # Send activity history
        history = subscriber.get_history()
        if history:
            emit('activity_history', history)
    
    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle web client disconnection"""
        print('[OK] Web client disconnected')
    
    def run_server():
        """Start the web server"""
        print("=" * 60)
        print("  MQTT Hub - Web Dashboard Server")
        print("=" * 60)
        
        if not subscriber.setup():
            print("[FAIL] Failed to setup MQTT. Exiting.")
            return
        
        print("=" * 60)
        print(f"  Starting web server on http://localhost:{WebConfig.PORT}")
        print("  Press Ctrl+C to exit")
        print("=" * 60)
        print()
        
        try:
            socketio.run(
                app,
                host=WebConfig.HOST,
                port=WebConfig.PORT,
                debug=WebConfig.DEBUG,
                allow_unsafe_werkzeug=True
            )
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        finally:
            subscriber.cleanup()
            print("[OK] MQTT client disconnected")
    
    return app, socketio, run_server


def main():
    """Entry point for web server"""
    app, socketio, run_server = create_app()
    run_server()


if __name__ == '__main__':
    main()

