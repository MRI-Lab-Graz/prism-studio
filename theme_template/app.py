import os
import sys
import webbrowser
import threading
import socket
from flask import Flask, render_template, jsonify, request
from waitress import serve

app = Flask(__name__)

# Basic Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Shutdown the Flask server when requested by the frontend."""
    print("Shutdown requested...")
    # This is a bit of a hack for Waitress/Flask but works for local apps
    # Alternatively, you can just sys.exit() if you don't need clean cleanup
    os._exit(0)
    return jsonify(success=True)

def find_free_port():
    """Find a free port on localhost."""
    with socket.socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM).type) as s:
        s.bind(('localhost', 0))
        return s.getsockname()[1]

def open_browser(url):
    """Wait for server to start and then open the browser."""
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()

if __name__ == '__main__':
    # Configuration
    port = 5001  # Or use find_free_port()
    host = '127.0.0.1'
    url = f'http://{host}:{port}'
    
    print(f" * Starting server at {url}")
    
    # Open browser in a separate thread
    open_browser(url)
    
    # Run with Waitress
    try:
        serve(app, host=host, port=port)
    except KeyboardInterrupt:
        print("\nStopping server...")
        sys.exit(0)
