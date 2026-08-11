import network
import time
from machine import UART
from umqtt.simple import MQTTClient


# ============================================================
# Configuration
# ============================================================

MQTT_SERVER = "192.168.0.46"
MQTT_PORT = 1883

MQTT_USER = None
MQTT_PASSWORD = None

MQTT_CLIENT_ID = b"esp32-lightstrip"


# ============================================================
# UART2
# ============================================================
#
# ESP32:
#
# UART2 TX = GPIO17
# UART2 RX = GPIO16
#
# Mega:
#
# RX1 = D19
# TX1 = D18
#
# ============================================================

uart = UART(
    2,
    baudrate=115200,
    bits=8,
    parity=None,
    stop=1,
    tx=17,
    rx=16
)


# ============================================================
# Read pws.txt
# ============================================================

def read_credentials():

    credentials = []

    try:
        with open("pws.txt", "r") as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                parts = line.split(" ", 1)

                if len(parts) != 2:
                    continue

                ssid = parts[0].strip()
                password = parts[1].strip()

                if ssid:
                    credentials.append((ssid, password))

    except OSError:
        print("Could not open pws.txt")

    return credentials


# ============================================================
# Read config.txt
# ============================================================

def read_signal_priority():

    try:
        with open("config.txt", "r") as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                if line.startswith("#"):
                    continue

                if "=" not in line:
                    continue

                key, value = line.split("=", 1)

                key = key.strip().upper()
                value = value.strip().lower()

                if key == "PRIORITY":

                    return value == "SIGNAL"

    except OSError:
        print("Could not open config.txt")

    # Default
    return False


# ============================================================
# Connect Wi-Fi
# ============================================================

def connect_wifi():

    credentials = read_credentials()

    if not credentials:
        print("No Wi-Fi credentials")
        return False

    signal_priority = read_signal_priority()

    print("Wi-Fi priority:",
          "SIGNAL" if signal_priority else "ORDER")


    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    print("Scanning Wi-Fi...")

    networks = wlan.scan()

    # --------------------------------------------------------
    # Convert scan results into:
    #
    # (SSID, RSSI)
    # --------------------------------------------------------

    visible = []

    for net in networks:

        ssid = net[0].decode("utf-8")
        rssi = net[3]

        visible.append((ssid, rssi))


    # ========================================================
    # SIGNAL priority
    # ========================================================

    if signal_priority:

        candidates = []

        for ssid, password in credentials:

            best_rssi = None

            for visible_ssid, rssi in visible:

                if visible_ssid == ssid:

                    if best_rssi is None or rssi > best_rssi:
                        best_rssi = rssi

            if best_rssi is not None:

                candidates.append(
                    (ssid, password, best_rssi)
                )


        # Strongest first
        candidates.sort(
            key=lambda x: x[2],
            reverse=True
        )


        for ssid, password, rssi in candidates:

            print(
                "Trying:",
                ssid,
                "RSSI:",
                rssi
            )

            wlan.connect(ssid, password)

            if wait_for_wifi(wlan):
                return True

            wlan.disconnect()

    # ========================================================
    # ORDER priority
    # ========================================================

    else:

        for ssid, password in credentials:

            found = False

            for visible_ssid, rssi in visible:

                if visible_ssid == ssid:
                    found = True
                    break

            if not found:
                continue

            print("Trying:", ssid)

            wlan.connect(ssid, password)

            if wait_for_wifi(wlan):
                return True

            wlan.disconnect()


    print("No Wi-Fi network could be connected")

    return False


# ============================================================
# Wait for Wi-Fi
# ============================================================

def wait_for_wifi(wlan, timeout=15):

    start = time.ticks_ms()

    while not wlan.isconnected():

        if time.ticks_diff(
            time.ticks_ms(),
            start
        ) > timeout * 1000:

            return False

        time.sleep_ms(250)

    print("Connected!")
    print("IP:", wlan.ifconfig()[0])

    return True


# ============================================================
# MQTT callback
# ============================================================

def mqtt_callback(topic, message):

    print("MQTT:", topic, message)

    if message == b"true":
        state = b"1"

    elif message == b"false":
        state = b"0"

    elif message == b"1":
        state = b"1"

    elif message == b"0":
        state = b"0"

    else:
        print("Invalid state:", message)
        return


    if topic == b"lightstrip/0":

        uart.write(b"0 " + state + b"\n")

        print("UART TX: 0", state)


    elif topic == b"lightstrip/1":

        uart.write(b"1 " + state + b"\n")

        print("UART TX: 1", state)

# ============================================================
# Connect MQTT
# ============================================================

def connect_mqtt():

    print("Connecting MQTT...")

    client = MQTTClient(
        MQTT_CLIENT_ID,
        MQTT_SERVER,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD
    )

    client.set_callback(mqtt_callback)

    client.connect()

    client.subscribe(b"lightstrip/0")
    client.subscribe(b"lightstrip/1")

    print("MQTT connected")

    return client


# ============================================================
# Main
# ============================================================

def main():

    while True:

        # ----------------------------------------------------
        # Wi-Fi
        # ----------------------------------------------------

        while not connect_wifi():

            print("Retrying Wi-Fi in 5 seconds...")
            time.sleep(5)


        # ----------------------------------------------------
        # MQTT
        # ----------------------------------------------------

        try:

            mqtt = connect_mqtt()

            while True:

                wlan = network.WLAN(network.STA_IF)

                if not wlan.isconnected():
                    raise OSError("Wi-Fi disconnected")

                mqtt.check_msg()

                time.sleep_ms(10)


        except Exception as e:

            print("MQTT error:", e)

            try:
                mqtt.disconnect()
            except:
                pass

            time.sleep(5)


# ============================================================
# Start
# ============================================================

main()