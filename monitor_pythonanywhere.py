import os
import time
import requests
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from keep_alive import KeepAlive

app = Flask(__name__)

# Configuration
PYTHONANYWHERE_URL = os.getenv('PYTHONANYWHERE_URL', 'https://eyosafit.pythonanywhere.com')
RENDER_URL = os.getenv('RENDER_URL', 'https://selamsnap-bot.onrender.com')

# Initialize keep-alive (PythonAnywhere pings Render)
keep_alive = KeepAlive(
    my_url=PYTHONANYWHERE_URL,
    partner_url=RENDER_URL,
    interval_minutes=14
)

# Store last ping times
last_ping_sent = None
last_ping_received = None

@app.route('/')
def home():
    """Home page for PythonAnywhere monitoring service"""
    status = "🟢 Active" if last_ping_received else "🔴 No recent pings"
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SelamSnap Monitor</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .container {{ max-width: 800px; margin: auto; }}
            .status {{ padding: 20px; border-radius: 10px; margin: 20px 0; }}
            .online {{ background: #d4edda; color: #155724; }}
            .offline {{ background: #f8d7da; color: #721c24; }}
            .info {{ background: #d1ecf1; color: #0c5460; padding: 15px; border-radius: 5px; }}
            .stats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
            .stat-box {{ padding: 15px; background: #f8f9fa; border-radius: 5px; }}
        </style>
        <meta http-equiv="refresh" content="30">
    </head>
    <body>
        <div class="container">
            <h1>🤖 SelamSnap Monitor</h1>
            <div class="status { 'online' if last_ping_received else 'offline' }">
                <h2>Status: {status}</h2>
                <p>PythonAnywhere ↔ Render.com Mutual Ping System</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>📤 Last Ping Sent</h3>
                    <p>{last_ping_sent or 'Never'}</p>
                </div>
                <div class="stat-box">
                    <h3>📥 Last Ping Received</h3>
                    <p>{last_ping_received or 'Never'}</p>
                </div>
            </div>
            
            <div class="info">
                <h3>🔗 Services</h3>
                <ul>
                    <li><strong>Render Bot:</strong> <a href="{RENDER_URL}" target="_blank">{RENDER_URL}</a></li>
                    <li><strong>This Monitor:</strong> <a href="{PYTHONANYWHERE_URL}" target="_blank">{PYTHONANYWHERE_URL}</a></li>
                    <li><strong>Ping Endpoint:</strong> <a href="{RENDER_URL}/ping" target="_blank">{RENDER_URL}/ping</a></li>
                    <li><strong>GitHub:</strong> <a href="https://github.com/Eyosafitelias/selamsnap-bot" target="_blank">Repository</a></li>
                </ul>
                
                <h3>⚙️ How It Works</h3>
                <p>Both servers ping each other every 14 minutes to prevent sleep.</p>
                <p>Render sleeps after 15 minutes of inactivity. PythonAnywhere free web apps need visits every 3 months.</p>
            </div>
            
            <div style="margin-top: 30px; text-align: center; color: #666;">
                <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>This page auto-refreshes every 30 seconds</p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/ping')
def ping():
    """Endpoint for Render to ping PythonAnywhere"""
    global last_ping_received
    from_url = request.args.get('from', 'unknown')
    last_ping_received = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Log the ping
    print(f"[{datetime.now()}] 🏓 Ping received from: {from_url}")
    
    # Send back response
    return jsonify({
        "status": "pong",
        "received_from": from_url,
        "timestamp": last_ping_received,
        "message": "PythonAnywhere monitor is active",
        "next_ping_in": "14 minutes"
    })

@app.route('/force-ping')
def force_ping():
    """Manually trigger a ping to Render"""
    global last_ping_sent
    try:
        response = requests.get(f"{RENDER_URL}/ping?from={PYTHONANYWHERE_URL}&t={int(time.time())}")
        last_ping_sent = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            "status": "success" if response.status_code == 200 else "failed",
            "message": f"Ping sent to Render. Response: {response.status_code}",
            "timestamp": last_ping_sent
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/status')
def status():
    """API endpoint for status"""
    return jsonify({
        "service": "SelamSnap Monitor (PythonAnywhere)",
        "status": "online",
        "last_ping_sent": last_ping_sent,
        "last_ping_received": last_ping_received,
        "render_url": RENDER_URL,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "monitor",
        "timestamp": datetime.now().isoformat()
    })

def background_pinger():
    """Background thread to continuously ping Render"""
    global last_ping_sent
    
    while True:
        try:
            print(f"[{datetime.now()}] 📤 Scheduled ping to Render...")
            response = requests.get(f"{RENDER_URL}/ping?from={PYTHONANYWHERE_URL}&t={int(time.time())}")
            
            if response.status_code == 200:
                last_ping_sent = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"[{datetime.now()}] ✅ Ping successful")
            else:
                print(f"[{datetime.now()}] ⚠️  Ping failed: {response.status_code}")
                
        except Exception as e:
            print(f"[{datetime.now()}] ❌ Ping error: {e}")
        
        # Sleep for 14 minutes (840 seconds)
        # Render sleeps after 15 minutes, so ping every 14
        time.sleep(14 * 60)

if __name__ == '__main__':
    print("🚀 Starting PythonAnywhere Monitor...")
    print(f"🔗 This URL: {PYTHONANYWHERE_URL}")
    print(f"🔗 Render URL: {RENDER_URL}")
    print("⏰ Pinging Render every 14 minutes")
    print("🌐 Web interface available at /")
    
    # Start background pinger in a thread
    import threading
    pinger_thread = threading.Thread(target=background_pinger, daemon=True)
    pinger_thread.start()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=8080)