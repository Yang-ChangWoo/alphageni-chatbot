"""알파지니 취업챗봇 Django 설정."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me-alphageni-chatbot")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["*"]
# 배포 주소(Netlify 프록시 등)에서 관리자 로그인 폼을 쓸 때 필요. 쉼표로 여러 개: https://a.netlify.app,https://b.hf.space
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "chatbot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # DEBUG=0일 때 정적 파일 제공
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # XFrameOptionsMiddleware는 뺌: Hugging Face Spaces 페이지가 앱을 iframe으로 보여 주기 때문
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---- 챗봇 검색 설정 (질문 200개 Grid Search 결과, test 정확도 96.7%)
CHATBOT = {
    "MODEL_NAME": "jhgan/ko-sroberta-multitask",
    # 0으로 두면 임베딩 모델 없이 fuzzy만 씀 (동작 확인용, 기준값이 맞지 않음)
    "USE_MODEL": os.environ.get("CHATBOT_USE_MODEL", "1") == "1",
    "W_EMBEDDING": 0.80,   # 최종점수 = 0.80 × 임베딩 + 0.20 × fuzzy
    "T_HIGH": 0.75,        # HIGH: 1위 ≥ 0.75 그리고 1·2위 차 ≥ 0.05
    "MARGIN": 0.05,
    "T_LOW": 0.43,         # LOW: 1위 < 0.43
    "TOP_K": 3,
    "INDEX_DIR": BASE_DIR / "index",   # build_index가 만든 임베딩(.npy) 저장 위치
    "DATA_DIR": BASE_DIR / "data",     # load_faq / load_dicts 기본 CSV 위치
}
