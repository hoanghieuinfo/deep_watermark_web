
# watermark.py
import cv2
import numpy as np
from PIL import Image
import io

def text_to_bits(text):
    # chuyển text -> chuỗi bit '010101...'
    return ''.join(format(ord(c), '08b') for c in text)

def bits_to_text(bits):
    # chia 8 bit -> char
    chars = []
    for i in range(0, len(bits), 8):
        byte = bits[i:i+8]
        if len(byte) < 8:
            break
        chars.append(chr(int(byte, 2)))
    return ''.join(chars)

def embed_watermark_lsb(image_bytes, watermark_text, max_len=1024):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = np.array(image)

    h, w, c = img.shape
    capacity = h * w  # mỗi pixel dùng 1 bit
    bits = text_to_bits(watermark_text)

    if len(bits) > min(capacity, max_len):
        bits = bits[:min(capacity, max_len)]

    pad_len = (8 - (len(bits) % 8)) % 8
    bits_padded = bits + '0' * pad_len

    flat = img.reshape(-1, 3)
    g_channel = flat[:, 1]  # kênh G

    for i, bit in enumerate(bits_padded):
        if i >= capacity:
            break
        g_val = int(g_channel[i])
        g_val = (g_val & 0xFE) | int(bit)   # dùng 0xFE thay cho ~1
        g_channel[i] = np.uint8(g_val)

    flat[:, 1] = g_channel
    img_stego = flat.reshape(h, w, 3)

    out_image = Image.fromarray(img_stego.astype('uint8'))
    buffer = io.BytesIO()
    out_image.save(buffer, format="PNG")
    return buffer.getvalue(), len(bits)



def extract_watermark_lsb(image_bytes, bits_length):
    """
    image_bytes: ảnh đã nhúng
    bits_length: số bit watermark gốc (đã lưu lúc embed)
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = np.array(image)
    h, w, c = img.shape

    flat = img.reshape(-1, 3)
    g_channel = flat[:, 1]

    bits = []
    for i in range(bits_length):
        bit = g_channel[i] & 1
        bits.append(str(bit))

    bits_str = ''.join(bits)
    text = bits_to_text(bits_str)
    return text
