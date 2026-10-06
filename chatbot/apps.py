import os
import threading

from django.apps import AppConfig


class ChatbotConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chatbot"
    verbose_name = "알파지니 취업챗봇"

    def ready(self):
        # 서버로 띄울 때만(runserver, 또는 CHATBOT_WARM=1인 gunicorn) 검색 엔진을 미리 올려 첫 질문이 느리지 않게 함
        if os.environ.get("RUN_MAIN") == "true" or os.environ.get("CHATBOT_WARM") == "1":
            from .engine import get_engine

            threading.Thread(target=self._warm, args=(get_engine,), daemon=True).start()

    @staticmethod
    def _warm(get_engine):
        try:
            get_engine()
        except Exception as e:  # 데이터 미적재 등은 첫 요청 때 화면에 안내
            print(f"[챗봇] 검색 엔진 준비 실패: {e}")
