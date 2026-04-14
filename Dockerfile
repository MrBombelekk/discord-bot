FROM python:3.11

WORKDIR /app
COPY . .

# 🔥 instalacja ffmpeg + node (WAŻNE)
RUN apt update && apt install -y ffmpeg nodejs npm

# 🔥 install python deps
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "botmuzyczny.py"]
