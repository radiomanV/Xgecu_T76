"""
===============================================================================
XGecu T76 Bitstream Uploader
Author: radiomanV
===============================================================================

This program uploads a custom FPGA bitstream to the XGecu T76 device via USB.

The uploader uses the T76's bulk transfer protocol with endpoint 0x01 (OUT)
for sending commands and data, and 0x81 (IN) for receiving status responses.

-------------------------------------------------------------------------------
Requirements:
    - Python 3.x
    - PyUSB (install with: pip install pyusb)
    - libusb backend (Linux/macOS) or WinUSB driver (Windows via Zadig)

-------------------------------------------------------------------------------
Usage:
    python t76_uploader.py <bitstream.bit>

Example:
    python t76_uploader.py my_fpga_config.bit

Ensure the device is connected and the appropriate USB driver is installed.
-------------------------------------------------------------------------------
"""


import usb.core
import usb.util
import struct
import sys
import os
import time
from usb.core import USBError

# Device constants
VENDOR_ID = 0xA466
PRODUCT_ID = 0x1A86
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81
TIMEOUT_MS = 5000

# Protocol constants
BS_PACKET_SIZE = 0x200
T76_WRITE_BITSTREAM = 0x26
T76_BEGIN_BS = 0x00
T76_BS_BLOCK = 0x01
T76_END_BS = 0x02

MP_STATUS_BOOTLOADER = 2
MP_STATUS_NORMAL = 1

class T76Device:
    def __init__(self):
        self.dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if self.dev is None:
            raise RuntimeError("USB device not found.")
        self.dev.set_configuration()
        cfg = self.dev.get_active_configuration()
        self.intf = cfg[(0, 0)]

        if self.dev.is_kernel_driver_active(self.intf.bInterfaceNumber):
            self.dev.detach_kernel_driver(self.intf.bInterfaceNumber)

        usb.util.claim_interface(self.dev, self.intf.bInterfaceNumber)

    def close(self):
        usb.util.release_interface(self.dev, self.intf.bInterfaceNumber)
        usb.util.dispose_resources(self.dev)

    def send(self, data):
        try:
            self.dev.write(ENDPOINT_OUT, data, timeout=TIMEOUT_MS)
        except USBError as e:
            raise RuntimeError(f"USB send error: {e}")

    def recv(self, size=80):
        try:
            return self.dev.read(ENDPOINT_IN, size, timeout=TIMEOUT_MS).tobytes()
        except USBError as e:
            raise RuntimeError(f"USB receive error: {e}")

    def query_info(self):
        self.send(bytes(8))  # Send 8 zero bytes
        msg = self.recv(80)
        return self._parse_info(msg)

    def _parse_info(self, msg):
        if len(msg) < 64:
            raise ValueError("Incomplete device info response.")

        status = MP_STATUS_BOOTLOADER if msg[4] == 0 else MP_STATUS_NORMAL
        model = "T76"
        mfg_date = msg[8:24].rstrip(b'\x00').decode(errors='ignore')
        device_code = msg[24:32].rstrip(b'\x00').decode(errors='ignore')
        serial = msg[32:56].rstrip(b'\x00').decode(errors='ignore')
        voltage = struct.unpack_from('<I', msg, 56)[0] / 1000.0
        speed = msg[60]
        ext_power = msg[62]
        hw = 0
        fw_str = f"{hw:02d}.{msg[5]}.{msg[4]:02d}"

        if status == MP_STATUS_BOOTLOADER:
            raise RuntimeError(f"{model} is in bootloader mode.")

        speed_desc = {0: "12 Mbps (USB 1.1)", 3: "5 Gbps (USB 3.0)"}.get(speed, "480 Mbps (USB 2.0)")
        power_source = "(External)" if ext_power else "(USB)"

        print("-----------------Device info:----------------")
        print(f"Model:          {model}")
        print(f"Device code:    {device_code}")
        print(f"Serial number:  {serial}")
        if mfg_date:
            print(f"Manufactured:   {mfg_date}")
        print(f"Firmware:       {fw_str}")
        print(f"USB speed:      {speed_desc}")
        if voltage > 0.0:
            print(f"Supply voltage: {voltage:.2f} V {power_source}")
        print()
        return status

    def write_bitstream(self, bitstream: bytes):
        payload_size = BS_PACKET_SIZE - 8
        total_len = len(bitstream)

        # BEGIN packet (8 bytes)
        begin = bytearray(8)
        begin[0] = T76_WRITE_BITSTREAM
        begin[1] = T76_BEGIN_BS
        struct.pack_into('<H', begin, 2, BS_PACKET_SIZE)
        struct.pack_into('<I', begin, 4, total_len)
        self.send(begin)
        resp = self.recv(8)
        if resp[1] != 0:
            raise RuntimeError("Device rejected begin stream command.")

        # Send all bitstream blocks
        for i in range(0, total_len, payload_size):
            chunk = bitstream[i:i + payload_size]
            block = bytearray(BS_PACKET_SIZE)
            block[0] = T76_WRITE_BITSTREAM
            block[1] = T76_BS_BLOCK
            struct.pack_into('<H', block, 2, len(chunk))
            block[8:8 + len(chunk)] = chunk
            self.send(block)
            percent = int((i + len(chunk)) / total_len * 100)
            print(f"\rUploading... {percent:3d}%", end='', flush=True)

        # END packet (8 bytes)
        print()
        end = bytearray(8)
        end[0] = T76_WRITE_BITSTREAM
        end[1] = T76_END_BS
        self.send(end)
        try:
            resp = self.recv(16)
            if resp[1] != 0:
                raise RuntimeError("Bitstream rejected.")
        except USBError as e:
            raise RuntimeError(f"Failed to read response: {e}")


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <bitstream.bit>")
        sys.exit(1)

    filename = sys.argv[1]
    if not os.path.isfile(filename):
        print("Error: File does not exist.")
        sys.exit(1)

    try:
        print("Connecting..")
        dev = T76Device()
        dev.query_info()

        with open(filename, 'rb') as f:
            bitstream = f.read()
        print(f"Bitstream size: {len(bitstream)} bytes")

        dev.write_bitstream(bitstream)
        print("Bitstream upload successful.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        if 'dev' in locals():
            try:
                dev.dev.reset() 
            except Exception:
                pass
            dev.close()
            print("Disconnected.")

if __name__ == "__main__":
    main()
