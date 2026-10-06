from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from chatbot.models import Abbreviation, Profanity

from .load_faq import read_csv


class Command(BaseCommand):
    help = "줄임말 사전과 비속어 사전 CSV를 DB에 적재합니다. 기존 사전은 지우고 새로 넣습니다."

    def add_arguments(self, parser):
        d = settings.CHATBOT["DATA_DIR"]
        parser.add_argument("--abbr", default=str(d / "abbreviations.csv"))
        parser.add_argument("--profanity", default=str(d / "profanity.csv"))

    @transaction.atomic
    def handle(self, *args, **o):
        abbr_rows = read_csv(o["abbr"])
        prof_rows = read_csv(o["profanity"])

        Abbreviation.objects.all().delete()
        seen = {}
        for r in abbr_rows:  # 같은 줄임말이 두 번 있으면 뒤의 행으로 덮어씀
            seen[r["abbr"].strip()] = r
        Abbreviation.objects.bulk_create([
            Abbreviation(abbr=a, expansion=r["expansion"].strip(), category=r.get("category", ""),
                         ambiguous=r.get("ambiguous", "N") == "Y", alt_expansions=r.get("alt_expansions", ""),
                         match=r.get("match") or "prefix", note=r.get("note", ""))
            for a, r in seen.items() if a
        ])

        Profanity.objects.all().delete()
        Profanity.objects.bulk_create([
            Profanity(word=r["word"], pattern=r["pattern"], type=r.get("type", ""),
                      severity=int(r.get("severity") or 1), action=r.get("action") or "remove", note=r.get("note", ""))
            for r in prof_rows if r["pattern"].strip()
        ])
        dup = len(abbr_rows) - len(seen)
        self.stdout.write(self.style.SUCCESS(
            f"줄임말 {Abbreviation.objects.count()}개" + (f" (중복 {dup}개 합침)" if dup else "")
            + f", 비속어 {Profanity.objects.count()}개 적재 완료"))
        self.stdout.write("사전이 바뀌면 색인 정규화도 바뀌니 python manage.py build_index 를 다시 실행하세요.")
