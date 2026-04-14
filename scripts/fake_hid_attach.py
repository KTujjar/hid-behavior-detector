from evdev import UInput, ecodes as e
import time
cap = {e.EV_KEY: [e.KEY_A, e.KEY_B, e.KEY_ENTER]}
ui = UInput(
    cap,
    name="demo-virtual-keyboard",
    vendor=0x046D,   # vendor id
    product=0xC31C,  # product id
    version=0x0001,
    bustype=e.BUS_USB
)
print("Attached")
time.sleep(5)
ui.close()
print("Detached")
