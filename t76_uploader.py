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
    - libusb backend (Linux/macOS) or WinUSB driver (Windows via Zadig)

-------------------------------------------------------------------------------
Usage:
    python t76_uploader.py <bitstream.bit>

Example:
    python t76_uploader.py my_fpga_config.bit

Ensure the device is connected and the appropriate USB driver is installed.
-------------------------------------------------------------------------------
"""

import ctypes
import ctypes.util
import sys
import os
import struct
import time

# Device Constants
VENDOR_ID = 0xA466
PRODUCT_ID = 0x1A86
ENDPOINT_OUT = 0x01
ENDPOINT_IN = 0x81
TIMEOUT_MS = 5000
BS_PACKET_SIZE = 0x200
T76_WRITE_BITSTREAM = 0x26
T76_BEGIN_BS = 0x00
T76_BS_BLOCK = 0x01
T76_END_BS = 0x02

# Load libusb
libusb_path = ctypes.util.find_library("usb-1.0")
if not libusb_path:
    raise ImportError("libusb-1.0 not found.")
libusb = ctypes.CDLL(libusb_path)

# libusb structures and prototypes
class libusb_device(ctypes.Structure):
    pass

libusb_device_p = ctypes.POINTER(libusb_device)
libusb_device_p_p = ctypes.POINTER(libusb_device_p)
libusb_device_handle_p = ctypes.c_void_p

libusb.libusb_init.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
libusb.libusb_exit.argtypes = [ctypes.c_void_p]
libusb.libusb_get_device_list.argtypes = [ctypes.c_void_p, ctypes.POINTER(libusb_device_p_p)]
libusb.libusb_get_device_descriptor.argtypes = [libusb_device_p, ctypes.POINTER(ctypes.c_ubyte * 18)]
libusb.libusb_open.argtypes = [libusb_device_p, ctypes.POINTER(libusb_device_handle_p)]
libusb.libusb_claim_interface.argtypes = [libusb_device_handle_p, ctypes.c_int]
libusb.libusb_release_interface.argtypes = [libusb_device_handle_p, ctypes.c_int]
libusb.libusb_close.argtypes = [libusb_device_handle_p]
libusb.libusb_bulk_transfer.argtypes = [
    libusb_device_handle_p, ctypes.c_ubyte, ctypes.POINTER(ctypes.c_ubyte),
    ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_uint
]

# T76 device class
class T76Device:
    
    # USB open
    def __init__(self):
        self.ctx = ctypes.c_void_p()
        if libusb.libusb_init(ctypes.byref(self.ctx)) != 0:
            raise RuntimeError("libusb_init failed")

        device_list = libusb_device_p_p()
        count = libusb.libusb_get_device_list(self.ctx, ctypes.byref(device_list))
        if count < 0:
            raise RuntimeError("Failed to get device list")

        self.handle = None
        descriptor = (ctypes.c_ubyte * 18)()

        for i in range(count):
            dev = device_list[i]
            if not dev:
                continue
            if libusb.libusb_get_device_descriptor(dev, ctypes.byref(descriptor)) != 0:
                continue
            vid = descriptor[8] | (descriptor[9] << 8)
            pid = descriptor[10] | (descriptor[11] << 8)
            if vid == VENDOR_ID and pid == PRODUCT_ID:
                handle = libusb_device_handle_p()
                if libusb.libusb_open(dev, ctypes.byref(handle)) == 0:
                    self.handle = handle
                    break

        if not self.handle:
            libusb.libusb_exit(self.ctx)
            raise RuntimeError("Device not found in list")

        if libusb.libusb_claim_interface(self.handle, 0) != 0:
            libusb.libusb_close(self.handle)
            libusb.libusb_exit(self.ctx)
            raise RuntimeError("Failed to claim interface")

    # USB close
    def close(self):
        libusb.libusb_release_interface(self.handle, 0)
        libusb.libusb_close(self.handle)
        libusb.libusb_exit(self.ctx)

    # USB send
    def send(self, data: bytes):
        buf = (ctypes.c_ubyte * len(data))(*data)
        transferred = ctypes.c_int()
        r = libusb.libusb_bulk_transfer(self.handle, ENDPOINT_OUT, buf, len(data),
                                        ctypes.byref(transferred), TIMEOUT_MS)
        if r != 0:
            raise RuntimeError(f"USB send error: {r}")
        

    # USB receive
    def recv(self, size=8):
        buf = (ctypes.c_ubyte * size)()
        transferred = ctypes.c_int()
        r = libusb.libusb_bulk_transfer(self.handle, ENDPOINT_IN, buf, size,
                                        ctypes.byref(transferred), TIMEOUT_MS)
        if r != 0:
            raise RuntimeError(f"USB receive error: {r}")
        
        return bytes(buf[:transferred.value])

    # Write bitstream
    def write_bitstream(self, bitstream: bytes):
        payload_size = BS_PACKET_SIZE - 8
        begin = bytearray(8)
        begin[0] = T76_WRITE_BITSTREAM
        begin[1] = T76_BEGIN_BS
        struct.pack_into('<H', begin, 2, BS_PACKET_SIZE)
        struct.pack_into('<I', begin, 4, len(bitstream))
        self.send(begin)
        resp = self.recv(8)
        if resp[1] != 0:
            raise RuntimeError("Device rejected begin stream command.")

        print("Sending bitstream...")
        for i in range(0, len(bitstream), payload_size):
            chunk = bitstream[i:i + payload_size]
            block = bytearray(BS_PACKET_SIZE)
            block[0] = T76_WRITE_BITSTREAM
            block[1] = T76_BS_BLOCK
            struct.pack_into('<H', block, 2, len(chunk))
            block[8:8 + len(chunk)] = chunk
            self.send(block)
            percent = int((i + len(chunk)) / len(bitstream) * 100)
            print(f"Uploading... {percent:3d}%", end='\r')

        print()
        end = bytearray(8)
        end[0] = T76_WRITE_BITSTREAM
        end[1] = T76_END_BS
        self.send(end)
        resp = self.recv(8)
        if resp[1] != 0:
            raise RuntimeError("Bitstream rejected.")

    # Query device info
    def query_info(self):
        self.send(bytes(8))
        msg = self.recv(80)
        if len(msg) < 64:
            raise RuntimeError("Incomplete device info response.")
        model = "T76"
        mfg_date = msg[8:24].rstrip(b'\x00').decode(errors='ignore')
        device_code = msg[24:32].rstrip(b'\x00').decode(errors='ignore')
        serial = msg[32:56].rstrip(b'\x00').decode(errors='ignore')
        voltage = struct.unpack_from('<I', msg, 56)[0] / 1000.0
        speed = msg[60]
        ext_power = msg[62]
        fw_str = f"{msg[5]}.{msg[4]:02d}"

        print("-----------------Device info:----------------")
        print(f"Model:          {model}")
        print(f"Device code:    {device_code}")
        print(f"Serial number:  {serial}")
        if mfg_date:
            print(f"Manufactured:   {mfg_date}")
        print(f"Firmware:       {fw_str}")
        speed_desc = {0: "12 Mbps (USB 1.1)", 3: "5 Gbps (USB 3.0)"}.get(speed, "480 Mbps (USB 2.0)")
        print(f"USB speed:      {speed_desc}")
        if voltage > 0.0:
            print(f"Supply voltage: {voltage:.2f} V {'(External)' if ext_power else '(USB)'}")
        print()

# Main function
def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <bitstream.bit>")
        sys.exit(1)

    filename = sys.argv[1]
    if not os.path.isfile(filename):
        print("File does not exist.")
        sys.exit(1)

    try:
        dev = T76Device()
        print("Connecting..")
        dev.query_info()
        
        # Open and load file
        with open(filename, 'rb') as f:
            bitstream = f.read()
        print(f"Bitstream size: {len(bitstream)} bytes")
        
        # Write bitstream to device
        dev.write_bitstream(bitstream)
        print("Upload successful.")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        if 'dev' in locals():
            dev.close()
            print("Disconnected.")

if __name__ == "__main__":
    main()
