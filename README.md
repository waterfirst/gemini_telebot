# 🤖 Gemini Assistant (Telegram Bot with bkit)

Google Workspace(Gmail, Calendar, Drive)와 개발 워크플로우를 관리해주는 지능형 AI 에이전트입니다. **bkit(Vibecoding Kit) v1.5.0** 기반의 PDCA 방법론을 채택하여 체계적인 작업 수행을 지원합니다.

## 🚀 주요 기능

### 1. Google Workspace 통합 관리
*   **Gmail**: 최신 메일 스크랩, 요약, 답장 초안 작성 및 전송.
*   **Calendar**: 일정 조회, 새로운 일정 예약 및 알림.
*   **Drive**: 파일 검색 및 관리.

### 2. bkit PDCA 개발 워크플로우
모든 작업은 **Plan-Do-Check-Act** 사이클에 따라 체계적으로 진행됩니다.
*   `/pdca plan [feature]`: 새로운 기능이나 프로젝트 계획 수립.
*   `/pdca design [feature]`: 계획에 따른 상세 설계 및 아키텍처 정의.
*   `/pdca do [feature]`: 실제 구현 및 작업 수행 가이드.
*   `/pdca analyze [feature]`: 설계와 구현 간의 Gap 분석.
*   `/pdca iterate [feature]`: 분석 결과에 따른 자동 개선 반복.
*   `/pdca report [feature]`: 최종 완료 보고서 생성.

### 3. GitHub 자동 동기화
*   에이전트가 수행한 코드 수정, 문서 작성 등 모든 작업은 연결된 GitHub 레포지토리(`waterfirst/gemini_telebot`)에 자동으로 커밋 및 푸시됩니다.

### 4. 550+ 전문 스킬 라이브러리 연동
*   `antigravity-awesome-skills` 저장소를 통해 보안 분석, 아키텍처 설계, SEO 최적화 등 550개 이상의 전문화된 AI 스킬을 상황에 맞게 활성화하여 사용합니다.

## 🛠 사용 방법

텔레그램 대화창을 통해 자연어로 요청하거나 전용 명령어를 사용합니다.

*   **일반 요청**: "오늘 온 이란 관련 뉴스 요약해줘", "내일 오후 2시 회의 일정 잡아줘"
*   **개발 요청**: `/pdca plan 텔레그램 봇 기능 확장`
*   **분석 요청**: "현재 코드의 보안 취약점을 `security-auditor` 스킬로 분석해줘"

## ⚙️ 설정 방법 (환경 변수)

봇을 실행하기 전, 프로젝트 최상단에 `.env` 파일을 생성하고 다음 정보를 기입해야 합니다.
```env
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
TELEGRAM_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
CHAT_ID=YOUR_ALLOWED_CHAT_ID
BKIT_PATH=./bkit_skills
```
> **보안 주의**: 비밀 키(API Key 및 토큰)가 깃허브 등에 유출되지 않도록, `.env` 파일은 `.gitignore`에 등록되어 있습니다.

## 🏗 기술 스택
*   **Language**: Python
*   **AI Engine**: Google Gemini (Flash/Pro)
*   **Toolkit**: bkit v1.5.0 (AI-native development toolkit)
*   **Integrations**: Google Workspace API, GitHub API, Telegram Bot API

---
*Created and maintained by Gemini Assistant.*
