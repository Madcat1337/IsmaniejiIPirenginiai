import requests
import json
from flask import Flask, render_template, jsonify
import os
import webbrowser
from threading import Timer
from datetime import datetime

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
        # Save in the same directory as 1kursin.py
        target_dir = r"c:\Users\Kompiuteris\Desktop\Ismanieji IP irenginiai"
        json_path = os.path.join(target_dir, filename)

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
    # Save in the same directory as 1kursin.py
    target_dir = r"c:\Users\Kompiuteris\Desktop\Ismanieji IP irenginiai"
    templates_dir = os.path.join(target_dir, "templates")
    os.makedirs(templates_dir, exist_ok=True)

    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Exchange Rates Viewer</title>
        <meta http-equiv="refresh" content="120">
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
            .json-container {
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                padding: 25px;
                margin: 30px auto;
                max-width: 1400px;
            }
            .json-content {
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 6px;
                padding: 20px;
                font-family: 'Courier New', monospace;
                white-space: pre-wrap;
                overflow-x: auto;
                font-size: 13px;
                line-height: 1.4;
                max-height: 500px;
                overflow-y: auto;
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
            }
        </style>
    </head>
    <body>
        <h1>Exchange Rates Viewer</h1>

        <div class="base-info">
            <h3>Base Currency: {{ base_currency }}</h3>
            <p>Last Updated: {{ last_updated }}</p>
        </div>

<div class="grid-container">
    {% for currency, rate in rates|dictsort %}
        <div class="currency-card">
            <div class="currency-code">{{ currency }}</div>
            <div class="currency-rate">{{ "%.4f"|format(rate) }}</div>
        </div>
    {% endfor %}
</div>

        <h2>Complete JSON Data</h2>
        <div class="json-container">
            <div class="json-content">{{ json_data }}</div>
        </div>
    </body>
    </html>
    """

    template_path = os.path.join(templates_dir, "index.html")
    with open(template_path, "w") as f:
        f.write(html_template)

    return True

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
    from flask import request, redirect

    message = request.form.get("message", "")
    if message:
        try:
            global mqtt_client, mqtt_connected

            if mqtt_client and mqtt_connected:
                # Publish the message
                result = mqtt_client.publish(mqtt_topic_subscribe, message, qos=1)
                result.wait_for_publish()

                if result.is_published():
                    print(f"Published user message to {mqtt_topic_subscribe}: {message}")
                else:
                    print(f"Failed to publish user message: {message}")
            else:
                print("MQTT client not connected, cannot publish user message")
        except Exception as e:
            print(f"Error publishing user message: {e}")

    # Redirect back to the home page
    return redirect("/")

def open_browser():
    webbrowser.open("http://127.0.0.1:5000/")

if __name__ == "__main__":
    # Setup templates
    setup_templates()

    # Fetch data from API
    api_data = fetch_api_data()

    if api_data:
        # Save data to JSON file
        json_file_path = save_to_json_file(api_data)

        if json_file_path:
            # Open browser after a short delay
            Timer(1.5, open_browser).start()

            # Run Flask application
            print("\nStarting Flask server to display JSON data...")
            print("Open your browser at http://127.0.0.1:5000/")
            app.run(debug=False)
    else:
        print("Failed to fetch data from API. Exiting.")