import time
import board
import busio
import supervisor
import adafruit_amg88xx
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService

i2c = busio.I2C(board.SCL, board.SDA)
amg = None
for address in [0x69, 0x68]:
    try:
        amg = adafruit_amg88xx.AMG88XX(i2c, addr=address)
        break
    except ValueError:
        continue

if not amg:
    print("HARDWARE FAULT: Sensor not detected.")
    while True:
        time.sleep(1)

ble = BLERadio()
ble.name = "OSINT_THERMAL"
uart = UARTService()
advertisement = ProvideServicesAdvertisement(uart)

ble.start_advertising(advertisement)
stream_enabled = False

while True:
    try:
        # 1. Capture Frame Data
        flat_pixels = []
        for row in amg.pixels:
            flat_pixels.extend(row)
        
        # Format string to 1 decimal place to prevent BLE MTU fragmentation
        pixel_strs = ["{:.1f}".format(temp) for temp in flat_pixels]
        out_str = ",".join(pixel_strs)
        
        # 2. Hardware USB Serial Uplink (Always active if USB is connected)
        if supervisor.runtime.serial_connected:
            print(out_str)
            
        # 3. Wireless BLE Uplink (Requires Command-Response Handshake)
        if ble.connected:
            if uart.in_waiting:
                raw_bytes = uart.read(uart.in_waiting)
                if b"START" in raw_bytes:
                    stream_enabled = True
                elif b"STOP" in raw_bytes:
                    stream_enabled = False
                    
            if stream_enabled:
                uart.write((out_str + "\n").encode("utf-8"))
        else:
            stream_enabled = False
            if not ble.advertising:
                try:
                    ble.start_advertising(advertisement)
                except Exception:
                    pass

    except Exception as e:
        pass # Catch anomalies to prevent script termination
        
    time.sleep(0.1) # Maintain 10Hz hardware refresh rate