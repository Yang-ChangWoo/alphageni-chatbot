"""검색 엔진: 질문 → 정규화 → FAQ 5,800개 표현 검색 → HIGH / MID / LOW 판정.

search/matcher.py와 같은 로직을 DB에서 읽어 오도록 옮긴 것입니다.
  최종점수 = 0.80 × 임베딩(ko-sroberta 코사인) + 0.20 × fuzzy(token_set_ratio/100)
  FAQ 점수 = 그 FAQ의 표현 10개(대표 1 + 유사 9) 중 최고점
  LOW  : 1위 점수 < 0.43, 또는 비속어를 빼면 남는 글자가 없음
  HIGH : 1위 점수 ≥ 0.75 그리고 (1위 − 2위) ≥ 0.05
  MID  : 나머지

벡터 DB는 쓰지 않습니다. 표현 5,800개 × 768차원 임베딩은 약 18MB라 서버 메모리에 한 번
올려 두고 numpy 행렬곱으로 전부 비교해도 질문 하나에 수 밀리초면 끝납니다.
"""
import hashlib
import json
import threading

import numpy as np
from django.conf import settings
from rapidfuzz import fuzz, process

from .normalize import Normalizer, keyword_form

_lock = threading.Lock()
_engine = None


class NotLoaded(Exception):
    pass


def cfg(key):
    return settings.CHATBOT[key]


def texts_hash(texts, model_name):
    return hashlib.md5(("\n".join(texts) + model_name).encode()).hexdigest()[:12]


def index_paths():
    d = cfg("INDEX_DIR")
    return d / "expr_embeddings.npy", d / "meta.json"


def load_model(model_name):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


class Engine:
    def __init__(self):
        from .models import FAQ, Abbreviation, Expression, Profanity

        self.norm = Normalizer([a.as_row() for a in Abbreviation.objects.all()],
                               [p.as_row() for p in Profanity.objects.all()])

        self.faqs = {f.faq_id: f for f in FAQ.objects.all()}
        exprs = list(Expression.objects.select_related("faq").order_by("id").values_list("faq__faq_id", "text"))
        if not self.faqs or not exprs:
            raise NotLoaded("FAQ 데이터가 없습니다. python manage.py load_faq 를 먼저 실행하세요.")
        self.expr_faq = [f for f, _ in exprs]
        self.expr_text = [t for _, t in exprs]
        self.faq_ids = list(dict.fromkeys(self.expr_faq))
        idx = {f: j for j, f in enumerate(self.faq_ids)}
        self.groups = [[] for _ in self.faq_ids]
        for i, f in enumerate(self.expr_faq):
            self.groups[idx[f]].append(i)
        self.categories = sorted({f.category for f in self.faqs.values()})

        # 색인 쪽도 질문과 같은 정규화 적용
        self.expr_norm = [self.norm(t).text for t in self.expr_text]
        self.expr_kw = [keyword_form(t) for t in self.expr_norm]

        self.w = cfg("W_EMBEDDING")
        self.model, self.E, self.mode_note = None, None, ""
        if cfg("USE_MODEL"):
            try:
                self.model = load_model(cfg("MODEL_NAME"))
                self.E = self._embeddings()
            except Exception as e:
                self.model, self.E = None, None
                self.mode_note = f"임베딩 모델을 불러오지 못해 fuzzy만 사용 중 ({type(e).__name__})"
                print(f"[챗봇] {self.mode_note}: {e}")
        else:
            self.mode_note = "CHATBOT_USE_MODEL=0: fuzzy만 사용 중 (동작 확인용)"

    @property
    def mode(self):
        return "embedding+fuzzy" if self.model is not None else "fuzzy-only"

    def _embeddings(self):
        """build_index가 만든 .npy가 현재 데이터와 맞으면 그대로, 아니면 새로 만들어 저장."""
        name = cfg("MODEL_NAME")
        npy, meta = index_paths()
        h = texts_hash(self.expr_norm, name)
        if npy.exists() and meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
            if m.get("hash") == h:
                return np.load(npy)
            print("[챗봇] 데이터가 바뀌어 임베딩을 다시 만듭니다.")
        return build_embeddings(self.model, self.expr_norm, name)

    # ------------------------------------------------------------ scoring
    def _expr_scores(self, variants):
        F = process.cdist([keyword_form(v) for v in variants], self.expr_kw,
                          scorer=fuzz.token_set_ratio, workers=-1).max(axis=0) / 100.0
        if self.model is not None:
            Q = self.model.encode(variants, normalize_embeddings=True)
            S = np.clip(Q @ self.E.T, 0, 1).max(axis=0)
        else:
            S = F
        return self.w * S + (1 - self.w) * F, F, S

    def match(self, query: str, top_k: int = None) -> dict:
        top_k = top_k or cfg("TOP_K")
        t_high, t_low, margin = cfg("T_HIGH"), cfg("T_LOW"), cfg("MARGIN")
        n = self.norm(query)
        base = {
            "query": query, "normalized": n.text, "profanity_removed": n.profanity, "masked": n.masked,
            "abbr_expanded": n.expanded, "abbr_ambiguous": n.ambiguous, "mode": self.mode,
        }
        if n.empty:
            return {**base, "grade": "LOW", "reason": "비속어·기호를 빼면 남는 내용이 없음",
                    "top1_score": 0.0, "gap": 0.0, "candidates": [], "categories": self.categories}

        C, F, S = self._expr_scores(n.variants)
        best_e = [g[int(np.argmax(C[g]))] for g in self.groups]
        faq_score = C[best_e]
        order = np.argsort(-faq_score)
        top1, top2 = float(faq_score[order[0]]), float(faq_score[order[1]])
        gap = top1 - top2

        if top1 < t_low:
            grade, reason = "LOW", f"1위 점수 {top1:.3f} < {t_low}"
        elif top1 >= t_high and gap >= margin:
            grade, reason = "HIGH", f"1위 점수 {top1:.3f} ≥ {t_high}, 1·2위 차 {gap:.3f} ≥ {margin}"
        elif top1 < t_high:
            grade, reason = "MID", f"1위 점수 {top1:.3f} < {t_high}"
        else:
            grade, reason = "MID", f"1·2위 차 {gap:.3f} < {margin} (비슷한 FAQ가 여러 개)"

        cands = []
        for j in order[:top_k]:
            e = best_e[j]
            cands.append({**faq_dict(self.faqs[self.faq_ids[j]]), "matched_text": self.expr_text[e],
                          "score": round(float(C[e]), 4), "fuzzy": round(float(F[e]), 4),
                          "semantic": round(float(S[e]), 4)})
        return {**base, "grade": grade, "reason": reason, "top1_score": round(top1, 4), "gap": round(gap, 4),
                "candidates": cands, "categories": self.categories if grade == "LOW" else []}


def faq_dict(f):
    return {"faq_id": f.faq_id, "category": f.category, "job_group": f.job_group,
            "rep_question": f.rep_question, "answer": f.answer,
            "source": f.discovery_source, "evidence": f.evidence_source}


def build_embeddings(model, texts, model_name):
    npy, meta = index_paths()
    npy.parent.mkdir(parents=True, exist_ok=True)
    E = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=True)
    E = np.asarray(E, dtype=np.float32)
    np.save(npy, E)
    meta.write_text(json.dumps({"model": model_name, "count": len(texts), "dim": int(E.shape[1]),
                                "hash": texts_hash(texts, model_name)}, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    return E


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = Engine()
    return _engine


def reset_engine():
    global _engine
    with _lock:
        _engine = None
