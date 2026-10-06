# Render(무료 512MB) / Hugging Face Spaces 공용.
# 원래 모델 대신 ONNX 8비트 모델(GitHub Release model-v1)을 받아 쓰고, 이미지를 만들 때 DB 적재와 임베딩까지 끝내 둡니다.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_DEBUG=0 \
    CHATBOT_ENCODER=onnx \
    PORT=7860 \
    MODEL_URL=https://github.com/Yang-ChangWoo/alphageni-chatbot/releases/download/model-v1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN mkdir -p onnx_model \
 && python -c "import os,urllib.request as u;[u.urlretrieve(os.environ['MODEL_URL']+'/'+f,'onnx_model/'+f) for f in ('model.onnx','tokenizer.json')]" \
 && python manage.py migrate \
 && python manage.py load_faq \
 && python manage.py load_dicts \
 && python manage.py build_index \
 && python manage.py collectstatic --noinput \
 && chmod -R 777 /app

EXPOSE 7860
CMD CHATBOT_WARM=1 gunicorn config.wsgi --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 180
