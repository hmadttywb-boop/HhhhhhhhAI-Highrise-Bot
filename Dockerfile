FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/bot.py .

CMD ["python", "-u", "bot.py"]
