import requests
import json
from flask import Flask, render_template, request, redirect
import os
import webbrowser
from threading import Timer, Thread
from datetime import datetime
import paho.mqtt.client as mqtt
import time
import uuid
import queue

# Global variables for MQTT
mqtt_messages = queue.Queue(maxsize=100)  # Store last 100 messages
mqtt_client = None
mqtt_connected = False
mqtt_client_id = f'exchange-rates-app-{uuid.uuid4().hex[:8]}'
# Use exact topic names without any leading/trailing spaces
mqtt_topic_publish = "exchange/rates/data"
mqtt_topic_subscribe = "exchange/rates/messages"
# Add a debug flag to print more information
mqtt_debug = True

# MQTT callback functions
def on_connect(client, userdata, flags, rc, properties=None):
    """
    The callback for when the client receives a CONNACK response from the server.
    Handles both MQTT v3.1.1 and v5 protocols.
    """
    global mqtt_connected, mqtt_debug
    rc_codes = {
        0: "Connection successful",
        1: "Connection refused - incorrect protocol version",
        2: "Connection refused - invalid client identifier",
        3: "Connection refused - server unavailable",
        4: "Connection refused - bad username or password",
        5: "Connection refused - not authorized"
    }

    if rc == 0:
        print(f"Connected to MQTT broker: {rc_codes.get(rc, 'Unknown result code')}")
        mqtt_connected = True
        # Subscribe to both topics to ensure we can receive messages
        client.subscribe(mqtt_topic_publish, qos=1)
        client.subscribe(mqtt_topic_subscribe, qos=1)

        if mqtt_debug:
            print(f"Subscribed to topics: {mqtt_topic_publish} and {mqtt_topic_subscribe}")
            print(f"Client ID: {mqtt_client_id}")
            print(f"Connection flags: {flags}")
            if properties:
                print(f"Connection properties: {properties}")

        # Add connection message to queue
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mqtt_messages.put(f"[{timestamp}] Connected to MQTT broker")

        # Publish a test message to both topics
        test_message = f"Test message from {mqtt_client_id} at {timestamp}"
        client.publish(mqtt_topic_publish, test_message, qos=1)
        client.publish(mqtt_topic_subscribe, test_message, qos=1)

        if mqtt_debug:
            print(f"Published test messages to both topics")
    else:
        print(f"Failed to connect to MQTT broker: {rc_codes.get(rc, 'Unknown error')}")
        mqtt_connected = False

def on_disconnect(client, userdata, rc):
    global mqtt_connected, mqtt_debug

    if mqtt_debug:
        print(f"Disconnected from MQTT broker with code {rc}")
        if rc > 0:
            print("Unexpected disconnection")

    mqtt_connected = False
    # Add disconnection message to queue
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mqtt_messages.put(f"[{timestamp}] Disconnected from MQTT broker")

def on_message(client, userdata, msg):
    global mqtt_debug
    # Process incoming message
    try:
        payload = msg.payload.decode()
        topic = msg.topic
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"[{timestamp}] Topic: {topic}, Message: {payload}"

        if mqtt_debug:
            print(f"Received MQTT message: {message}")
            print(f"QoS: {msg.qos}, Retain: {msg.retain}")

        # Add to message queue, if full, remove oldest
        if mqtt_messages.full():
            mqtt_messages.get()
        mqtt_messages.put(message)
    except Exception as e:
        print(f"Error processing MQTT message: {e}")
        if mqtt_debug:
            import traceback
            traceback.print_exc()

def on_publish(client, userdata, mid):
    global mqtt_debug

    if mqtt_debug:
        print(f"Message published with ID: {mid}")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mqtt_messages.put(f"[{timestamp}] Published message with ID: {mid}")

