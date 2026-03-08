# 🤖 GWS(Google Workspace) 연동 Telegram Bot 구축 가이드

본 가이드는 `gwcli`(Google Workspace CLI)를 활용하여 Gmail, Calendar, Drive 등의 Google Workspace 환경을 텔레그램 메신저에서 AI(Gemini)와 대화하며 제어할 수 있는 봇을 구축하는 과정을 상세히 안내합니다.

## 📌 1. 아키텍처 및 주요 기술 스택

이 봇은 사용자의 자연어 요청을 해석하여 실제 GWS 명령어로 연결해주는 스마트 비서 역할을 합니다.

- **Telegram Bot API (`python-telegram-bot`)**: 텔레그램 메시지 엔드포인트 처리 및 사용자와의 대화 인터페이스 담당.
- **Gemini API (`gemini-2.0-flash`)**: 사용자의 자연어 요청 분석 및 **Function Calling** 수행.
- **GWS CLI (`gwcli`)**: 내부 시스템 하위 프로세스로 실행되어 실제 Google Workspace API(메일 조회 및 전송, 일정 관리, 드라이브 검색 등) 작업을 매개하는 CLI 명령형 툴.
- **FastAPI / Uvicorn**: Cloud Run과 같은 클라우드 (Webhook) 환경 배포 시 사용되는 웹 프레임워크 베이스.

## 📂 2. 핵심 파일 구조와 역할

이 텔레그램 봇은 크게 세 가지 주요 Python 스크립트 파일과 설정 파일로 구성되어 있습니다.

- **`gemini_bot.py`**: 로컬 환경에서 **Long Polling** 방식으로 봇을 실행하는 메인 프로그램입니다. 지정된 단일/복수 사용자만 봇을 사용할 수 있게 하는 보안 필터링(`chat_id` 확인), Gemini 대화 세션 유지, 텔레그램 기본 메시지 제한(4096자) 극복을 위한 분할 전송 기능이 구현되어 있습니다.
- **`tools.py`**: 봇(Gemini)이 사용할 수 있는 여러 가지 도구(Tools) 모음입니다. `_run_gwcli()` 함수를 이용해 `gmail_list`, `calendar_create`, `drive_search` 등의 GWS 관련 명령어를 직접 호출하고 그 결과를 파싱합니다. 추가적으로 `bkit_skills` 연결과 로컬 파일/디렉토리 시스템 접근 도구를 포함합니다.
- **`cloud_run_bot.py`**: GCP(구글 클라우드 플랫폼) Cloud Run과 같은 서버리스 환경에 배포하기 알맞게 설계되었습니다. 롱 폴링 대신 **Webhook** 패턴을 적용하여, 웹 요청(HTTP POST)이 올 때만 동작하도록 FastAPI 기반으로 개발되었습니다.
- **`.env`**: 애플리케이션 구동에 필요한 키와 환경 설정값을 보관하는 설정 파일입니다. (보안을 위해 깃에서는 제외되어야 합니다.)

## 🛠 3. 설정 및 구축 단계

### Step 1: 의존성 패키지 설치
봇을 구동하기 위한 필수 라이브러리를 설치합니다.
```bash
pip install -r requirements.txt
```

### Step 2: GWS CLI (`gwcli`) 설치 및 인증
- 본 봇은 `gwcli`에 완전히 의존합니다. 따라서 봇이 구동될 로컬 PC나 서버 컨테이너에 먼저 `gwcli` 패키지(npm 등)가 설치되어 있어야 합니다.
- 또한 사용자의 Google 계정으로 접근 권한을 얻기 위한 OAuth 로그인 절차 등의 인증이 사전 통과되어 있어야 작동합니다.

### Step 3: .env 구성
서버나 봇 구동 프로그램 최상단 경로에 `.env` 파일을 생성하고 다음 정보를 기입합니다.
```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
CHAT_ID=YOUR_ALLOWED_CHAT_ID
BKIT_PATH=./bkit_skills
```
> **Tip:** 처음 봇을 실행하려 할 때 텔레그램 Chat ID를 모르겠다면, 우선 `CHAT_ID` 값을 비운 채 봇을 시작합니다. 텔레그램 봇에 들어가 `/start` 명령어를 치면 당신의 Chat ID를 봇이 알려줍니다. 해당 번호를 복사해 설정에 추가하면 그때부터 보안이 활성화됩니다.

### Step 4: 봇 실행 방법

운영 환경(Local vs Web) 목적에 따라 다음 두 가지 방식 중 하나를 선택해 실행합니다.

**방법 A. 로컬 및 백그라운드 환경 (Long Polling 방식)**
외부 연결 포트를 포워딩할 필요가 없는 개인 PC나 내부망 서버 환경에서 적합합니다.
```bash
python gemini_bot.py
```

**방법 B. 클라우드 배포 환경 (Cloud Run / Webhook 방식)**
GCP Cloud Run 등에 서빙하여 완전 관리형 서비스로 띄울 경우 사용합니다. 
```bash
uvicorn cloud_run_bot:app --host 0.0.0.0 --port 8080
```
*(참고로 프로젝트 내 포함된 `Dockerfile`을 통해 도커 허브 또는 GCR 등에 빌드 이미지를 푸쉬하여 배포할 수 있습니다.)*

## 💡 4. 서비스 작동 흐름도 (Workflow)

실제로 사용자가 텔레그램 봇과 대화하여 GWS 작업을 처리하는 흐름은 다음과 같습니다.

1. **사용자 요청 수신**: 사용자가 스마트폰 텔레그램에 "다음 주 월요일 오후 2시 세일즈 미팅 잡아줘"라고 전송.
2. **보안 및 컨텍스트 확인**: `gemini_bot.py` 에서 등록된 사용자가 권한이 있는지 필터링 후, 이전 대화 내용(History 컨텍스트)과 메시지를 결합합니다.
3. **AI 의도 분석**: 조합된 정보를 Gemini 2.0 모델 API로 전달합니다.
4. **Function Calling 요청**: Gemini는 사용자 문장의 의도를 파악하고 외부 기능 실행이 필수적이라 판단하여, `tools.py`에 선언된 `calendar_create` 함수의 매개변수를 생성해 봇 프로그램으로 응답(콜백)합니다.
5. **GWS API 연동**: 파이썬 앱은 이것을 해석, 내부 시스템의 서브프로세스 쉘(Subprocess Shell)을 통해 `gwcli calendar create "세일즈 미팅" --start "next monday 14:00"` 형식의 명령어로 치환하여 실행합니다.
6. **결과 수집 로직**: `gwcli` 가 반환한 결과 및 상태(성공, 실패 등)를 JSON 포맷으로 저장 및 취합하여 다시 Gemini 모델에게 전송합니다.
7. **최종 응답 발송**: Gemini는 도구의 실행 결과값을 확인하여 자연스럽게 문맥을 다듬은 후 `("네, 등록하신 세일즈 미팅을 다음 주 월요일 오후 2시에 추가 완료했습니다.")` 텔레그램으로 최종 메시지를 전송합니다.
