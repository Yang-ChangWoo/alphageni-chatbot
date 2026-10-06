# Hugging Face Spaces(Docker)용. 이미지를 만들 때 DB 적재와 임베딩까지 끝내 둡니다.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache \
    DJANGO_DEBUG=0 \
    PORT=7860

WORKDIR /app

# CPU용 torch를 먼저 설치 (GPU용보다 훨씬 작음)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN python manage.py migrate \
 && python manage.py load_faq \
 && python manage.py load_dicts \
 && python manage.py build_index \
 && python manage.py collectstatic --noinput \
 && chmod -R 777 /app

EXPOSE 7860
CMD CHATBOT_WARM=1 gunicorn config.wsgi --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 180