# Setup MQTT client
def setup_mqtt():
    global mqtt_client, mqtt_connected, mqtt_debug
    try:
        # Create MQTT client with clean session
        if mqtt_debug:
            print(f"Creating MQTT client with ID: {mqtt_client_id}")

        # Use MQTT v3.1.1 for better compatibility
        mqtt_client = mqtt.Client(client_id=mqtt_client_id, protocol=mqtt.MQTTv311)
        if mqtt_debug:
            print("Using MQTT v3.1.1 protocol")

        # Set callbacks
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_message = on_message
        mqtt_client.on_publish = on_publish

        # Set a shorter keep alive interval and connection timeout
        if mqtt_debug:
            print("Connecting to broker.hivemq.com...")

        # Use synchronous connection for better error reporting
        try:
            mqtt_client.connect("broker.hivemq.com", 1883, keepalive=30)
            if mqtt_debug:
                print("Connection initiated")
        except Exception as e:
            if mqtt_debug:
                print(f"Initial connection attempt failed: {e}")
            # Try alternative broker immediately
            try:
                if mqtt_debug:
                    print("Trying alternative broker test.mosquitto.org...")
                mqtt_client.connect("test.mosquitto.org", 1883, keepalive=30)
                if mqtt_debug:
                    print("Connection to alternative broker initiated")
            except Exception as e2:
                if mqtt_debug:
                    print(f"Alternative connection attempt failed: {e2}")
                return False

        # Start MQTT loop in a separate thread
        mqtt_client.loop_start()

        # Wait for connection or timeout
        connection_timeout = 10  # seconds - increased timeout
        start_time = time.time()
        while not mqtt_connected and time.time() - start_time < connection_timeout:
            time.sleep(0.5)  # Longer sleep to reduce CPU usage
            if mqtt_debug and (time.time() - start_time) % 2 < 0.5:
                print(f"Waiting for connection... ({int(time.time() - start_time)}s)")

        if mqtt_connected:
            if mqtt_debug:
                print("MQTT connection established successfully")
            return True
        else:
            if mqtt_debug:
                print(f"MQTT connection timed out after {connection_timeout} seconds")
            return False
    except Exception as e:
        if mqtt_debug:
            print(f"Error setting up MQTT: {e}")
            import traceback
            traceback.print_exc()
        return False

# Publish exchange rate data to MQTT
def publish_to_mqtt(data):
    global mqtt_client, mqtt_connected, mqtt_debug

    if not mqtt_client:
        if mqtt_debug:
            print("MQTT client not initialized, cannot publish")
        return False

    if not mqtt_connected:
        if mqtt_debug:
            print("MQTT client not connected, cannot publish")
        return False

    try:
        # Convert data to JSON string
        json_data = json.dumps(data)

        # Add a timestamp and identifier to the data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message_data = {
            "timestamp": timestamp,
            "client_id": mqtt_client_id,
            "data": data
        }

        # Convert to JSON string
        message_json = json.dumps(message_data)

        if mqtt_debug:
            print(f"Publishing to {mqtt_topic_publish} with QoS 1")
            print(f"Message size: {len(message_json)} bytes")

        # Publish to topic with QoS 1 (at least once delivery)
        result = mqtt_client.publish(mqtt_topic_publish, message_json, qos=1, retain=True)

        # Wait for the message to be published
        if mqtt_debug:
            print("Waiting for message to be published...")

        result.wait_for_publish(timeout=10)

        if result.is_published():
            if mqtt_debug:
                print(f"Successfully published exchange rate data to {mqtt_topic_publish}")

            # Also publish a simple message to the messages topic
            simple_message = f"Exchange rates updated at {timestamp}"
            mqtt_client.publish(mqtt_topic_subscribe, simple_message, qos=1)

            return True
        else:
            if mqtt_debug:
                print("Failed to publish exchange rate data - timeout or error")
            return False
    except Exception as e:
        if mqtt_debug:
            print(f"Error publishing to MQTT: {e}")
            import traceback
            traceback.print_exc()
        return False

# Function to fetch data from Exchange Rates API
def fetch_api_data():
    # Using Open Exchange Rates API to get latest exchange rates
    api_url = "https://open.er-api.com/v6/latest/USD"

    try:
        print(f"Fetching data from {api_url}...")
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Parse JSON response
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
        return None

# Function to save data to a JSON file
def save_to_json_file(data, filename="any_api.json"):
    try:
        # Save in the same directory as the script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, filename)

        with open(json_path, "w") as json_file:
            json.dump(data, json_file, indent=4)
        print(f"Data successfully saved to {json_path}")
        return json_path
    except Exception as e:
        print(f"Error saving data to file: {e}")
        return None

# Initialize Flask application
app = Flask(__name__)

