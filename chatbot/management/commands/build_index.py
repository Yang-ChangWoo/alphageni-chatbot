import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from chatbot import engine as eng
from chatbot.models import Abbreviation, Expression, Profanity
from chatbot.normalize import Normalizer


class Command(BaseCommand):
    help = "표현 5,800개를 ko-sroberta로 임베딩해 index/expr_embeddings.npy에 저장합니다 (벡터 DB 대신 파일)."

    def handle(self, *args, **o):
        texts = list(Expression.objects.order_by("id").values_list("text", flat=True))
        if not texts:
            raise CommandError("표현이 없습니다. python manage.py load_faq 를 먼저 실행하세요.")
        norm = Normalizer([a.as_row() for a in Abbreviation.objects.all()],
                          [p.as_row() for p in Profanity.objects.all()])
        texts = [norm(t).text for t in texts]

        name = settings.CHATBOT["MODEL_NAME"]
        self.stdout.write(f"모델 불러오는 중: {name} (처음 한 번은 내려받느라 시간이 걸립니다)")
        try:
            model = eng.load_model(name)
        except ImportError:
            raise CommandError("sentence-transformers가 없습니다. pip install -r requirements.txt")
        t = time.time()
        E = eng.build_embeddings(model, texts, name)
        npy, _ = eng.index_paths()
        self.stdout.write(self.style.SUCCESS(
            f"임베딩 {E.shape[0]}개 × {E.shape[1]}차원 저장 ({time.time() - t:.0f}초, {E.nbytes / 1e6:.1f}MB) → {npy}"))
