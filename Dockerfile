FROM python:3.11

WORKDIR /app
COPY . .

RUN apt update && apt install -y ffmpeg
RUN pip install -r requirements.txt

CMD ["python", "botmuzyczny.py"]
