FROM python:3.11

WORKDIR /app
COPY . .

# 🔥 KLUCZOWE (bez tego nie działa YT)
RUN apt update && apt install -y ffmpeg nodejs npm

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "botmuzyczny.py"]
