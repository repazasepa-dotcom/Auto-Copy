# keep_alive.py
from flask import Flask
import os
import threading

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Server is running!"

def run_web():
    port = int(os.environ.get("PORT", 5000))  # default 5000, change if needed
    print(f"🌐 Starting web server on port {port}")
    app.run(host="0.0.0.0", port=port)

def start():
    """Start the Flask server in a separate thread."""
    threading.Thread(target=run_web, daemon=True).start()
