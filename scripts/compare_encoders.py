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
VAR_DIR = ROOT / "onnx_model/variants"
names = sorted(p.name for p in VAR_DIR.iterdir()) if VAR_DIR.exists() else ["onnx"]
res = {}
for enc in ["st"] + names:
    settings.CHATBOT["ENCODER"] = "st" if enc == "st" else "onnx"
    if enc != "st" and VAR_DIR.exists():
        settings.CHATBOT["ONNX_DIR"] = VAR_DIR / enc
        settings.CHATBOT["INDEX_DIR"] = ROOT / "index" / enc
    eng.reset_engine()
    e = eng.get_engine()
    print(enc, e.mode, e.mode_note, flush=True)
    res[enc] = [e.match(r["query"]) for r in rows]


def ok(r, m):
    top = m["candidates"][0]["faq_id"] if m["candidates"] else ""
    return m["grade"] == r["expected_grade"] and (m["grade"] != "HIGH" or top == r["gold_faq_id"])


def score(k):
    t = [i for i, r in enumerate(rows) if r["split"] == "test"]
    return sum(ok(r, m) for r, m in zip(rows, res[k])), sum(ok(rows[i], res[k][i]) for i in t)


lines = ["| 방식 | 전체 200 | val 140 | test 60 | 틀린 HIGH | st와 등급·1위 동일 |", "|---|---|---|---|---|---|"]
for k in ["st"] + names:
    v = [i for i, r in enumerate(rows) if r["split"] == "val"]
    t = [i for i, r in enumerate(rows) if r["split"] == "test"]
    a = sum(ok(r, m) for r, m in zip(rows, res[k]))
    va = sum(ok(rows[i], res[k][i]) for i in v)
    ta = sum(ok(rows[i], res[k][i]) for i in t)
    wh = sum(m["grade"] == "HIGH" and m["candidates"][0]["faq_id"] != r["gold_faq_id"] for r, m in zip(rows, res[k]))
    same = sum(x["grade"] == y["grade"] and x["candidates"][0]["faq_id"] == y["candidates"][0]["faq_id"]
               for x, y in zip(res["st"], res[k]))
    lines.append(f"| {k} | {a} ({a / 200:.1%}) | {va} | {ta} | {wh} | {same} |")
best = max(names, key=lambda k: (score(k)[0], sum(x["grade"] == y["grade"] for x, y in zip(res["st"], res[k]))))
lines.append(f"\n선택: **{best}**")
diff = [(r["query"], a["grade"], b["grade"], f"{a['top1_score']:.3f}", f"{b['top1_score']:.3f}")
        for r, a, b in zip(rows, res["st"], res[best]) if a["grade"] != b["grade"]]
if diff:
    lines.append(f"\n| 등급이 달라진 질문 ({best}) | st | onnx | st 점수 | onnx 점수 |\n|---|---|---|---|---|")
    lines += [f"| {q} | {x} | {y} | {s} | {t} |" for q, x, y, s, t in diff]
report = "\n".join(lines)
print(report)
if VAR_DIR.exists():
    import shutil
    for f in ("model.onnx", "tokenizer.json"):
        shutil.copy(VAR_DIR / best / f, ROOT / "onnx_model" / f)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
        f.write("## ONNX 8비트 양자화 방식 비교 (200문항)\n\n" + report + "\n")
