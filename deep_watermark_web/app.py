# -*- coding: utf-8 -*-

# app.py
import os
from flask import Flask, render_template, request, send_file, redirect, url_for, flash
from werkzeug.utils import secure_filename
from io import BytesIO

from watermark import embed_watermark_lsb, extract_watermark_lsb
import blockchain_mock as bc

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "super-secret-key"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/embed", methods=["POST"])
def embed():
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

    # đường dẫn để hiển thị trong HTML
    out_url = url_for("static", filename=f"uploads/{out_name}")

    return render_template(
        "result_embed.html",
        image_url=out_url,
        tx_hash=tx_hash,
        record=record
    )


@app.route("/download/<path:filename>")
def download_file(filename):
    # tải file trong static/uploads
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    return send_file(path, as_attachment=True)


@app.route("/verify", methods=["POST"])
def verify():
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


if __name__ == "__main__":
    app.run(debug=True)
