# XGecu T76

## Documentation and Utilities for the XGecu T76 Programmer

Here you can find a useful script for converting a bitstream file generated by the Anlogic TD IDE  
into a format accepted by the XGecu T76 programmer.

Also included is a simple Verilog design for testing the FPGA on the XGecu T76.

---

## Bitstream Conversion

You can convert the bitstream generated by TD IDE using the following command:

```bash
python3 gen_bit.py T76.bit out.bit
```

The resulting `out.bit` file can be uploaded to the T76 FPGA.

---

## Bitstream Upload

To upload the converted bitstream to the T76 device, use the included uploader script:

```bash
python3 t76_uploader.py out.bit
```

### Example:

```bash
python3 t76_uploader.py test_design.bit
```

---

## Requirements

- Python 3.x


- **libusb backend:**
  - **Linux/macOS:**  
    Make sure `libusb-1.0` is installed:

    ```bash
    sudo apt install libusb-1.0-0-dev
    ```

  - **Windows:**  
    Use [Zadig](https://zadig.akeo.ie/) to install the **WinUSB driver** for the T76 device.


## License

This project is released under [The Unlicense](https://unlicense.org/).  
You are free to do anything with this software.
