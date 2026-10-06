"""같은 200문항을 sentence-transformers(원래)와 ONNX 8비트로 돌려 등급·정확도를 비교합니다.
  python scripts/compare_encoders.py   (DB 적재와 onnx_model/ 이 있어야 함)
"""
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402

from chatbot import engine as eng  # noqa: E402

rows = list(csv.DictReader(open(ROOT / "tests/test_questions_200.csv", encoding="utf-8-sig")))
res = {}
for enc in ("st", "onnx"):
    settings.CHATBOT["ENCODER"] = enc
    eng.reset_engine()
    e = eng.get_engine()
    print(enc, e.mode, e.mode_note)
    res[enc] = [e.match(r["query"]) for r in rows]


def ok(r, m):
    top = m["candidates"][0]["faq_id"] if m["candidates"] else ""
    return m["grade"] == r["expected_grade"] and (m["grade"] != "HIGH" or top == r["gold_faq_id"])


lines = ["| 구분 | 원래(st) | ONNX 8비트 |", "|---|---|---|"]
for split in ("val", "test", None):
    idx = [i for i, r in enumerate(rows) if split is None or r["split"] == split]
    a = sum(ok(rows[i], res["st"][i]) for i in idx)
    b = sum(ok(rows[i], res["onnx"][i]) for i in idx)
    lines.append(f"| {split or '전체'} ({len(idx)}) | {a} ({a / len(idx):.1%}) | {b} ({b / len(idx):.1%}) |")
wh = lambda k: sum(m["grade"] == "HIGH" and m["candidates"][0]["faq_id"] != r["gold_faq_id"] for r, m in zip(rows, res[k]))
lines.append(f"| 틀린 HIGH | {wh('st')} | {wh('onnx')} |")
same = sum(a["grade"] == b["grade"] and a["candidates"][0]["faq_id"] == b["candidates"][0]["faq_id"]
           for a, b in zip(res["st"], res["onnx"]))
lines.append(f"\n등급과 1위 FAQ가 둘 다 같은 질문: {same}/{len(rows)}")
diff = [(r["query"], a["grade"], b["grade"], f"{a['top1_score']:.3f}", f"{b['top1_score']:.3f}")
        for r, a, b in zip(rows, res["st"], res["onnx"]) if a["grade"] != b["grade"]]
if diff:
    lines.append("\n| 등급이 달라진 질문 | st | onnx | st 점수 | onnx 점수 |\n|---|---|---|---|---|")
    lines += [f"| {q} | {x} | {y} | {s} | {t} |" for q, x, y, s, t in diff]
report = "\n".join(lines)
print(report)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write("## ONNX 8비트 vs 원래 모델 (200문항)\n\n" + report + "\n")
