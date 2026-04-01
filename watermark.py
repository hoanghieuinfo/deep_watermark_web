# watermark.py
import numpy as np
from PIL import Image
import io
import time

def embed_watermark_lsb(image_bytes, watermark_text):
    """
    Nhúng watermark vào ảnh sử dụng phương pháp LSB
    """
    try:
        print(f"Starting watermark embedding...")  # Debug log
        start_time = time.time()
        
        # Kiểm tra watermark text
        if not watermark_text:
            raise ValueError("Watermark text is empty")
        
        # Giới hạn độ dài watermark để tránh treo
        if len(watermark_text) > 500:
            watermark_text = watermark_text[:500]
            print(f"Watermark truncated to 500 chars")
        
        # Đọc ảnh từ bytes
        img = Image.open(io.BytesIO(image_bytes))
        print(f"Image loaded: {img.size}, mode: {img.mode}")
        
        # Chuyển sang RGB nếu cần
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Chuyển thành numpy array
        img_array = np.array(img)
        print(f"Image array shape: {img_array.shape}")
        
        # Chuyển watermark thành binary
        watermark_binary = ''.join(format(ord(char), '08b') for char in watermark_text)
        watermark_binary += '1111111111111110'  # Delimiter
        print(f"Watermark binary length: {len(watermark_binary)} bits")
        
        # Làm phẳng mảng ảnh
        flat_array = img_array.flatten()
        total_pixels = len(flat_array)
        print(f"Total pixels: {total_pixels}")
        
        # Kiểm tra watermark có vừa với ảnh không
        if len(watermark_binary) > total_pixels:
            raise ValueError(f"Watermark too long: {len(watermark_binary)} bits, max {total_pixels} bits")
        
        # Nhúng watermark
        for i in range(len(watermark_binary)):
            if i % 10000 == 0:  # Log mỗi 10,000 bits
                print(f"Embedding progress: {i}/{len(watermark_binary)} bits")
            
            # Đảm bảo giá trị pixel hợp lệ
            pixel_value = int(flat_array[i])
            bit = int(watermark_binary[i])
            flat_array[i] = (pixel_value & 0xFE) | bit
        
        # Tái tạo ảnh
        embedded_array = flat_array.reshape(img_array.shape)
        embedded_img = Image.fromarray(embedded_array.astype('uint8'))
        
        # Chuyển thành bytes
        output_bytes = io.BytesIO()
        embedded_img.save(output_bytes, format='PNG', optimize=True)
        output_bytes = output_bytes.getvalue()
        
        elapsed_time = time.time() - start_time
        print(f"Embedding completed in {elapsed_time:.2f} seconds")
        
        # Trả về ảnh đã nhúng và số bits đã dùng
        return output_bytes, len(watermark_binary)
    
    except Exception as e:
        print(f"Error in embed_watermark_lsb: {str(e)}")
        raise Exception(f"Lỗi nhúng watermark: {str(e)}")

def extract_watermark_lsb(image_bytes, bits_length):
    """
    Trích xuất watermark từ ảnh
    """
    try:
        print(f"Starting watermark extraction...")
        start_time = time.time()
        
        # Đọc ảnh
        img = Image.open(io.BytesIO(image_bytes))
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        img_array = np.array(img)
        flat_array = img_array.flatten()
        
        # Giới hạn số bits cần đọc
        max_bits = min(bits_length + 16, len(flat_array))
        print(f"Extracting {max_bits} bits")
        
        # Trích xuất LSB
        extracted_binary = ''
        delimiter = '1111111111111110'
        
        for i in range(max_bits):
            extracted_binary += str(flat_array[i] & 1)
            
            # Kiểm tra delimiter
            if len(extracted_binary) >= len(delimiter) and extracted_binary.endswith(delimiter):
                extracted_binary = extracted_binary[:-len(delimiter)]
                break
        
        # Chuyển binary thành text
        watermark_text = ''
        for i in range(0, len(extracted_binary), 8):
            if i + 8 <= len(extracted_binary):
                byte = extracted_binary[i:i+8]
                try:
                    char_code = int(byte, 2)
                    if 32 <= char_code <= 126:  # Chỉ lấy ký tự in được
                        watermark_text += chr(char_code)
                except:
                    pass
        
        elapsed_time = time.time() - start_time
        print(f"Extraction completed in {elapsed_time:.2f} seconds")
        
        return watermark_text if watermark_text else "Không tìm thấy watermark hợp lệ"
    
    except Exception as e:
        print(f"Error in extract_watermark_lsb: {str(e)}")
        raise Exception(f"Lỗi trích xuất watermark: {str(e)}")
