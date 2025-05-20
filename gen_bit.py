"""
===============================================================================
Anlogic EG4 Bitstream Block Processor for XGecu T76
Author: radiomanV
===============================================================================

This program processes a binary input file consisting of structured data blocks.
Each block starts with a 4-byte header:
    - 2 bytes: Block size
    - 1 byte: Command ID
    - 1 byte: Flag
    - 2 bytes: Size (big-endian)

The binary file may contain an ASCII header section (terminated by b'\x0A\x0A'),
which is parsed separately. Some blocks include CRC-16/BUYPASS checks for integrity.

Key features:
-------------------------------------------------------------------------------
- Parses and filters blocks based on their command type.
- Validates CRC-16 for applicable blocks using the BUYPASS variant.
- Extracts and prints device information (e.g. Device ID, Frame Info).
- Identifies and handles valid/invalid frame data regions.
- Skips known padding or invalid blocks.
- Ensures the final output file has even length for alignment.
- Detects SOF and EOF via two consecutive 16-byte blocks of 0xFF.

Special block handling:
-------------------------------------------------------------------------------
- CMD_DEVICE_ID  : Extracts and prints device ID.
- CMD_FRAME_INFO : Extracts number of frames and frame size.
- CMD_FRAME_DATA : Validates frame structure; skips or processes accordingly.
- CMD_RESET_CRC  : Accepted only once.
- CMD_END_DATA   : Resets EOF tracking.
- Other commands may be skipped or passed through based on configuration.
"""

import sys
import re
from typing import List
from struct import pack
from io import BytesIO

# Command Byte Definitions
CMD_DEVICE_ID       = 0xf0
CMD_RESET_CRC       = 0xf1
CMD_UNK_1           = 0xf3
CMD_UNK_2           = 0xf5
CMD_END_DATA        = 0xf7
CMD_FRAME_INFO      = 0xc7
CMD_FRAME_DATA      = 0xec

PADDING_SIZE = 19
UINT16_MAX = 0xFFFF
MARKER = 0x0000

START_SIGNATURE = bytes([0xCC, 0x55, 0xAA, 0x33])

'''
# Compress bistream
def deflate_bitstream(input_data: List[int]) -> bytearray:
    """Compress input_data using zero-run-length encoding with marker escape."""
    output = BytesIO()
    i = 0
    count = len(input_data)

    while i < count:
        val = input_data[i]

        if val == 0:
            # Count zero run (up to UINT16_MAX)
            run_len = 0
            while i < count and input_data[i] == 0 and run_len < UINT16_MAX:
                i += 1
                run_len += 1
            output.write(pack('<HH', MARKER, run_len))
        elif val == MARKER:
            # Escape a literal 0x0000 value
            output.write(pack('<HH', MARKER, MARKER))
            i += 1
        else:
            # Literal word
            output.write(pack('<H', val))
            i += 1

    return bytearray(output.getvalue())
'''

# Compute CRC-16/BYPASS
def crc16_buypass(data: bytes) -> int:
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x8005) & 0xffff
            else:
                crc = (crc << 1) & 0xffff
    return crc
    

# Validate CRC-16
def validate_crc16_block(data_block: bytes) -> bool:
    if len(data_block) < 2:
        print("Error: Block too short to contain CRC.")
        return True

    crc_expected = int.from_bytes(data_block[-2:], byteorder='big')
    crc_computed = crc16_buypass(data_block[:-2])

    if crc_computed != crc_expected:
        print(f"Error: CRC mismatch. Expected 0x{crc_expected:04X}, got 0x{crc_computed:04X}")
        return True

    return False

# Return True if start signature is found
def is_signature_start(blocks):
    return (
        len(blocks) == 3 and
        blocks[0] == b'\xff' * 16 and
        blocks[1] == b'\xff' * 16 and
        blocks[2] == START_SIGNATURE
    )


