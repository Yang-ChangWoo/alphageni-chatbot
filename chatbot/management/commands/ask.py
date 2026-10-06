import csv
import json
from collections import Counter

from django.core.management.base import BaseCommand

from chatbot.engine import get_engine


class Command(BaseCommand):
    help = "터미널에서 질문하기. 질문 하나, 또는 query 열이 있는 CSV를 한꺼번에 돌려 결과 CSV를 만듭니다."

    def add_arguments(self, parser):
        parser.add_argument("query", nargs="?")
        parser.add_argument("--csv", help="query 열이 있는 CSV (예: 미등록 시험 질문 60개)")
        parser.add_argument("--out", default="ask_result.csv")
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **o):
        e = get_engine()
        self.stdout.write(f"[검색 방식: {e.mode}] {e.mode_note}")
        if o["csv"]:
            with open(o["csv"], encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            out = []
            for r in rows:
                res = e.match(r["query"])
                c = res["candidates"][0] if res["candidates"] else {}
                out.append({**r, "grade": res["grade"], "normalized": res["normalized"],
                            "top1_faq": c.get("faq_id", ""), "top1_question": c.get("rep_question", ""),
                            "top1_score": res["top1_score"], "gap": res["gap"], "reason": res["reason"]})
            with open(o["out"], "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(out[0]))
                w.writeheader()
                w.writerows(out)
            self.stdout.write(f"등급 분포: {dict(Counter(x['grade'] for x in out))} → {o['out']}")
        elif o["query"]:
            res = e.match(o["query"])
            if o["json"]:
                self.stdout.write(json.dumps(res, ensure_ascii=False, indent=2))
                return
            self.stdout.write(f"[{res['grade']}] {res['reason']}\n정규화: {res['normalized']}")
            for k, c in enumerate(res["candidates"], 1):
                self.stdout.write(f"  {k}. {c['faq_id']} {c['rep_question']} ({c['score']:.3f})")
