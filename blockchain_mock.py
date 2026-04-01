
import json
import os
import hashlib
from datetime import datetime


LEDGER_FILE = "/tmp/ledger.json"  

def _load_ledger():
    """Đọc ledger từ file"""
    if not os.path.exists(LEDGER_FILE):
        return {}
    try:
        with open(LEDGER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        # Nếu file bị lỗi, trả về ledger rỗng
        return {}

def _save_ledger(data):
    """Lưu ledger vào file"""
    try:
        # Đảm bảo thư mục tồn tại
        os.makedirs(os.path.dirname(LEDGER_FILE), exist_ok=True)
        
        with open(LEDGER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving ledger: {e}")
        return False

def sha256_bytes(data: bytes) -> str:
    """Tính hash SHA256 của bytes data"""
    return hashlib.sha256(data).hexdigest()

def register_image(image_bytes, watermark_text, author_info: dict, bits_len: int):
    """
    Giả lập ghi lên blockchain:
    - tính hash ảnh
    - tính hash watermark
    - lưu record vào ledger.json
    """
    ledger = _load_ledger()

    image_hash = sha256_bytes(image_bytes)
    wm_hash = sha256_bytes(watermark_text.encode("utf-8"))

    record = {
        "image_hash": image_hash,
        "watermark_hash": wm_hash,
        "author": author_info,
        "bits_length": bits_len,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    # key bằng image_hash
    ledger[image_hash] = record
    
    # Lưu lại ledger
    if not _save_ledger(ledger):
        raise Exception("Không thể lưu ledger")

    # giả lập tx_hash (hash của concatenation)
    tx_hash = sha256_bytes((image_hash + wm_hash).encode("utf-8"))
    return tx_hash, record

def verify_image(image_bytes):
    """
    - Tính hash ảnh
    - Tìm record trong ledger.json
    """
    ledger = _load_ledger()
    image_hash = sha256_bytes(image_bytes)
    record = ledger.get(image_hash)
    return image_hash, record

def get_all_records():
    """Lấy tất cả records (cho mục đích debugging)"""
    return _load_ledger()

def clear_ledger():
    """Xóa toàn bộ ledger (chỉ dùng cho testing)"""
    if os.path.exists(LEDGER_FILE):
        os.remove(LEDGER_FILE)
    return {}

def get_stats():
    """Lấy thống kê về ledger"""
    ledger = _load_ledger()
    return {
        "total_records": len(ledger),
        "ledger_file": LEDGER_FILE,
        "file_exists": os.path.exists(LEDGER_FILE)
    }