# Create templates directory and HTML template
def setup_templates():
    try:
        # Create templates directory in the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.join(current_dir, "templates")

        print(f"Creating templates directory at: {templates_dir}")
        os.makedirs(templates_dir, exist_ok=True)

        html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Exchange Rates Viewer with MQTT</title>
        <meta http-equiv="refresh" content="60">
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }
            h1, h2 {
                color: #333;
                text-align: center;
            }
            .grid-container {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 15px;
                max-width: 1400px;
                margin: 0 auto 30px auto;
                padding: 0 20px;
            }
            .currency-card {
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                padding: 20px;
                text-align: center;
                transition: transform 0.2s ease, box-shadow 0.2s ease;
                border: 1px solid #e0e0e0;
            }
            .currency-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }
            .currency-code {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 8px;
            }
            .currency-rate {
                font-size: 16px;
                font-weight: bold;
                color: #27ae60;
                margin: 5px 0;
            }
            .base-info {
                text-align: center;
                margin: 20px 0;
                padding: 15px;
                background-color: #3498db;
                color: white;
                border-radius: 8px;
                max-width: 1400px;
                margin: 20px auto;
            }
            .json-container, .mqtt-container {
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                padding: 25px;
                margin: 30px auto;
                max-width: 1400px;
            }
            .json-content, .mqtt-content {
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 20px;
                font-family: 'Courier New', monospace;
                white-space: pre-wrap;
                overflow-x: auto;
                font-size: 13px;
                line-height: 1.4;
                max-height: 300px;
                overflow-y: auto;
            }
            .mqtt-status {
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 10px 0;
            }
            .status-indicator {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
            }
            .status-connected {
                background-color: #2ecc71;
            }
            .status-disconnected {
                background-color: #e74c3c;
            }
            .mqtt-message {
                border-bottom: 1px solid #eee;
                padding: 8px 0;
            }
            .mqtt-message:last-child {
                border-bottom: none;
            }
            .mqtt-form {
                margin-top: 20px;
                display: flex;
                gap: 10px;
            }
            .mqtt-form input {
                flex: 1;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            .mqtt-form button {
                padding: 10px 15px;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            .mqtt-form button:hover {
                background-color: #2980b9;
            }
            /* Ensure minimum 2 columns on larger screens */
            @media (min-width: 768px) {
                .grid-container {
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                }
            }
            @media (min-width: 1200px) {
                .grid-container {
                    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                }
            }
            /* Mobile responsive */
            @media (max-width: 480px) {
                .grid-container {
                    grid-template-columns: 1fr;
                    padding: 0 10px;
                }
                .currency-card {
                    padding: 15px;
                }
                .mqtt-form {
                    flex-direction: column;
                }
            }
        </style>
    </head>
    <body>
        <h1>Exchange Rates Viewer with MQTT</h1>

        <div class="base-info">
            <h3>Base Currency: {{ base_currency }}</h3>
            <p>Last Updated: {{ last_updated }}</p>
            <div class="mqtt-status">
                <div class="status-indicator {% if mqtt_connected %}status-connected{% else %}status-disconnected{% endif %}"></div>
                <span>MQTT: {% if mqtt_connected %}Connected{% else %}Disconnected{% endif %}</span>
            </div>
        </div>

        <div class="grid-container">
            {% for currency, rate in rates|dictsort %}
                <div class="currency-card">
                    <div class="currency-code">{{ currency }}</div>
                    <div class="currency-rate">{{ "%.4f"|format(rate) }}</div>
                </div>
            {% endfor %}
        </div>

        <h2>MQTT Messages</h2>
        <div class="mqtt-container">
            <div class="mqtt-content">
                {% if mqtt_messages %}
                    {% for message in mqtt_messages %}
                        <div class="mqtt-message">{{ message }}</div>
                    {% endfor %}
                {% else %}
                    <p>No MQTT messages received yet.</p>
                {% endif %}
            </div>
            <form class="mqtt-form" action="/publish_message" method="post">
                <input type="text" name="message" placeholder="Type a message to publish to MQTT...">
                <button type="submit">Send</button>
            </form>
        </div>

        <h2>Complete JSON Data</h2>
        <div class="json-container">
            <div class="json-content">{{ json_data }}</div>
        </div>
    </body>
    </html>
    """

        template_path = os.path.join(templates_dir, "index.html")
        print(f"Creating template file at: {template_path}")
        with open(template_path, "w") as f:
            f.write(html_template)

        print("Template setup completed successfully")
        return True
    except Exception as e:
        print(f"Error setting up templates: {e}")
        return False

# Define Flask route for the home page
@app.route("/")
def home():
    try:
        # Load the JSON file from the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "any_api.json")

        print(f"Attempting to load JSON data from: {json_path}")
        if not os.path.exists(json_path):
            return f"Error: JSON file not found at {json_path}"

        with open(json_path, "r") as f:
            data = json.load(f)

        # Format the JSON data for display
        formatted_json = json.dumps(data, indent=4)

        # Get the rates and other info
        rates = data.get("rates", {})
        base_currency = data.get("base_code", "USD")
        last_updated = data.get("time_last_update_utc", "Unknown")

        # Get MQTT messages for display
        global mqtt_connected, mqtt_messages
        mqtt_messages_list = list(mqtt_messages.queue)

        return render_template("index.html",
                             rates=rates,
                             json_data=formatted_json,
                             base_currency=base_currency,
                             last_updated=last_updated,
                             mqtt_connected=mqtt_connected,
                             mqtt_messages=mqtt_messages_list)
    except FileNotFoundError as e:
        return f"Error: File not found - {e}"
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON data - {e}"
    except Exception as e:
        return f"Error loading JSON data: {str(e)}"

# Route to handle publishing messages to MQTT
@app.route("/publish_message", methods=["POST"])
def publish_message():
    message = request.form.get("message", "")
    if message:
        try:
            global mqtt_client, mqtt_connected, mqtt_debug

            if not mqtt_client:
                if mqtt_debug:
                    print("MQTT client not initialized, cannot publish user message")
                return redirect("/")

            if not mqtt_connected:
                if mqtt_debug:
                    print("MQTT client not connected, cannot publish user message")
                return redirect("/")

            # Create a structured message with timestamp and sender info
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            structured_message = {
                "timestamp": timestamp,
                "sender": mqtt_client_id,
                "message": message
            }

            # Convert to JSON
            message_json = json.dumps(structured_message)

            if mqtt_debug:
                print(f"Publishing user message to {mqtt_topic_subscribe}")
                print(f"Message: {message}")
                print(f"Structured message: {message_json}")

            # Publish the message with QoS 1
            result = mqtt_client.publish(mqtt_topic_subscribe, message_json, qos=1)

            # Also publish the raw message for simpler clients
            mqtt_client.publish(mqtt_topic_subscribe, message, qos=1)

            # Wait for the message to be published
            result.wait_for_publish(timeout=5)

            if result.is_published():
                if mqtt_debug:
                    print(f"Successfully published user message")
            else:
                if mqtt_debug:
                    print(f"Failed to publish user message - timeout or error")
        except Exception as e:
            if mqtt_debug:
                print(f"Error publishing user message: {e}")
                import traceback
                traceback.print_exc()

    # Redirect back to the home page
    return redirect("/")

def open_browser():
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == "__main__":
    # Setup templates
    templates_created = setup_templates()

    if not templates_created:
        print("Failed to create templates. Exiting.")
        exit(1)

    # Setup MQTT client
    mqtt_setup_success = setup_mqtt()
    if not mqtt_setup_success:
        print("Warning: Failed to setup MQTT client. Continuing without MQTT functionality.")

    # Fetch data from API
    api_data = fetch_api_data()

    if api_data:
        # Save data to JSON file
        json_file_path = save_to_json_file(api_data)

        if json_file_path:
            # Publish data to MQTT if connected
            if mqtt_connected:
                publish_success = publish_to_mqtt(api_data)
                if publish_success:
                    print("Successfully published exchange rate data to MQTT")
                else:
                    print("Failed to publish exchange rate data to MQTT")

            # Open browser after a short delay
            Timer(1.5, open_browser).start()

            # Run Flask application
            print("\nStarting Flask server to display JSON data...")
            print("Open your browser at http://127.0.0.1:5000/")
            app.run(debug=False)

            # Clean up MQTT client on exit
            if mqtt_client:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
    else:
        print("Failed to fetch data from API. Exiting.")
