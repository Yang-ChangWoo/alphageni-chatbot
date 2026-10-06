from django.contrib import admin

from .models import FAQ, Abbreviation, ChatLog, Expression, Profanity


class ExpressionInline(admin.TabularInline):
    model = Expression
    extra = 0
    fields = ("expr_id", "text", "variation_label", "is_representative")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("faq_id", "category", "rep_question", "priority")
    list_filter = ("category", "priority")
    search_fields = ("faq_id", "rep_question", "answer")
    inlines = [ExpressionInline]


@admin.register(Expression)
class ExpressionAdmin(admin.ModelAdmin):
    list_display = ("expr_id", "faq", "text", "variation_label")
    list_filter = ("variation_label",)
    search_fields = ("text", "faq__faq_id")


@admin.register(Abbreviation)
class AbbreviationAdmin(admin.ModelAdmin):
    list_display = ("abbr", "expansion", "category", "ambiguous", "match")
    list_filter = ("category", "ambiguous", "match")
    search_fields = ("abbr", "expansion")


@admin.register(Profanity)
class ProfanityAdmin(admin.ModelAdmin):
    list_display = ("word", "type", "severity", "action", "pattern")
    list_filter = ("type", "action", "severity")
    search_fields = ("word",)


@admin.register(ChatLog)
class ChatLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "grade", "query", "top1_faq", "top1_score", "gap")
    list_filter = ("grade",)
    search_fields = ("query",)
