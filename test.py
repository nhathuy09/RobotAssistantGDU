import serial
import time

ser = serial.Serial(
    "/dev/ttyACM0",
    115200,
    timeout=1
)

print("Connected")

time.sleep(2)

ser.write(b"W")
ser.flush()

print("Sent W")

time.sleep(2)

ser.write(b"X")
ser.flush()

print("Sent X")

ser.close()