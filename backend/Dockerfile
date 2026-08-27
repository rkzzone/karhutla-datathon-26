# Backend konsol operator karhutla.
#
# Sengaja portabel — image ini jalan apa adanya di Render, Fly.io, Railway,
# maupun Hugging Face Spaces. Tidak ada yang spesifik ke satu penyedia selain
# membaca $PORT, yang memang konvensi bersama.
#
# Runtime TIDAK butuh torch. Inference dijalankan batch offline oleh
# scripts/jalankan_inference.py di mesin pengembang, hasilnya di-commit.
# Karena itu image tetap ~150 MB, bukan ~2 GB.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# requirements disalin lebih dulu supaya layer pip ter-cache selama daftar
# dependensinya tidak berubah.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Jalan sebagai non-root. Beberapa penyedia (mis. HF Spaces) mensyaratkannya,
# dan tidak ada alasan untuk root di sini.
RUN useradd --create-home --uid 1000 apl && chown -R apl:apl /app
USER apl

EXPOSE 8000

# $PORT diisi penyedia; 8000 untuk `docker run` lokal.
# Satu worker: cache FIRMS dan catatan keputusan operator disimpan di memori
# proses, jadi menambah worker akan membuat keduanya tidak konsisten antar
# permintaan. Beban kerjanya ringan — satu worker lebih dari cukup.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
