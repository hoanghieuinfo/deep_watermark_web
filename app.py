


import os
from flask import Flask, render_template, request, send_file, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from io import BytesIO


from watermark import embed_watermark_lsb, extract_watermark_lsb
import blockchain_mock as bc


UPLOAD_FOLDER = "/tmp/uploads"  # Quan trọng: phải dùng /tmp trên Render
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "super-secret-key"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/embed", methods=["POST"])
def embed():
    try:
        if "image" not in request.files:
            flash("Vui lòng chọn ảnh")
            return redirect(url_for("index"))

        file = request.files["image"]
        if file.filename == "":
            flash("Vui lòng chọn ảnh hợp lệ")
            return redirect(url_for("index"))

        watermark_text = request.form.get("watermark_text", "")
        author_name = request.form.get("author_name", "")
        author_email = request.form.get("author_email", "")
        author_link = request.form.get("author_link", "")

        if not watermark_text:
            flash("Vui lòng nhập nội dung watermark (text)")
            return redirect(url_for("index"))

        image_bytes = file.read()

        # nhúng watermark
        stego_bytes, bits_len = embed_watermark_lsb(image_bytes, watermark_text)

        # ghi "blockchain"
        author_info = {
            "name": author_name,
            "email": author_email,
            "link": author_link
        }
        tx_hash, record = bc.register_image(stego_bytes, watermark_text, author_info, bits_len)

        # lưu file output
        filename = secure_filename(file.filename)
        base, ext = os.path.splitext(filename)
        out_name = f"{base}_watermarked.png"
        out_path = os.path.join(app.config["UPLOAD_FOLDER"], out_name)

        with open(out_path, "wb") as f:
            f.write(stego_bytes)

        # Tạo URL để tải file
        download_url = url_for('download_file', filename=out_name, _external=True)

        return render_template(
            "result_embed.html",
            image_url=download_url,
            download_url=download_url,
            tx_hash=tx_hash,
            record=record,
            filename=out_name
        )
    
    except Exception as e:
        flash(f"Lỗi khi nhúng watermark: {str(e)}")
        return redirect(url_for("index"))

@app.route("/download/<path:filename>")
def download_file(filename):
    try:
        # Đảm bảo đường dẫn an toàn
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

        image_bytes = file.read()

        # tra cứu "blockchain" theo hash ảnh
        image_hash, record = bc.verify_image(image_bytes)

        if record is None:
            # không tìm thấy
            return render_template(
                "result_verify.html",
                status="NOT_FOUND",
                image_hash=image_hash,
                message="Không tìm thấy bản ghi trên sổ cái (blockchain mock). Ảnh có thể chưa được đăng ký hoặc đã bị chỉnh sửa nhiều."
            )

        # nếu tìm thấy: trích watermark và so sánh hash
        bits_len = record.get("bits_length", 0)
        extracted_text = extract_watermark_lsb(image_bytes, bits_len)
        extracted_hash = bc.sha256_bytes(extracted_text.encode("utf-8"))

        is_valid = (extracted_hash == record["watermark_hash"])
        status = "VALID" if is_valid else "TAMPERED"

        if is_valid:
            message = "Ảnh hợp lệ, watermark trùng khớp với bản ghi trên sổ cái."
        else:
            message = "Ảnh có watermark nhưng nội dung không trùng với bản ghi. Có thể đã bị sửa đổi."

        return render_template(
            "result_verify.html",
            status=status,
            image_hash=image_hash,
            record=record,
            extracted_text=extracted_text,
            message=message
        )
    
    except Exception as e:
        flash(f"Lỗi khi xác minh: {str(e)}")
        return redirect(url_for("index"))

@app.route("/health")
def health():
    """Health check endpoint cho Render"""
    return jsonify({"status": "healthy", "message": "App is running"})

# Dọn dẹp file cũ tự động
import threading
import time

def cleanup_old_files():
    """Xóa file cũ hơn 1 giờ"""
    while True:
        try:
            current_time = time.time()
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.isfile(file_path):
                    # Xóa file cũ hơn 1 giờ
                    if current_time - os.path.getctime(file_path) > 3600:
                        os.remove(file_path)
                        print(f"Deleted old file: {filename}")
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        # Chạy mỗi 1 giờ
        time.sleep(3600)

# Khởi chạy thread dọn dẹp
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=10000)
