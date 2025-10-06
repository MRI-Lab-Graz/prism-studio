#!/usr/bin/env python3
"""
Launch script for Psycho-Validator Web Interface
Simple launcher that starts the web interface with appropriate settings
"""

import sys
import os
import webbrowser
import time
import threading

def main():
    """Launch the web interface"""
    print("🌐 Starting Psycho-Validator Web Interface...")
    print()
    
    # Check if we're in the right directory
    if not os.path.exists('web_interface.py'):
        print("❌ Error: Please run this script from the psycho-validator directory")
        print("   Make sure web_interface.py exists in the current directory")
        sys.exit(1)
    
    # Check if Flask is installed
    try:
        import flask
    except ImportError:
        print("❌ Error: Flask is not installed")
        print("   Please install Flask with: pip install Flask")
        print("   Or run: pip install -r requirements.txt")
        sys.exit(1)
    
    # Set default parameters
    host = '127.0.0.1'
    port = 5000
    
    # Parse simple command line arguments
    if '--help' in sys.argv or '-h' in sys.argv:
        print("Psycho-Validator Web Interface Launcher")
        print()
        print("Usage: python launch_web.py [options]")
        print()
        print("Options:")
        print("  --port PORT    Set port number (default: 5000)")
        print("  --public       Allow external connections")
        print("  --no-browser   Don't open browser automatically")
        print("  --help, -h     Show this help message")
        return
    
    if '--public' in sys.argv:
        host = '0.0.0.0'
        print("⚠️  Warning: Running in public mode - accessible from other computers")
    
    if '--port' in sys.argv:
        try:
            port_idx = sys.argv.index('--port') + 1
            port = int(sys.argv[port_idx])
        except (IndexError, ValueError):
            print("❌ Error: Invalid port number")
            sys.exit(1)
    
    # Open browser after a short delay
    open_browser = '--no-browser' not in sys.argv
    if open_browser:
        def open_browser_delayed():
            time.sleep(1.5)  # Wait for server to start
            url = f"http://127.0.0.1:{port}"
            print(f"🔗 Opening browser to: {url}")
            webbrowser.open(url)
        
        browser_thread = threading.Thread(target=open_browser_delayed)
        browser_thread.daemon = True
        browser_thread.start()
    
    # Show startup information
    print(f"🔗 Web interface will be available at: http://{host}:{port}")
    if host == '0.0.0.0':
        print(f"🔗 Local access: http://127.0.0.1:{port}")
    print("💡 Press Ctrl+C to stop the server")
    print()
    print("=" * 50)
    
    # Start the web interface
    try:
        # Import and run the web interface
        from web_interface import app
        app.run(host=host, port=port, debug=False)
    except KeyboardInterrupt:
        print("\n👋 Shutting down the web interface...")
    except Exception as e:
        print(f"❌ Error starting web interface: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()