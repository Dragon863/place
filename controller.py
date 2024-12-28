from PIL import Image
import serial
import time
import struct

START_MARKER = 0xFF
PORT = "/dev/ttyUSB0"
BAUDRATE = 115200
DEBUG = False

try:
    ser = serial.Serial(PORT, BAUDRATE, timeout=1)
except serial.SerialException as e:
    if DEBUG:
        ser = None
    else:
        raise e

time.sleep(
    1
)  # Wait for the serial connection to be established. SHould this be necessary? No. But it is.


def send_image_to_esp32(image_path):
    img = Image.open(image_path).convert("RGB")
    img = img.resize((64, 64))

    # create a buffer for all pixels with start marker,and checksum
    pixel_data = bytearray()
    toReturn = []

    for y in range(64):
        toReturn.append([])
        for x in range(64):
            toReturn[y].append([])
            r, g, b = img.getpixel((x, y))

            # now calculate checksum (x, y, r, g, b)
            checksum = x ^ y ^ r ^ g ^ b

            # time to add start marker, pixel data, and checksum
            packet = (
                struct.pack("B", START_MARKER)
                + struct.pack("BBB", x, y, r)
                + struct.pack("BB", g, b)
                + struct.pack("B", checksum)
            )
            pixel_data += packet
            toReturn[y][x] = [r, g, b]

    ser.write(pixel_data)
    return toReturn


def clear_canvas():
    set_pixel_color(244, 0, 0, 0, 0)  # Magic number to clear the canvas


def set_pixel_color(x, y, r, g, b):
    packet = (
        struct.pack("B", START_MARKER)
        + struct.pack("BBB", x, y, r)
        + struct.pack("BB", g, b)
        + struct.pack("B", x ^ y ^ r ^ g ^ b)
    )
    ser.write(packet)


if __name__ == "__main__":
    image_path = "/home/daniel/Pictures/hackclub.jpg"
    serial_port = "/dev/ttyUSB0"

    send_image_to_esp32(image_path)
    set_pixel_color(0, 0, 0, 255, 0)
    ser.close()
