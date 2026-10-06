"""입력 정규화: 비속어 제거 → 반복 기호 정리 → 줄임말 확장.

질문과 색인(표현 4,790개) 양쪽에 같은 함수를 적용해야 점수가 맞습니다.
Django와 무관한 순수 Python 모듈입니다.
"""
import csv
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

DICT_DIR = Path(__file__).resolve().parent.parent / "dict"

# 줄임말 뒤에 붙어도 되는 조사·어미 (match=word 일 때)
_PARTICLES = (
    "은|는|이|가|을|를|에|에서|에게|한테|랑|이랑|과|와|도|만|으로|로|의|이나|나|부터|까지|"
    "임|이야|야|예요|이에요|에요|여|냐|지|죠|해|하|함|했|할|됨|돼|된|인데|인가|이라|라|요"
)
_WORD_END = rf"(?=(?:{_PARTICLES})?(?![0-9A-Za-z가-힣ㄱ-ㅎ]))"
_WORD_START = r"(?<![0-9A-Za-z가-힣ㄱ-ㅎ])"
_NOISE = re.compile(r"[ㅋㅎㅠㅜ]{2,}|[ㅋㅎ]+(?=\s|$)|[!?~.]{2,}|\^\^|;;+")


@dataclass
class Normalized:
    original: str
    text: str                      # 검색에 쓰는 문장 (다의어는 원문 유지)
    variants: list                 # 다의어 확장형까지 포함한 검색 후보 문장들 (text 포함)
    profanity: list = field(default_factory=list)   # 지운 비속어
    masked: list = field(default_factory=list)      # 표시만 한 단어
    expanded: list = field(default_factory=list)    # (줄임말, 확장형)
    ambiguous: list = field(default_factory=list)   # (줄임말, [후보 뜻...])

    @property
    def empty(self):
        return not re.search(r"[0-9A-Za-z가-힣]", self.text)


def _load_csv(name):
    with open(DICT_DIR / name, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _abbr_regex(row):
    abbr = re.escape(row["abbr"])
    tail = ""
    exp = row["expansion"].replace(" ", "")
    # 이미 확장형으로 쓴 경우(중견기업, 임원면접)는 다시 바꾸지 않음
    if exp.startswith(row["abbr"]) and len(exp) > len(row["abbr"]):
        tail = f"(?!\\s?{re.escape(exp[len(row['abbr']):])})"
    flags = re.IGNORECASE if row["abbr"].isascii() else 0
    if row["match"] == "word":
        return re.compile(_WORD_START + abbr + tail + _WORD_END, flags)
    return re.compile(_WORD_START + abbr + tail, flags)


class Normalizer:
    def __init__(self, abbr_rows=None, prof_rows=None):
        abbr_rows = abbr_rows if abbr_rows is not None else _load_csv("abbreviations.csv")
        prof_rows = prof_rows if prof_rows is not None else _load_csv("profanity.csv")
        # 긴 줄임말부터 적용 (취준생 > 취준, PT면 > 면)
        self.abbrs = [(r, _abbr_regex(r)) for r in sorted(abbr_rows, key=lambda r: -len(r["abbr"]))]
        self.prof = [(r, re.compile(r["pattern"], re.IGNORECASE)) for r in prof_rows]

    def __call__(self, s: str) -> Normalized:
        original = s
        # 전각 영숫자(ＡＩ)만 반각으로, 한글 자모(ㅋ, ㅅㅂ)는 그대로 둠
        s = "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in s)
        s = unicodedata.normalize("NFC", s).strip()

        removed, masked = [], []
        for row, rx in self.prof:
            hits = [m.group(0) for m in rx.finditer(s) if m.group(0).strip()]
            if not hits:
                continue
            if row["action"] == "mask":
                masked += hits
            else:
                removed += hits
                s = rx.sub(" ", s)

        s = _NOISE.sub(" ", s)

        expanded, ambiguous = [], []
        for row, rx in self.abbrs:
            if not rx.search(s):
                continue
            if row["ambiguous"] == "Y":
                ambiguous.append((row["abbr"], [row["expansion"]] + [a for a in row["alt_expansions"].split("|") if a]))
            else:
                s = rx.sub(row["expansion"], s)
                expanded.append((row["abbr"], row["expansion"]))

        s = re.sub(r"\s+", " ", s).strip()

        variants = [s]
        for row, rx in self.abbrs:
            if row["ambiguous"] == "Y" and rx.search(s):
                variants.append(re.sub(r"\s+", " ", rx.sub(row["expansion"], s)).strip())

        return Normalized(original, s, variants, removed, masked, expanded, ambiguous)


_default = None


def normalize(s: str) -> Normalized:
    global _default
    if _default is None:
        _default = Normalizer()
    return _default(s)


# 퍼지(1차) 점수용: 문장부호를 지우고 2글자 이상 단어 끝의 조사를 뗌.
# 조사 떼기만으로 대표질문 색인 기준 퍼지 1위 정답률 81.1% → 85.0% (dict/README.md 참고)
_JOSA = re.compile(r"(?<=[가-힣]{2})(?:에서는|에서|에게|으로|이랑|은|는|이|가|을|를|에|의|도|로|와|과|랑|만)$")


def keyword_form(text: str) -> str:
    tokens = re.sub(r"[^\w가-힣 ]", " ", text).split()
    return " ".join(_JOSA.sub("", t) for t in tokens)
