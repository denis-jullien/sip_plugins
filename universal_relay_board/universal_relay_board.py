#!/usr/bin/env python

# standard library imports
import json
from sys import exception
import time

# local module imports
from blinker import signal
import gv  # Get access to SIP's settings, gv = global variables
from sip import template_render
from urls import urls  # Get access to SIP's URLs
import web
from webpages import ProtectedPage

gv.use_gpio_pins = False  # Signal SIP to not use GPIO pins

# Load the Raspberry Pi GPIO (General Purpose Input Output) library
try:
    if gv.use_pigpio:
        import pigpio
        pi = pigpio.pi()
    else:
        import RPi.GPIO as GPIO
        pi = 0
except IOError:
    pass

# Add a new url to open the data entry page.
# fmt: off
urls.extend(
    [
        "/urb", "plugins.universal_relay_board.settings",
        "/urbu", "plugins.universal_relay_board.update",
    ]
)
# fmt: on

# Add this plugin to the home page plugins menu
gv.plugin_menu.append([_("Universal Relay Board"), "/urb"])

params = {}

# Read in the parameters for this plugin from it's JSON file
def load_params():
    global params
    try:
        with open("./data/universal_relay_board.json", "r") as f:  # Read the settings from file
            params = json.load(f)
    except IOError:  #  If file does not exist create file with defaults.
        params = {
            "active": "high",
            "gpio_pins": [7, 15, 31, 37]  # Default physical pins
        }
        with open("./data/universal_relay_board.json", "w") as f:
            json.dump(params, f, indent=4, sort_keys=True)

load_params()

#### define the GPIO pins that will be used ####
try:
    if gv.platform == "pi":  # If this will run on Raspberry Pi:
        if not gv.use_pigpio:
            GPIO.setmode(
                GPIO.BOARD
            )  # IO channels are identified by header connector pin numbers. Pin numbers are
        relay_pins = params["gpio_pins"][:]
        for i in range(len(relay_pins)):
            try:
                relay_pins[i] = gv.pin_map[relay_pins[i]]
            except:
                relay_pins[i] = 0
    else:
        print("relay board plugin only supported on pi.")
except BaseException as e:
    print(f"Relay board: GPIO pins not set : {e}")
    pass


#### setup GPIO pins as output and high ####
def init_pins():
    global pi

    try:
        for i in range(len(relay_pins)):
            if gv.use_pigpio:
                pi.set_mode(relay_pins[i], pigpio.OUTPUT)
                if params["active"] == "low":
                    pi.write(bcm_pin, 1)  # High = off for active low
                else:
                    pi.write(bcm_pin, 0)  # Low = off for active high
            else:
                GPIO.setup(relay_pins[i], GPIO.OUT)
                if params["active"] == "low":
                    GPIO.output(relay_pins[i], GPIO.HIGH)  # High = off for active low
                else:
                    GPIO.output(relay_pins[i], GPIO.LOW)   # Low = off for active high
            time.sleep(0.1)
    except:
        pass


#### change outputs when blinker signal received ####
def on_zone_change(arg):  #  arg is just a necessary placeholder.
    """ Switch relays when core program signals a change in zone state."""
    global pi
    with gv.output_srvals_lock:
        for i in range(len(relay_pins)):
            try:
                if (gv.output_srvals[i] and params["active"] == "low") or (not gv.output_srvals[i] and params["active"] != "low"):  # if station is set to on
                    if gv.use_pigpio:
                        pi.write(relay_pins[i], 0)
                    else:
                        GPIO.output(relay_pins[i], GPIO.LOW)
                else:  # station is set to off
                    if gv.use_pigpio:
                        pi.write(relay_pins[i], 1)
                    else:
                        GPIO.output(relay_pins[i], GPIO.HIGH)
            except Exception as e:
                print("Problem switching relays", e, relay_pins[i])
                pass


init_pins()

zones = signal("zone_change")
zones.connect(on_zone_change)

################################################################################
# Web pages:                                                                   #
################################################################################

class settings(ProtectedPage):
    """Load an html page for entering relay board adjustments"""

    def GET(self):
        with open("./data/universal_relay_board.json", "r") as f:  # Read the settings from file
            params = json.load(f)
        params["gpio_pins_str"] = ", ".join(map(str, params.get("gpio_pins", [])))
        return template_render.universal_relay_board(params)


class update(ProtectedPage):
    """Save user input to universal_relay_board.json file"""

    def GET(self):
        qdict = web.input()
        changed = False

        # Update active state
        if "active" in qdict and params["active"] != qdict["active"]:
            params["active"] = qdict["active"]
            changed = True
        
        # Update GPIO pins from comma-separated string
        if "gpio_pins" in qdict:
            try:
                # Parse comma-separated pin numbers
                pin_string = qdict["gpio_pins"].strip()
                if pin_string:
                    # Split by comma, strip whitespace, convert to int
                    new_gpio_pins = []
                    for pin_str in pin_string.split(","):
                        pin_str = pin_str.strip()
                        if pin_str:
                            pin_num = int(pin_str)
                            # Valid physical pins that can be used as GPIO
                            valid_physical_pins = [3, 7, 8, 10, 11, 12, 13, 15, 16, 18, 19, 21, 22, 23, 24, 26, 29, 31, 32, 33, 35, 36, 37, 38, 40]
                            if pin_num in valid_physical_pins:
                                new_gpio_pins.append(pin_num)
                            else:
                                print(f"Invalid pin number: {pin_num}")
                else:
                    new_gpio_pins = []
                
                if new_gpio_pins != params["gpio_pins"]:
                    params["gpio_pins"] = new_gpio_pins
                    changed = True
                    
            except ValueError as e:
                print(f"Error parsing GPIO pins: {e}")
                # Keep existing pins on error

        if changed:
            init_pins()
            with open(
                "./data/universal_relay_board.json", "w"
            ) as f:  # write the settings to file
                json.dump(params, f, indent=4, sort_keys=True)
        raise web.seeother("/")