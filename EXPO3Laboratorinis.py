import uuid
import webbrowser
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import paho.mqtt.client as mqtt
import logging
import time
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MQTT Configuration
MQTT_BROKER = "192.168.8.6"  # Replace with your MQTT broker IP
MQTT_PORT = 1883
MQTT_TOPIC = "expo/test"
MQTT_CLIENT_ID = f"gsmarena_search_scraper_{uuid.uuid4()}"  # Unique client ID

# Selenium Configuration
URL = "https://www.gsmarena.com/"
SEARCH_TERM = "Cubot"  # Change to your desired brand (e.g., "Apple", "Xiaomi")

def setup_mqtt_client():
    """Set up and connect MQTT client."""
    try:
        client = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
        client.on_connect = on_connect
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
    else:
        logger.error(f"Failed to connect to MQTT broker with code: {rc}")

def on_publish(client, userdata, mid):
    """Callback for when a message is published."""
    logger.info(f"Message {mid} published to {MQTT_TOPIC}")

def setup_selenium_driver():
    """Set up Selenium WebDriver."""
    try:
        options = Options()
        options.add_argument("--headless=new")  # Headless mode for Selenium
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        logger.error(f"Failed to set up Selenium driver: {e}")
        return None

def scrape_first_result(driver, search_term):
    """Search for a phone brand on GSMArena and return the link of the first result."""
    try:
        logger.info(f"Navigating to {URL}")
        for attempt in range(3):
            try:
                driver.get(URL)
                WebDriverWait(driver, 20).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                break
            except Exception as e:
                logger.warning(f"Retry {attempt+1}/3: Failed to load page: {e}")
                time.sleep(2)
        else:
            raise Exception("Failed to load page after retries")
        
        # Find and interact with search bar
        search_input_selectors = [
            "input#topsearch-text",
            "input.form-control",
            "input[type='text']",
            "input[name='sSearch']"
        ]
        search_input = None
        for selector in search_input_selectors:
            try:
                search_input = driver.find_element(By.CSS_SELECTOR, selector)
                logger.info(f"Found search input with selector: {selector}")
                break
            except:
                continue
        
        if not search_input:
            logger.error("Search input not found. Saving page source and screenshot.")
            with open("page_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot("error_screenshot.png")
            return None
        
        # Enter search term and submit
        logger.info(f"Searching for: {search_term}")
        search_input.clear()
        search_input.send_keys(search_term)
        time.sleep(1)  # Mimic human typing
        search_input.send_keys(Keys.ENTER)
        
        # Wait for search results
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.makers, div#review-body, div.listing"))
        )
        
        # Find the first phone element
        result_selectors = [
            "div.makers ul li",
            "div#review-body div.makers li",
            "div.listing li",
            "ul li a"
        ]
        first_element = None
        for selector in result_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                first_element = elements[0]
                logger.info(f"Found first element with selector: {selector}")
                break
        
        if not first_element:
            logger.error("No search results found. Saving page source and screenshot.")
            with open("page_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot("error_screenshot.png")
            return None
        
        # Extract the link from the first element
        try:
            link_element = first_element.find_element(By.CSS_SELECTOR, "a")
            first_link = link_element.get_attribute("href")
            if not first_link.startswith("http"):
                first_link = "https://www.gsmarena.com/" + first_link
            logger.info(f"First result link: {first_link}")
            return first_link
        except Exception as e:
            logger.warning(f"Could not extract link from first result: {e}")
            return None
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        with open("page_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        driver.save_screenshot("error_screenshot.png")
        return None

def main():
    """Main function to scrape the first result, open it in Chrome, and publish to MQTT."""
    mqtt_client = setup_mqtt_client()
    if not mqtt_client:
        logger.error("Exiting due to MQTT setup failure")
        return
    
    driver = setup_selenium_driver()
    if not driver:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.error("Exiting due to Selenium setup failure")
        return
    
    try:
        first_link = scrape_first_result(driver, SEARCH_TERM)
        if first_link:
            # Open the link in the default browser (assumed to be Chrome)
            logger.info(f"Opening the first result in Chrome: {first_link}")
            webbrowser.open(first_link)
            
            # Publish the link to MQTT
            result = mqtt_client.publish(MQTT_TOPIC, first_link, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published first link to {MQTT_TOPIC}: {first_link}")
            else:
                logger.error(f"Failed to publish to MQTT: {result.rc}")
        else:
            logger.warning("No link to publish or open")
    
    finally:
        driver.quit()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        logger.info("Script execution completed")

if __name__ == "__main__":
    main()