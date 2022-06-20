#!/usr/bin/env python3

import time
import colorsys
import os
import sys
import ST7735
import urllib2
import requests
import threading
import json
import random

try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError:
    import ltr559

from bme280 import BME280
from enviroplus import gas
from subprocess import PIPE, Popen
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from fonts.ttf import RobotoMedium as UserFont
import logging

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info("""all-in-one.py - Displays readings from all of Enviro plus' sensors
Press Ctrl+C to exit!
""")

# BME280 temperature/pressure/humidity sensor
bme280 = BME280()

# Create ST7735 LCD display class
st7735 = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize display
st7735.begin()

WIDTH = st7735.width
HEIGHT = st7735.height

# Set up canvas and font
img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
path = os.path.dirname(os.path.realpath(__file__))
font_size = 20
font = ImageFont.truetype(UserFont, font_size)

message = ""

# The position of the top bar
top_pos = 25

def thingspeak_post():
    threading.Timer(30,thingspeak_post).start()
    URl='https://api.thingspeak.com/update?api_key='
    KEY='FFITAZO9SSK1CVBH'
    HEADER='&field1={}&field2={}&field3={}&field5={}'.format(get_room_temp(avg_cpu_temp)
                                                                       ,bme280.get_pressure()
                                                                       ,ltr559.get_lux()
                                                                       ,bme280.get_humidity()
                                                                       )
    NEW_URL = URl+KEY+HEADER
    #print(NEW_URL)
    data=urllib2.urlopen(NEW_URL)
    #print(data)
    

# Displays data and text on the 0.96" LCD
def display_text(variable, data, unit):
    
    if ltr559.get_lux() > 2:
        st7735.set_backlight(12)
        # Maintain length of list
        values[variable] = values[variable][1:] + [data]
        # Scale the values for the variable between 0 and 1
        vmin = min(values[variable])
        vmax = max(values[variable])
        colours = [(v - vmin + 1) / (vmax - vmin + 1) for v in values[variable]]
        # Format the variable name and value
        message = "{}: {:.1f} {}".format(variable[:4], data, unit)
        #logging.info(message)
        draw.rectangle((0, 0, WIDTH, HEIGHT), (255, 255, 255))
        for i in range(len(colours)):
            # Convert the values to colours from red to blue
            colour = (1.0 - colours[i]) * 0.6
            r, g, b = [int(x * 255.0) for x in colorsys.hsv_to_rgb(colour, 1.0, 1.0)]
            # Draw a 1-pixel wide rectangle of colour
            draw.rectangle((i, top_pos, i + 1, HEIGHT), (r, g, b))
            # Draw a line graph in black
            line_y = HEIGHT - (top_pos + (colours[i] * (HEIGHT - top_pos))) + top_pos
            draw.rectangle((i, line_y, i + 1, line_y + 1), (0, 0, 0))
        # Write the text at the top in black
        draw.text((0, 0), message, font=font, fill=(0, 0, 0))
        st7735.display(img)
    else:
        draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
        st7735.display(img)
        st7735.set_backlight(0)


# Get the temperature of the CPU for compensation
def get_cpu_temperature():
    process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE, universal_newlines=True)
    output, _error = process.communicate()
    return float(output[output.index('=') + 1:output.rindex("'")])


# Tuning factor for compensation. Decrease this number to adjust the
# temperature down, and increase to adjust up
factor = 2.25

cpu_temps = [get_cpu_temperature()] * 5
avg_cpu_temp = 0 

delay = 1  # Debounce the proximity tap
mode = 0  # The starting mode
last_page = 0
light = 1

# Create a values dict to store the data
variables = ["temperature",
             "pressure",
             "humidity",
             "light"]

values = {}

for v in variables:
    values[v] = [1] * WIDTH
    
def get_room_temp(avg_cpu_temp):
    raw_temp = bme280.get_temperature()
    data = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
    return data
    

# The main loop
try:
    thingspeak_post()
    while True:
        proximity = ltr559.get_proximity()

        # If the proximity crosses the threshold, toggle the mode
        if proximity > 1500 and time.time() - last_page > delay:
            mode += 1
            mode %= len(variables)
            last_page = time.time()

        # One mode for each variable
        if mode == 0:
            # variable = "temperature"
            unit = "C"
            cpu_temp = get_cpu_temperature()
            # Smooth out with some averaging to decrease jitter
            cpu_temps = cpu_temps[1:] + [cpu_temp]
            avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
            display_text(variables[mode], get_room_temp(avg_cpu_temp), unit)


        if mode == 1:
            # variable = "pressure"
            unit = "hPa"
            data = bme280.get_pressure()
            display_text(variables[mode], data, unit)

        if mode == 2:
            # variable = "humidity"
            unit = "%"
            data = bme280.get_humidity()
            display_text(variables[mode], data, unit)

        if mode == 3:
            # variable = "light"
            unit = "Lux"
            if proximity < 10:
                data = ltr559.get_lux()
            else:
                data = 1
            display_text(variables[mode], data, unit)
            



# Exit cleanly
except KeyboardInterrupt:
    st7735.set_backlight(0)
    sys.exit(0)
