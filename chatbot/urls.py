from django.urls import path

from . import views

app_name = "chatbot"

urlpatterns = [
    path("", views.chat, name="chat"),
    path("faq/", views.faq_list, name="faq"),
    path("dict/", views.dictionary, name="dict"),
    path("api/chat/", views.api_chat, name="api_chat"),
    path("api/faq/<str:faq_id>/", views.api_faq, name="api_faq"),
    path("api/category/", views.api_category, name="api_category"),
    path("api/normalize/", views.api_normalize, name="api_normalize"),
    path("api/status/", views.api_status, name="api_status"),
]
