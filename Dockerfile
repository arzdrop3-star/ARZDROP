FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir fastapi uvicorn python-multipart

# Копируем файлы проекта (только то, что есть)
COPY server.py .
COPY web.html .

# Если папка skins существует — копируем, иначе игнорируем
COPY skins/ ./skins/ 2>/dev/null || true

# Создаём пустую папку, если её нет
RUN mkdir -p skins

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
