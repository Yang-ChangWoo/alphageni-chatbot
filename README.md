---
title: 알파지니 취업 챗봇
emoji: 🤖
colorFrom: pink
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# 알파지니 취업 챗봇 (Django)

FAQ 580개(대표 질문 + 유사 질문 9개 = 검색 표현 5,800개)와 줄임말·비속어 사전으로 질문에 답하는 검색형 챗봇입니다.
화면은 Stitch 디자인(Warm Radiant Conversational UI)을 따랐습니다.

## 화면
| 주소 | 내용 |
|---|---|
| `/` 상담 라운지 | 채팅. HIGH는 답변+출처, MID는 후보 3개 선택, LOW는 다시 질문 안내와 6개 분야 |
| `/faq/` 취업 Q&A | FAQ 580개를 분야별로 보고 검색. 펼치면 답변, 출처, 검색 표현 10개 |
| `/dict/` 사전 점검 | 줄임말 246개, 비속어 70개 목록과 문장 정규화 테스트 |
| `/admin/` | FAQ, 표현, 사전, 질문 기록(ChatLog) 관리 |

채팅 입력창의 **점수 보기**를 켜면 판정 근거와 후보별 최종·임베딩·퍼지 점수가 함께 나옵니다.

## 로컬 실행 (Windows PowerShell 기준)
```powershell
cd web
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py load_faq      # data/faq_580_with_similar.csv + data/expressions_580.csv
python manage.py load_dicts    # data/abbreviations.csv + data/profanity.csv
python manage.py build_index   # ko-sroberta로 표현 5,800개 임베딩 → index/expr_embeddings.npy (처음엔 모델 내려받기)
python manage.py createsuperuser   # 관리자 페이지를 쓸 때만

python manage.py runserver
```
`db.sqlite3`에는 이미 데이터가 적재돼 있어서 `load_faq`, `load_dicts`는 건너뛰어도 됩니다.
브라우저에서 http://127.0.0.1:8000 을 엽니다. 오른쪽 위가 **AI 응답 가능**이면 임베딩+퍼지로 동작 중이고,
**퍼지 전용 모드**면 모델을 불러오지 못한 것입니다(마우스를 올리면 이유가 보입니다).

터미널에서 바로 물어보거나 시험 질문을 한꺼번에 돌릴 수도 있습니다.
```powershell
python manage.py ask "자소서 AI로 써도 됨?"
python manage.py ask --csv 시험질문.csv --out 결과.csv   # query 열이 있는 CSV
```

## 검색 방식
1. 정규화: 비속어 제거 → 반복 기호(ㅋㅋ, ㅠㅠ, !!) 정리 → 줄임말 확장. 뜻이 여러 개인 줄임말은 모든 뜻으로 검색
2. 점수: `0.80 × 임베딩(jhgan/ko-sroberta-multitask 코사인) + 0.20 × 퍼지(token_set_ratio)`
3. FAQ 점수 = 그 FAQ 표현 10개 중 최고점
4. 등급: **HIGH** 1위 ≥ 0.75 그리고 1·2위 차 ≥ 0.05 / **LOW** 1위 < 0.43 / 나머지 **MID**

기준값은 질문 200개 Grid Search(validation 140 / test 60, test 정확도 96.7%)로 정했고 `config/settings.py`의 `CHATBOT`에 있습니다.
`chatbot/engine.py`는 `search/matcher.py`와 같은 로직을 DB에서 읽도록 옮긴 것으로, 200문항에서 두 결과가 모두 같습니다(퍼지 모드로 확인).

**벡터 DB는 쓰지 않습니다.** FAQ·표현·사전은 SQLite(RDBMS)에 넣고, 임베딩(5,800 × 768, 약 18MB)은 `.npy` 파일로 저장해
서버가 뜰 때 메모리에 한 번 올립니다. 질문마다 numpy 행렬곱으로 5,800개 전체를 비교해도 수 밀리초면 끝납니다.

