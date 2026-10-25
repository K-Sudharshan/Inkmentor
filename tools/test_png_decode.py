import zlib
import struct
import base64

def decode_png(png_bytes):
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Invalid PNG signature")
    idx = 8
    width = height = None
    bit_depth = color_type = None
    idat_chunks = []
    while idx < len(png_bytes):
        length = struct.unpack(">I", png_bytes[idx:idx+4])[0]
        ctype = png_bytes[idx+4:idx+8]
        data = png_bytes[idx+8:idx+8+length]
        idx += 12 + length
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", data[:13])
        elif ctype == b"IDAT":
            idat_chunks.append(data)
        elif ctype == b"IEND":
            break

    raw = zlib.decompress(b"".join(idat_chunks))
    bpp = 4 if color_type == 6 else (3 if color_type == 2 else 1)
    stride = width * bpp
    pixels = bytearray(width * height * 4)

    # Defilter scanlines
    prev_row = bytearray(stride)
    raw_idx = 0
    out_idx = 0

    for r in range(height):
        filter_type = raw[raw_idx]
        raw_idx += 1
        curr_row = bytearray(raw[raw_idx:raw_idx+stride])
        raw_idx += stride

        if filter_type == 0: # None
            pass
        elif filter_type == 1: # Sub
            for c in range(bpp, stride):
                curr_row[c] = (curr_row[c] + curr_row[c - bpp]) & 0xFF
        elif filter_type == 2: # Up
            for c in range(stride):
                curr_row[c] = (curr_row[c] + prev_row[c]) & 0xFF
        elif filter_type == 3: # Average
            for c in range(stride):
                left = curr_row[c - bpp] if c >= bpp else 0
                curr_row[c] = (curr_row[c] + ((left + prev_row[c]) >> 1)) & 0xFF
        elif filter_type == 4: # Paeth
            for c in range(stride):
                a = curr_row[c - bpp] if c >= bpp else 0
                b = prev_row[c]
                c_val = prev_row[c - bpp] if c >= bpp else 0
                p = a + b - c_val
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c_val)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c_val)
                curr_row[c] = (curr_row[c] + pr) & 0xFF

        prev_row = curr_row

        if bpp == 4:
            pixels[out_idx:out_idx+stride] = curr_row
            out_idx += stride
        elif bpp == 3:
            for x in range(width):
                pixels[out_idx] = curr_row[x*3]
                pixels[out_idx+1] = curr_row[x*3+1]
                pixels[out_idx+2] = curr_row[x*3+2]
                pixels[out_idx+3] = 255
                out_idx += 4

    return width, height, pixels

if __name__ == "__main__":
    # Test on an existing PNG if available
    for p in ["caveat_integral_screenshot.png", "tools/line_by_line_final.png"]:
        try:
            with open(p, "rb") as f:
                w, h, pix = decode_png(f.read())
                print(f"Decoded {p}: {w}x{h}, pixels len={len(pix)}")
                break
        except Exception as e:
            print(f"Could not decode {p}: {e}")
