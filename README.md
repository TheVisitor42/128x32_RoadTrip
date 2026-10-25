# 128x32_RoadTrip
A fun video of a car driving on a roadtrip made for a 128x32 display. It travels through different biomes and have some cut scenes.
Its mostly an orthographic view with some 2D animations.

I'm running this with a Raspberry Pi Pico and an I2C connection to the Adafruit 128x32 2.23" OLED Bonnet. Though with some small changes to the code it should work with any 128x32 OLED display.

The trip was inspired by the lofi music channels on youtube with minimal movements of the main subject and their environment being the thing that changes. In this example parallax is used to give the feeling of the car moving through the country. Occasionally another vehicle will come along and pass the car or get passed by it.  

The car travels through these biomes:
- Desert
- Farmland
- Forest
- Mountains
- Big City
- Coastal City
- The Grid

There are these cut scenes that happen during the trip:
- Gas station (Desert)
- Tunnel (Mountains)

Some fun things that will appear during the trip unexpectedly are:
- A UFO
- Shooting stars

Weather events:
- Rain
- Snow

Traffic:
- Speeding car
- Slow car
- Tractor
- Big Rig
- Light Cycle

There are 3 car designs of the main character's car. Every time the trip starts over at the gas station it will cycle the car out with the next design.

-----
Objects in the display are saved mainly as bitmaps. The speed of the parallax can be changed with the variables.

This is still a work in progress so don't judge me too harshly if something looks silly. 