# Process all incoming data blocks
def process_block(data_block: bytes, block_num: int) -> bytes:
    if len(data_block) < 4:
        print(f"Block {block_num}: Too short to contain required header")
        return data_block
        
    # Skip all blocks after the EOF marker
    if hasattr(process_block, "eof") and process_block.eof == 2:
        return None

    # Skip invalid frame data after invalid CMD_FRAME_DATA
    if getattr(process_block, "skip_bytes_remaining", 0) > 0:
        skip_now = min(len(data_block), process_block.skip_bytes_remaining)
        process_block.skip_bytes_remaining -= skip_now
        #print(f"Skipping {skip_now} bytes of invalid frame data (remaining: {process_block.skip_bytes_remaining})")
        return None


    # Process valid frame data after valid CMD_FRAME_DATA
    if getattr(process_block, "frames", 0) > 0:
        frame = process_block.num_frames - process_block.frames
        #if set(data_block) == {0}:
            #print(f"Frame {frame} of {len(data_block)} blank.")
        if frame > 0 and validate_crc16_block(data_block):
            print(f"Frame {frame} of {len(data_block)} bytes bad CRC")
            sys.exit(1)
        process_block.frames -= 1
        #print(f"Frame {frame} of {len(data_block)} bytes CRC ok.")
        return data_block

    cmd = data_block[0]
    flag = data_block[1]
    size = int.from_bytes(data_block[2:4], byteorder='big')
    payload = data_block[4:]

    SKIPPED_COMMANDS = {CMD_UNK_1, CMD_UNK_2}
    if cmd in SKIPPED_COMMANDS:
        return None

    # Only allow first CMD_RESET_CRC command
    if cmd == CMD_RESET_CRC:
        if not getattr(process_block, "reset_crc", False):
            process_block.reset_crc = True
            return data_block
        return None

    # Detect EOF signature: 2 consecutive 16-byte blocks of 0xFF
    if data_block == b'\xff' * 16:
        process_block.eof = getattr(process_block, "eof", 0) + 1
        if process_block.eof == 2:
            print("EOF signature found.")
        return data_block

    # Parse CMD_DEVICE_ID
    if cmd == CMD_DEVICE_ID:
        if len(payload) != size:
            print(f"Block {block_num}: Size mismatch, expected {size} payload bytes, got {len(payload)}")
            return None
        if flag == 0 and size >= 2:
            if validate_crc16_block(data_block):
                sys.exit(1)
            digits = f"{int.from_bytes(payload[:-2], 'big'):X}"
            if len(digits) % 2 != 0:
                digits = "0" + digits
            print(f"Device ID: 0x{digits}")
        return data_block

    # Parse CMD_FRAME_INFO
    if cmd == CMD_FRAME_INFO:
        if len(payload) != size:
            print(f"Block {block_num}: Size mismatch, expected {size} payload bytes, got {len(payload)}")
            return None
        if flag == 0 and size >= 2:
            if validate_crc16_block(data_block):
                sys.exit(1)
            process_block.num_frames = int.from_bytes(payload[0:2], 'big')
            process_block.frame_size = int.from_bytes(payload[2:4], 'big')
            print(f"Number of frames: {process_block.num_frames}\nFrame size: {process_block.frame_size} bytes")
        return data_block

    # Parse CMD_FRAME_DATA
    if cmd == CMD_FRAME_DATA and flag != 0:
        if not hasattr(process_block, "num_frames"):
            print(f"Block {block_num}: CMD_FRAME_DATA received before CMD_FRAME_INFO.")
            return None
        if size != process_block.num_frames:
            total_block_size = size * (process_block.frame_size + 6)
            #print(f"\nSkipped frame data block {block_num} with length {total_block_size} bytes")
            process_block.skip_bytes_remaining = size * process_block.frame_size + PADDING_SIZE
            return None
        print(f"\nFound {size} frames on block {block_num}")
        process_block.frames = size
        return data_block

    # Parse CMD_END_DATA
    if cmd == CMD_END_DATA and flag == 0:
        print(f"End of data found on block {block_num}")
        process_block.eof = 0
        return data_block

    return data_block

# Process a bitstream file genearted by Anlogic TD and generate a stripped down version for T76 
def process_file(input_file, output_file):
    with open(input_file, "rb") as f:
        content = f.read()

    # Find and print the header
    header_end_idx = content.find(b'\x0a\x0a')
    if header_end_idx == -1:
        print("Error: SOF terminator (0x0a 0x0a) not found.")
        return

    header_bytes = content[:header_end_idx]
    try:
        header_text = header_bytes.decode('utf-8', errors='replace')
    except UnicodeDecodeError:
        header_text = "<header could not be decoded>"
        sys.exit(1)
        
    # Extract file CRC
    '''
    match = re.search(r"# Bitstream CRC:\s*([01]{16})", header_text)
    if match:
        print(f"Bitstream CRC: 0x{int(match.group(1), 2):04X}")
    '''
    
    offset = header_end_idx + 2
    output_data = bytearray()
    total_blocks = 0
    pending_signature_blocks = []
    
    print("\n-----------------Bitstream info:----------------")
    print(header_text)
    print("------------------------------------------------\n")

    # Collect and verify the first three blocks for the signature
    while len(pending_signature_blocks) < 3 and offset + 2 <= len(content):
        size_bits = int.from_bytes(content[offset:offset+2], byteorder='big')
        offset += 2
        size_bytes = size_bits // 8

        if offset + size_bytes > len(content):
            print("Error: Unexpected end of file while reading SOF signature blocks.")
            return

        block = content[offset:offset + size_bytes]
        offset += size_bytes
        pending_signature_blocks.append(block)
        total_blocks += 1

    if not is_signature_start(pending_signature_blocks):
        print("Error: SOF signature not found. Aborting.")
        return
    else:
        print("SOF signature found.")
        for b in pending_signature_blocks:
            output_data.extend(b)

    # Process remaining blocks
    while offset + 2 <= len(content):
        size_bits = int.from_bytes(content[offset:offset+2], byteorder='big')
        offset += 2
        size_bytes = size_bits // 8

        if offset + size_bytes > len(content):
            print(f"Warning: Incomplete block at block {total_blocks + 1}.")
            break

        block = content[offset:offset + size_bytes]
        offset += size_bytes
        total_blocks += 1

        processed = process_block(block, total_blocks)
        if processed is not None:
            output_data.extend(processed)


    # Ensure output is even sized
    if len(output_data) % 2 != 0:
        output_data.append(0x00)
        
    # Compress bitstream
    #compressed = deflate_bitstream(output_data)

    with open(output_file, "wb") as f_out:
        f_out.write(output_data)

    print(f"\nProcessed {total_blocks} blocks and wrote {len(output_data)} bytes to {output_file}.")
    #print(f"Compressed size: {len(compressed)} bytes")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} input_file output_file")
    else:
        process_file(sys.argv[1], sys.argv[2])
