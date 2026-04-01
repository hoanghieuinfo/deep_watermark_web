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

UPLOAD_FOLDER = "/tmp/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "super-secret-key"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # Giảm xuống 10MB để tránh treo
app.config['TIMEOUT'] = 30  # Timeout 30 giây

# Decorator để giới hạn thời gian xử lý
def timeout_handler(timeout_seconds):
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = [None]
            error = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    error[0] = e
            
            thread = threading.Thread(target=target)
            thread.start()
            thread.join(timeout_seconds)
            
            if thread.is_alive():
                raise TimeoutError(f"Operation timed out after {timeout_seconds} seconds")
            
            if error[0]:
                raise error[0]
            
            return result[0]
        
        return wrapper
    return decorator

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/embed", methods=["POST"])
def embed():
    try:
        # Kiểm tra file
        if "image" not in request.files:
            flash("Vui lòng chọn ảnh")
            return redirect(url_for("index"))

        file = request.files["image"]
        if file.filename == "":
            flash("Vui lòng chọn ảnh hợp lệ")
            return redirect(url_for("index"))

        # Kiểm tra kích thước file
        file.seek(0, 2)  # Đến cuối file
        file_size = file.tell()
        file.seek(0)  # Quay lại đầu
        
        if file_size > 10 * 1024 * 1024:  # 10MB
            flash("Ảnh quá lớn (tối đa 10MB). Vui lòng chọn ảnh nhỏ hơn.")
            return redirect(url_for("index"))
        
        watermark_text = request.form.get("watermark_text", "")
        author_name = request.form.get("author_name", "")
        author_email = request.form.get("author_email", "")
        author_link = request.form.get("author_link", "")

        if not watermark_text:
            flash("Vui lòng nhập nội dung watermark (text)")
            return redirect(url_for("index"))
        
        # Giới hạn độ dài watermark
        if len(watermark_text) > 500:
            watermark_text = watermark_text[:500]
            flash("Watermark quá dài, đã cắt xuống 500 ký tự")

        # Đọc file ảnh
        image_bytes = file.read()
        
        # Thông báo đang xử lý
        flash("Đang xử lý ảnh, vui lòng chờ...", "info")
        
        # Nhúng watermark (có timeout)
        try:
            stego_bytes, bits_len = embed_watermark_lsb(image_bytes, watermark_text)
        except TimeoutError:
            flash("Xử lý quá lâu. Vui lòng thử với ảnh nhỏ hơn hoặc watermark ngắn hơn.", "error")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Lỗi khi nhúng watermark: {str(e)}", "error")
            return redirect(url_for("index"))

        # Ghi vào blockchain mock
        author_info = {
            "name": author_name,
            "email": author_email,
            "link": author_link
        }
        
        try:
            tx_hash, record = bc.register_image(stego_bytes, watermark_text, author_info, bits_len)
        except Exception as e:
            flash(f"Lỗi khi ghi blockchain: {str(e)}", "error")
            return redirect(url_for("index"))

        # Lưu file output
        filename = secure_filename(file.filename)
        base, ext = os.path.splitext(filename)
        out_name = f"{base}_watermarked.png"
        out_path = os.path.join(app.config["UPLOAD_FOLDER"], out_name)

        with open(out_path, "wb") as f:
            f.write(stego_bytes)

        download_url = url_for('download_file', filename=out_name, _external=True)

        flash("✅ Nhúng watermark thành công!", "success")
        
        return render_template(
            "result_embed.html",
            image_url=download_url,
            download_url=download_url,
            tx_hash=tx_hash,
            record=record,
            filename=out_name
        )
    
    except Exception as e:
        app.logger.error(f"Embed error: {str(e)}")
        flash(f"Lỗi hệ thống: {str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/verify", methods=["POST"])
def verify():
    try:
        if "image" not in request.files:
            flash("Vui lòng chọn ảnh cần xác minh")
            return redirect(url_for("index"))

        file = request.files["image"]
        if file.filename == "":
            flash("Vui lòng chọn ảnh hợp lệ")
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
        try:
            image_hash, record = bc.verify_image(image_bytes)
        except Exception as e:
            flash(f"Lỗi khi tra cứu blockchain: {str(e)}", "error")
            return redirect(url_for("index"))

        if record is None:
            return render_template(
                "result_verify.html",
                status="NOT_FOUND",
                image_hash=image_hash,
                message="Không tìm thấy bản ghi trên sổ cái. Ảnh có thể chưa được đăng ký hoặc đã bị chỉnh sửa."
            )

        # Trích xuất watermark
        bits_len = record.get("bits_length", 0)
        
        try:
            extracted_text = extract_watermark_lsb(image_bytes, bits_len)
        except TimeoutError:
            flash("Xử lý quá lâu. Vui lòng thử lại.", "error")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Lỗi trích xuất watermark: {str(e)}", "error")
            return redirect(url_for("index"))

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
        flash(f"Lỗi hệ thống: {str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/download/<path:filename>")
def download_file(filename):
    try:
        if '..' in filename or '/' in filename:
            flash("Tên file không hợp lệ")
            return redirect(url_for("index"))
        
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        
        if not os.path.exists(path):
            flash("File không tồn tại hoặc đã hết hạn")
            return redirect(url_for("index"))
        
        return send_file(path, as_attachment=True, download_name=filename)
    
    except Exception as e:
        flash(f"Lỗi khi tải file: {str(e)}")
        return redirect(url_for("index"))

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "message": "App is running",
        "upload_folder": app.config["UPLOAD_FOLDER"]
    })

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=10000)
