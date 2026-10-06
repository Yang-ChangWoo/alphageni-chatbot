import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chatbot.models import FAQ, Expression

FAQ_FIELDS = ["category", "job_group", "rep_question", "answer", "discovery_route", "discovery_source",
              "evidence_source", "evidence_summary", "priority", "checked_date", "review_status", "note"]


def read_csv(path):
    path = Path(path)
    if not path.exists():
        raise CommandError(f"파일이 없습니다: {path}")
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


class Command(BaseCommand):
    help = "FAQ CSV와 표현(대표+유사 질문) CSV를 DB에 적재합니다. 기존 FAQ·표현은 지우고 새로 넣습니다."

    def add_arguments(self, parser):
        d = settings.CHATBOT["DATA_DIR"]
        parser.add_argument("--faq", default=str(d / "faq_580_with_similar.csv"))
        parser.add_argument("--expressions", default=str(d / "expressions_580.csv"))

    @transaction.atomic
    def handle(self, *args, **o):
        faq_rows = read_csv(o["faq"])
        expr_rows = read_csv(o["expressions"])

        Expression.objects.all().delete()
        FAQ.objects.all().delete()

        faqs = FAQ.objects.bulk_create([
            FAQ(faq_id=r["faq_id"], row_no=int(r.get("row_no") or i + 1), **{k: r.get(k, "") for k in FAQ_FIELDS})
            for i, r in enumerate(faq_rows)
        ])
        by_id = {f.faq_id: f for f in FAQ.objects.all()}

        missing = sorted({r["faq_id"] for r in expr_rows} - by_id.keys())
        if missing:
            raise CommandError(f"표현 CSV에 FAQ CSV에 없는 faq_id가 있습니다: {missing[:10]}")

        Expression.objects.bulk_create([
            Expression(expr_id=r["expr_id"], faq=by_id[r["faq_id"]], text=r["text"].strip(),
                       is_representative=r.get("is_representative") == "Y",
                       variation_type=r.get("variation_type", ""), variation_label=r.get("variation_label", ""))
            for r in expr_rows if r["text"].strip()
        ], batch_size=1000)

        no_expr = FAQ.objects.filter(expressions__isnull=True).count()
        self.stdout.write(self.style.SUCCESS(
            f"FAQ {len(faqs)}개, 표현 {Expression.objects.count()}개 적재 완료"
            + (f" (표현이 없는 FAQ {no_expr}개)" if no_expr else "")))
        self.stdout.write("데이터가 바뀌었으니 python manage.py build_index 로 임베딩을 다시 만드세요.")
