FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости прямо в Dockerfile
RUN pip install --no-cache-dir fastapi uvicorn python-multipart

# Копируем файлы проекта
COPY server.py .
COPY web.html .
COPY skins/ ./skins/

# Открываем порт
EXPOSE 8000

# Запускаем сервер
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
