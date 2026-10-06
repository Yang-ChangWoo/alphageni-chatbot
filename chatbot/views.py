import json

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .engine import NotLoaded, faq_dict, get_engine
from .models import FAQ, Abbreviation, ChatLog, Expression, Profanity

MAX_LEN = 1000

# 카테고리별 아이콘 (Material Symbols)
CATEGORY_ICONS = {
    "직무 탐색·전환": "explore",
    "이력서·자소서": "edit_note",
    "면접·인적성": "record_voice_over",
    "채용공고·지원전략": "campaign",
    "경험·포트폴리오": "work_history",
    "역량개발·준비계획": "trending_up",
}


def _counts():
    return {"faq_count": FAQ.objects.count(), "expr_count": Expression.objects.count(),
            "abbr_count": Abbreviation.objects.count(), "prof_count": Profanity.objects.count()}


def _categories():
    return [{"name": c, "icon": CATEGORY_ICONS.get(c, "help"), "count": FAQ.objects.filter(category=c).count()}
            for c in FAQ.objects.order_by("category").values_list("category", flat=True).distinct()]


def _quick_chips():
    """카테고리마다 우선순위 '상' FAQ 중 가장 짧은 대표 질문 하나 (자주 묻는 질문 바로가기)."""
    chips = []
    for c in _categories():
        qs = FAQ.objects.filter(category=c["name"])
        pool = list(qs.filter(priority="상")) or list(qs)
        if pool:
            f = min(pool, key=lambda f: len(f.rep_question))
            chips.append({"text": f.rep_question, "icon": c["icon"]})
    return chips


def chat(request):
    return render(request, "chatbot/chat.html", {
        **_counts(), "chips": _quick_chips(), "nav": "chat", "categories": _categories(),
    })


def faq_list(request):
    qs = FAQ.objects.all()
    cat = request.GET.get("category", "")
    q = request.GET.get("q", "").strip()
    if cat:
        qs = qs.filter(category=cat)
    if q:
        qs = qs.filter(Q(rep_question__icontains=q) | Q(answer__icontains=q) | Q(expressions__text__icontains=q)).distinct()
    page = Paginator(qs.prefetch_related("expressions"), 15).get_page(request.GET.get("page"))
    return render(request, "chatbot/faq.html", {
        **_counts(), "nav": "faq", "page": page, "categories": _categories(), "category": cat, "q": q,
        "total": qs.count(),
    })


def dictionary(request):
    return render(request, "chatbot/dict.html", {
        **_counts(), "nav": "dict",
        "abbrs": Abbreviation.objects.order_by("category", "abbr"),
        "profs": Profanity.objects.all(),
    })


def _engine_or_error():
    try:
        return get_engine(), None
    except NotLoaded as e:
        return None, JsonResponse({"error": str(e)}, status=503)


def _body(request):
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


# 로그인 없는 검색 API라 CSRF를 끔 (Netlify 프록시처럼 주소가 바뀌어도 동작하게)
@csrf_exempt
@require_POST
def api_chat(request):
    q = str(_body(request).get("q", "")).strip()[:MAX_LEN]
    if not q:
        return JsonResponse({"error": "질문을 입력해 주세요."}, status=400)
    engine, err = _engine_or_error()
    if err:
        return err
    res = engine.match(q)
    top = res["candidates"][0] if res["candidates"] else {}
    ChatLog.objects.create(query=q, normalized=res["normalized"], grade=res["grade"],
                           top1_faq=top.get("faq_id", ""), top1_score=res["top1_score"],
                           gap=res["gap"], reason=res["reason"][:200])
    if res["grade"] == "LOW":
        res["categories"] = [{"name": c, "icon": CATEGORY_ICONS.get(c, "help")} for c in res["categories"]]
    return JsonResponse(res)


@require_GET
def api_faq(request, faq_id):
    f = get_object_or_404(FAQ, faq_id=faq_id)
    return JsonResponse(faq_dict(f))


@require_GET
def api_category(request):
    name = request.GET.get("name", "")
    qs = FAQ.objects.filter(category=name)
    picks = list(qs.filter(priority="상").order_by("row_no")[:5]) or list(qs[:5])
    return JsonResponse({"category": name, "questions": [{"faq_id": f.faq_id, "text": f.rep_question} for f in picks]})


@csrf_exempt
@require_POST
def api_normalize(request):
    engine, err = _engine_or_error()
    if err:
        return err
    n = engine.norm(str(_body(request).get("q", ""))[:MAX_LEN])
    return JsonResponse({"normalized": n.text, "variants": n.variants, "profanity_removed": n.profanity,
                         "masked": n.masked, "abbr_expanded": n.expanded, "abbr_ambiguous": n.ambiguous,
                         "empty": n.empty})


@require_GET
def api_status(request):
    engine, err = _engine_or_error()
    if err:
        return err
    return JsonResponse({"mode": engine.mode, "note": engine.mode_note, "expressions": len(engine.expr_text)})
