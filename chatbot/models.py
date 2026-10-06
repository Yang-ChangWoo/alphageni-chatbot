from django.db import models


class FAQ(models.Model):
    faq_id = models.CharField("FAQ ID", max_length=20, unique=True)
    category = models.CharField("카테고리", max_length=40, db_index=True)
    job_group = models.CharField("직무군", max_length=60, blank=True)
    rep_question = models.TextField("대표 질문")
    answer = models.TextField("답변")
    discovery_route = models.CharField("발굴 경로", max_length=100, blank=True)
    discovery_source = models.TextField("질문 출처", blank=True)
    evidence_source = models.TextField("근거 자료", blank=True)
    evidence_summary = models.TextField("근거 요약", blank=True)
    priority = models.CharField("우선순위", max_length=4, blank=True)
    checked_date = models.CharField("확인일", max_length=20, blank=True)
    review_status = models.CharField("검토 상태", max_length=20, blank=True)
    note = models.TextField("비고", blank=True)
    row_no = models.PositiveIntegerField("순번", default=0)

    class Meta:
        ordering = ["row_no"]
        verbose_name = verbose_name_plural = "FAQ"

    def __str__(self):
        return f"{self.faq_id} {self.rep_question[:40]}"


class Expression(models.Model):
    """검색 대상 표현: FAQ마다 대표 질문 1개 + 유사 질문 9개."""
    expr_id = models.CharField(max_length=20, unique=True)
    faq = models.ForeignKey(FAQ, on_delete=models.CASCADE, related_name="expressions")
    text = models.TextField("표현")
    is_representative = models.BooleanField("대표 질문", default=False)
    variation_type = models.CharField("유형", max_length=30, blank=True)
    variation_label = models.CharField("유형 설명", max_length=60, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = verbose_name_plural = "검색 표현"

    def __str__(self):
        return self.text


class Abbreviation(models.Model):
    abbr = models.CharField("줄임말", max_length=40, unique=True)
    expansion = models.CharField("확장형", max_length=100)
    category = models.CharField("분류", max_length=40, blank=True)
    ambiguous = models.BooleanField("다의어", default=False)
    alt_expansions = models.CharField("다른 뜻(|구분)", max_length=200, blank=True)
    match = models.CharField("매칭 방식", max_length=10, default="prefix",
                             choices=[("prefix", "prefix"), ("word", "word")])
    note = models.TextField("비고", blank=True)

    class Meta:
        ordering = ["abbr"]
        verbose_name = verbose_name_plural = "줄임말 사전"

    def __str__(self):
        return f"{self.abbr} → {self.expansion}"

    def as_row(self):
        return {"abbr": self.abbr, "expansion": self.expansion, "ambiguous": "Y" if self.ambiguous else "N",
                "alt_expansions": self.alt_expansions, "match": self.match}


class Profanity(models.Model):
    word = models.CharField("비속어", max_length=40)
    pattern = models.CharField("정규식", max_length=300)
    type = models.CharField("유형", max_length=20, blank=True)
    severity = models.PositiveSmallIntegerField("심각도", default=1)
    action = models.CharField("처리", max_length=10, default="remove",
                              choices=[("remove", "제거"), ("mask", "표시만")])
    note = models.TextField("비고", blank=True)

    class Meta:
        ordering = ["-severity", "word"]
        verbose_name = verbose_name_plural = "비속어 사전"

    def __str__(self):
        return self.word

    def as_row(self):
        return {"word": self.word, "pattern": self.pattern, "action": self.action}


class ChatLog(models.Model):
    """챗봇에 들어온 질문과 판정 결과 (시험 질문 결과 확인용)."""
    created_at = models.DateTimeField("시각", auto_now_add=True)
    query = models.TextField("질문")
    normalized = models.TextField("정규화", blank=True)
    grade = models.CharField("등급", max_length=4)
    top1_faq = models.CharField("1위 FAQ", max_length=20, blank=True)
    top1_score = models.FloatField("1위 점수", default=0)
    gap = models.FloatField("1·2위 차", default=0)
    reason = models.CharField("판정 근거", max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "질문 기록"

    def __str__(self):
        return f"[{self.grade}] {self.query[:40]}"
