
# blockchain_mock.py
import json
import os
import hashlib
from datetime import datetime

LEDGER_FILE = "ledger.json"

def _load_ledger():
    if not os.path.exists(LEDGER_FILE):
        return {}
    with open(LEDGER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_ledger(data):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def sha256_bytes(data: bytes) -> str:
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
    _save_ledger(ledger)

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
