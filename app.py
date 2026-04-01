# -*- coding: utf-8 -*-

# app.py
import os
import time
import threading
from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from io import BytesIO

from watermark import embed_watermark_lsb, extract_watermark_lsb
import blockchain_mock as bc

# Sử dụng /tmp/uploads cho file tạm
UPLOAD_FOLDER = "/tmp/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "super-secret-key"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/embed", methods=["POST"])
def embed():
    try:
        if "image" not in request.files:
            flash("Vui lòng chọn ảnh", "error")
            return redirect(url_for("index"))

        file = request.files["image"]
        if file.filename == "":
            flash("Vui lòng chọn ảnh hợp lệ", "error")
            return redirect(url_for("index"))

        # Kiểm tra kích thước file
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 10 * 1024 * 1024:
            flash("Ảnh quá lớn (tối đa 10MB)", "error")
            return redirect(url_for("index"))
        
        watermark_text = request.form.get("watermark_text", "")
        author_name = request.form.get("author_name", "")
        author_email = request.form.get("author_email", "")
        author_link = request.form.get("author_link", "")

        if not watermark_text:
            flash("Vui lòng nhập nội dung watermark", "error")
            return redirect(url_for("index"))
        
        # Giới hạn độ dài watermark
        if len(watermark_text) > 500:
            watermark_text = watermark_text[:500]
            flash("Watermark quá dài, đã cắt xuống 500 ký tự", "info")

        # Đọc file ảnh
        image_bytes = file.read()
        
        flash("Đang xử lý ảnh, vui lòng chờ...", "info")
        
        # Nhúng watermark
        stego_bytes, bits_len = embed_watermark_lsb(image_bytes, watermark_text)

        # Ghi vào blockchain mock
        author_info = {
            "name": author_name,
            "email": author_email,
            "link": author_link
        }
        
        tx_hash, record = bc.register_image(stego_bytes, watermark_text, author_info, bits_len)

        # Lưu file output với tên an toàn
        filename = secure_filename(file.filename)
        base, ext = os.path.splitext(filename)
        # Loại bỏ khoảng trắng và ký tự đặc biệt
        base = "".join(c for c in base if c.isalnum() or c in "._-")
        out_name = f"{base}_watermarked.png"
        out_path = os.path.join(app.config["UPLOAD_FOLDER"], out_name)

        with open(out_path, "wb") as f:
            f.write(stego_bytes)
        
        # Tạo URL download trực tiếp (không qua static)
        download_url = url_for('download_file', filename=out_name, _external=True)
        
        flash("✅ Nhúng watermark thành công!", "success")
        
        return render_template(
            "result_embed.html",
            download_url=download_url,
            tx_hash=tx_hash,
            record=record,
            filename=out_name
        )
    
    except Exception as e:
        app.logger.error(f"Embed error: {str(e)}")
        flash(f"Lỗi: {str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/verify", methods=["POST"])
def verify():
    try:
        if "image" not in request.files:
            flash("Vui lòng chọn ảnh cần xác minh", "error")
            return redirect(url_for("index"))

        file = request.files["image"]
        if file.filename == "":
            flash("Vui lòng chọn ảnh hợp lệ", "error")
            return redirect(url_for("index"))

        # Kiểm tra kích thước
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 10 * 1024 * 1024:
            flash("Ảnh quá lớn (tối đa 10MB)", "error")
            return redirect(url_for("index"))

        image_bytes = file.read()
        
        flash("Đang xác minh, vui lòng chờ...", "info")

        # Tra cứu blockchain mock
        image_hash, record = bc.verify_image(image_bytes)

        if record is None:
            return render_template(
                "result_verify.html",
                status="NOT_FOUND",
                image_hash=image_hash,
                message="Không tìm thấy bản ghi trên sổ cái. Ảnh có thể chưa được đăng ký hoặc đã bị chỉnh sửa."
            )

        # Trích xuất watermark
        bits_len = record.get("bits_length", 0)
        extracted_text = extract_watermark_lsb(image_bytes, bits_len)

        # So sánh hash
        extracted_hash = bc.sha256_bytes(extracted_text.encode("utf-8"))
        is_valid = (extracted_hash == record["watermark_hash"])
        status = "VALID" if is_valid else "TAMPERED"

        if is_valid:
            message = "✅ Ảnh hợp lệ, watermark trùng khớp với bản ghi trên sổ cái."
        else:
            message = "⚠️ Ảnh có watermark nhưng nội dung không trùng với bản ghi. Có thể đã bị sửa đổi."

        return render_template(
            "result_verify.html",
            status=status,
            image_hash=image_hash,
            record=record,
            extracted_text=extracted_text,
            message=message
        )
    
    except Exception as e:
        app.logger.error(f"Verify error: {str(e)}")
        flash(f"Lỗi: {str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/download/<filename>")
def download_file(filename):
    """Tải file đã watermark"""
    try:
        # Kiểm tra tên file hợp lệ
        if '..' in filename or '/' in filename or '\\' in filename:
            flash("Tên file không hợp lệ", "error")
            return redirect(url_for("index"))
        
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        
        if not os.path.exists(path):
            flash("File không tồn tại hoặc đã hết hạn", "error")
            return redirect(url_for("index"))
        
        # Trả file về để tải
        return send_file(
            path, 
            as_attachment=True, 
            download_name=filename,
            mimetype='image/png'
        )
    
    except Exception as e:
        flash(f"Lỗi khi tải file: {str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/health")
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "upload_folder": app.config["UPLOAD_FOLDER"],
        "files": os.listdir(app.config["UPLOAD_FOLDER"]) if os.path.exists(app.config["UPLOAD_FOLDER"]) else []
    })

@app.route("/test")
def test():
    """Test endpoint"""
    return jsonify({
        "status": "ok",
        "message": "App is working"
    })

# Dọn dẹp file cũ
def cleanup_old_files():
    """Xóa file cũ hơn 1 giờ"""
    while True:
        try:
            current_time = time.time()
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.isfile(file_path):
                    if current_time - os.path.getctime(file_path) > 3600:
                        os.remove(file_path)
                        print(f"Deleted old file: {filename}")
        except Exception as e:
            print(f"Cleanup error: {e}")
        time.sleep(3600)

# Khởi chạy thread dọn dẹp
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=10000)
