FROM python:3.11

WORKDIR /app

# instalacja ffmpeg i libs
RUN apt update && apt install -y ffmpeg libopus-dev

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "botmuzyczny.py"]
