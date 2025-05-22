import uuid
import paho.mqtt.client as mqtt
import logging
import time
import paramiko

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MQTT Configuration
MQTT_BROKER = "192.168.8.16"
MQTT_PORT = 1883
MQTT_COMMAND_TOPIC = "expo/test"
MQTT_RESULT_TOPIC = "expo/test/results"
MQTT_CLIENT_ID = f"system_agent_{uuid.uuid4()}"

# SSH Configuration for the Linux VM
VM_HOST = "192.168.8.16"  # Replace with your VM's IP address
VM_USERNAME = "madcat"  # Replace with your VM's SSH username
VM_PASSWORD = "madcat"  # Replace with your VM's SSH password

def ssh_execute_command(command):
    """Execute a command on the Linux VM via SSH."""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VM_HOST, username=VM_USERNAME, password=VM_PASSWORD)
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        ssh.close()
        if error:
            return f"SSH error: {error}"
        return output
    except Exception as e:
        return f"SSH connection failed: {e}"

def setup_mqtt_client():
    """Set up and connect MQTT client."""
    try:
        client = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_publish = on_publish
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        return client
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
        return None

def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the broker."""
    if rc == 0:
        logger.info("Connected to MQTT broker")
        client.subscribe(MQTT_COMMAND_TOPIC, qos=1)
        logger.info(f"Subscribed to {MQTT_COMMAND_TOPIC}")
    else:
        logger.error(f"Failed to connect to MQTT broker with code: {rc}")

def on_publish(client, userdata, mid):
    """Callback for when a message is published."""
    logger.info(f"Message {mid} published to {MQTT_RESULT_TOPIC}")

def on_message(client, userdata, msg):
    """Callback for when a message is received."""
    try:
        command = msg.payload.decode().strip()
        logger.info(f"Received command: {command}")
        
        if command == "1":
            # List current directory files on VM
            try:
                ls_output = ssh_execute_command("ls")
                if "SSH error" in ls_output or "SSH connection failed" in ls_output:
                    result = ls_output
                else:
                    files = ls_output.splitlines()
                    result = "Current directory files:\n" + "\n".join(files)
            except Exception as e:
                result = f"Error listing files: {e}"
        elif command == "2":
            # Get IP addresses from VM
            try:
                ip_output = ssh_execute_command("ip addr show")
                if "SSH error" in ip_output or "SSH connection failed" in ip_output:
                    result = ip_output
                else:
                    ip_lines = [line for line in ip_output.splitlines() if "inet " in line]
                    ip_addresses = [line.split()[1].split('/')[0] for line in ip_lines]
                    result = "IP addresses:\n" + "\n".join(ip_addresses)
            except Exception as e:
                result = f"Error getting IP addresses: {e}"
        elif command == "3":
            # Get available RAM from VM
            try:
                mem_output = ssh_execute_command("free -m | grep Mem")
                if "SSH error" in mem_output or "SSH connection failed" in mem_output:
                    result = mem_output
                else:
                    available_mb = mem_output.split()[3]  # Available memory in MB
                    result = f"Available RAM: {available_mb} MB"
            except Exception as e:
                result = f"Error getting memory: {e}"
        elif command == "4":
            # Create a new file on VM
            try:
                filename = f"new_file_{int(time.time())}.txt"
                ssh_command = f"echo 'Created by MQTT agent' > {filename}"
                ssh_result = ssh_execute_command(ssh_command)
                if "SSH error" in ssh_result or "SSH connection failed" in ssh_result:
                    result = ssh_result
                else:
                    result = f"Created file: {filename}"
            except Exception as e:
                result = f"Error creating file: {e}"
        else:
            result = "Invalid command. Use: 1 (list files), 2 (IP addresses), 3 (available RAM), 4 (create file)"
        
        # Publish the result
        client.publish(MQTT_RESULT_TOPIC, result, qos=1)
        logger.info(f"Published result: {result}")
        
    except Exception as e:
        error_msg = f"Error processing command: {e}"
        client.publish(MQTT_RESULT_TOPIC, error_msg, qos=1)
        logger.error(error_msg)

def main():
    """Main function to set up MQTT client and listen for commands."""
    mqtt_client = setup_mqtt_client()
    if not mqtt_client:
        logger.error("Exiting due to MQTT setup failure")
        return
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("Script execution completed")

if __name__ == "__main__":
    main()