## 데이터를 바꿨을 때
CSV를 고친 뒤 `load_faq` / `load_dicts` → `build_index` 순서로 다시 실행하고 서버를 재시작하세요.
`build_index`를 빼먹어도 서버가 데이터가 바뀐 것을 알아채고 처음 뜰 때 임베딩을 다시 만듭니다.

## 배포 (Hugging Face Spaces + Netlify)
Netlify는 정적 사이트와 JavaScript·Go 함수만 실행해서 Django(Python)와 ko-sroberta 모델을 직접 돌릴 수 없습니다.
그래서 Django 서버는 Hugging Face Spaces(무료, 메모리 16GB, Docker)에 올리고, Netlify는 그 서버로 요청을 넘기는 주소 역할만 합니다.

1. **Hugging Face Space 만들기**: https://huggingface.co/new-space → 이름(예: `alphageni-chatbot`), SDK는 **Docker**, Blank 템플릿, Public
2. **파일 올리기**: Space의 Files → Add file → Upload files 에 이 `web` 폴더 안의 파일과 폴더를 전부 끌어다 놓고 Commit
   (`db.sqlite3`, `.venv`, `netlify` 폴더는 빼도 됩니다. 이 README 맨 위의 `sdk: docker`, `app_port: 7860` 설정을 Space가 읽습니다)
3. **(선택) Settings → Variables and secrets** 에 `DJANGO_SECRET_KEY`(아무 긴 문자열) 추가
4. 빌드 로그(Logs)가 끝나면 `https://<아이디>-alphageni-chatbot.hf.space` 에서 챗봇이 열립니다.
   빌드 때 모델을 내려받고 임베딩 5,800개를 만들어서 처음 빌드는 10분 정도 걸립니다.
5. **Netlify 연결**: `netlify/_redirects` 의 `YOUR-ID-alphageni-chatbot.hf.space` 를 4번 주소로 바꾼 뒤,
   app.netlify.com → Add new project → Deploy manually(“Upload your project files”)에 **`netlify` 폴더**를 끌어다 놓습니다.
   이제 `https://<사이트이름>.netlify.app` 으로 접속하면 챗봇이 보입니다.
6. Netlify 주소에서 `/admin/` 로그인까지 쓰려면 Space의 Variables에 `CSRF_TRUSTED_ORIGINS=https://<사이트이름>.netlify.app` 를 추가하고,
   Space 안에서 관리자 계정이 필요하면 Dockerfile의 RUN 줄 끝에 `createsuperuser --noinput`(환경변수 `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_PASSWORD`)를 넣으세요.

무료 Space는 48시간 동안 접속이 없으면 잠들고, 다음 접속 때 1~2분 깨어나는 시간이 걸립니다. 시연 전에 한 번 열어 두세요.

## 폴더 구조
```
config/                 settings.py (검색 기준값 CHATBOT), urls.py
chatbot/
  models.py             FAQ, Expression, Abbreviation, Profanity, ChatLog
  engine.py             검색 엔진 (서버당 한 번 생성해서 재사용)
  normalize.py          정규화 (search/normalize.py 복사본)
  views.py, urls.py     화면 3개 + API (/api/chat/, /api/faq/<id>/, /api/category/, /api/normalize/, /api/status/)
  management/commands/  load_faq, load_dicts, build_index, ask
  templates/, static/   화면 (app.css는 Tailwind로 빌드한 파일)
data/                   적재할 CSV 4개
index/                  build_index가 만든 임베딩
Dockerfile              Hugging Face Spaces 배포용
netlify/                Netlify에 올릴 폴더 (_redirects로 Space에 연결)
tailwind/               디자인 토큰. 화면 클래스를 바꿨다면 web 폴더에서 아래 명령으로 app.css 다시 빌드
                        npx tailwindcss@3 -c tailwind/tailwind.config.js -i tailwind/input.css -o chatbot/static/chatbot/app.css --minify
```
