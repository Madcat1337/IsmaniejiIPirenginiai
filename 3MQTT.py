from http import client
import paho.mqtt.client as mqtt
import time

def connect_broker(broker_address, client_name):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_name)
    client.connect(broker_address)
    time.sleep(1)
    client.loop_start()
    
    return client

if __name__ == "__main__":
    server = "broker.hivemq.com"
    client_name = "3LAB"
    client = connect_broker(server, client_name)
    try:
        while True:
            messsage = input("Enter message: ")
            client.publish("testtopic/temperature", messsage)
    except KeyboardInterrupt:
        client.disconnect()
        client.loop_stop()