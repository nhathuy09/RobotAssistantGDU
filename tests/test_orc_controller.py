from controller.orc_controller import OrcController
import time


orc = OrcController()

if not orc.connect():
    exit(1)
# ==============================
# SERVO
# ==============================
print("Hello")
orc.hello()
time.sleep(2)

print("Idle")
orc.idle()

time.sleep(2)


print("Absolute")
orc.absolute()

time.sleep(2)


# ==============================
# MOTOR
# ==============================

print("Forward")
orc.forward()

time.sleep(1)


print("Backward")
orc.backward()

time.sleep(1)


print("Turn left")
orc.turn_left()

time.sleep(1)


print("Turn right")
orc.turn_right()

time.sleep(1)


# ==============================
# STOP
# ==============================

print("STOP")
orc.stop()


orc.disconnect()