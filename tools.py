"""
GWS Agent Tools
- gwcli CLI를 래핑하여 Gemini Function Calling에서 사용할 도구를 정의합니다.
- Gmail, Calendar, Drive, Shell 명령을 지원합니다.
"""

import subprocess
import json
import logging
import shutil
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# gwcli 실행 경로 자동 탐지
GWCLI_PATH = shutil.which("gwcli")


def _run_gwcli(args: list[str], timeout: int = 30) -> dict:
    """gwcli 명령을 실행하고 결과를 반환합니다."""
    if not GWCLI_PATH:
        return {"error": "gwcli가 설치되지 않았습니다. 'npm link'를 실행해주세요."}

    cmd = [GWCLI_PATH] + args + ["--format", "json"]
    logger.info("Running: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        
        stdout = result.stdout or ""
        stderr = result.stderr or ""

        if result.returncode != 0:
            return {"error": stderr.strip() or f"명령 실행 실패 (코드: {result.returncode})"}

        try:
            return {"result": json.loads(stdout)}
        except json.JSONDecodeError:
            return {"result": stdout.strip()}

    except subprocess.TimeoutExpired:
        return {"error": f"명령 실행 시간 초과 ({timeout}초)"}
    except Exception as e:
        return {"error": str(e)}


def _run_shell(command: str, timeout: int = 30) -> dict:
    """안전한 쉘 명령을 실행합니다."""
    # 위험한 명령 차단
    dangerous = ["rm -rf", "del /f", "format", "mkfs", "dd if="]
    for d in dangerous:
        if d in command.lower():
            return {"error": f"위험한 명령어가 감지되었습니다: {d}"}

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        output = stdout.strip() or stderr.strip()
        return {"result": output, "exit_code": result.returncode}
    except subprocess.TimeoutExpired:
        return {"error": f"명령 실행 시간 초과 ({timeout}초)"}
    except Exception as e:
        return {"error": str(e)}


# ─── Tool 실행 함수 매핑 ─────────────────────────────────────
def execute_tool(tool_name: str, args: dict) -> str:
    """도구를 실행하고 결과를 문자열로 반환합니다."""
    result = None

    if tool_name == "gmail_list":
        cmd = ["gmail", "list"]
        if args.get("unread"):
            cmd.append("--unread")
        if args.get("limit"):
            cmd.extend(["--limit", str(args["limit"])])
        result = _run_gwcli(cmd)

    elif tool_name == "gmail_search":
        query = args.get("query", "")
        result = _run_gwcli(["gmail", "search", query])

    elif tool_name == "gmail_read":
        message_id = args.get("message_id", "")
        result = _run_gwcli(["gmail", "read", message_id])

    elif tool_name == "gmail_send":
        cmd = ["gmail", "send"]
        cmd.extend(["--to", args.get("to", "")])
        cmd.extend(["--subject", args.get("subject", "")])
        cmd.extend(["--body", args.get("body", "")])
        result = _run_gwcli(cmd)

    elif tool_name == "gmail_reply":
        cmd = ["gmail", "reply", args.get("message_id", "")],
        cmd.extend(["--body", args.get("body", "")])
        result = _run_gwcli(cmd)

    elif tool_name == "calendar_events":
        cmd = ["calendar", "events"]
        if args.get("days"):
            cmd.extend(["--days", str(args["days"])])
        if args.get("limit"):
            cmd.extend(["--limit", str(args["limit"])])
        result = _run_gwcli(cmd)

    elif tool_name == "calendar_search":
        query = args.get("query", "")
        result = _run_gwcli(["calendar", "search", query])

    elif tool_name == "calendar_create":
        cmd = ["calendar", "create", args.get("title", "")]
        cmd.extend(["--start", args.get("start", "")])
        if args.get("end"):
            cmd.extend(["--end", args["end"]])
        result = _run_gwcli(cmd)

    elif tool_name == "drive_list":
        cmd = ["drive", "list"]
        if args.get("limit"):
            cmd.extend(["--limit", str(args["limit"])])
        result = _run_gwcli(cmd)

    elif tool_name == "drive_search":
        query = args.get("query", "")
        result = _run_gwcli(["drive", "search", query])

    elif tool_name == "run_shell":
        command = args.get("command", "")
        result = _run_shell(command)

    elif tool_name == "read_file":
        path = Path(args.get("path", ""))
        try:
            if not path.exists():
                result = {"error": f"파일이 존재하지 않습니다: {path}"}
            else:
                result = {"result": path.read_text(encoding="utf-8")}
        except Exception as e:
            result = {"error": str(e)}

    elif tool_name == "write_file":
        path = Path(args.get("path", ""))
        content = args.get("content", "")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            result = {"result": f"파일 작성 완료: {path}"}
        except Exception as e:
            result = {"error": str(e)}

    elif tool_name == "list_files":
        directory = Path(args.get("directory", "."))
        try:
            if not directory.is_dir():
                result = {"error": f"디렉토리가 아닙니다: {directory}"}
            else:
                files = [str(p.relative_to(directory)) for p in directory.glob("**/*") if p.is_file()]
                result = {"result": files[:100]}  # 최대 100개
        except Exception as e:
            result = {"error": str(e)}

    elif tool_name == "activate_skill":
        skill_name = args.get("skill_name", "")
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
            bkit_path = Path(cfg.get("bkit_path", ""))
            skill_path = bkit_path / "skills" / skill_name / "SKILL.md"

            if not skill_path.exists():
                result = {"error": f"스킬을 찾을 수 없습니다: {skill_name}"}
            else:
                result = {"result": skill_path.read_text(encoding="utf-8"), "skill": skill_name}
        except Exception as e:
            result = {"error": str(e)}

    elif tool_name == "cokacdir_transfer":
        src = args.get("src", "")
        dest = args.get("dest", "")
        result = _run_shell(f"cokacdir {src} {dest}")

    elif tool_name == "gemini_cli_agent":
        prompt = args.get("prompt", "")
        with open("config.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        api_key = cfg.get("gemini_api_key")
        
        # 환경 변수 설정 후 gemini CLI 실행
        env = os.environ.copy()
        env["GOOGLE_GENAI_API_KEY"] = api_key
        
        # bkit 확장과 함께 실행됨 (이미 링크됨)
        # 비대화형 모드로 실행하여 결과를 텍스트로 받음
        cmd = f"gemini \"{prompt}\" --non-interactive"
        result = _run_shell(cmd)

    else:
        result = {"error": f"알 수 없는 도구: {tool_name}"}

    return json.dumps(result, ensure_ascii=False, indent=2)


# ─── Gemini Function Calling용 도구 선언 ────────────────────
TOOL_DECLARATIONS = [
    {
        "name": "gmail_list",
        "description": "최근 이메일 목록을 조회합니다. 읽지 않은 메일만 필터링할 수 있습니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "unread": {
                    "type": "boolean",
                    "description": "true이면 읽지 않은 메일만 표시",
                },
                "limit": {
                    "type": "integer",
                    "description": "조회할 이메일 수 (기본값: 10)",
                },
            },
        },
    },
    {
        "name": "gmail_search",
        "description": "Gmail에서 이메일을 검색합니다. Gmail 검색 쿼리를 사용합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Gmail 검색 쿼리 (예: 'from:boss@company.com', 'subject:회의')",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "gmail_read",
        "description": "특정 이메일의 전체 내용을 읽습니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "읽을 이메일의 메시지 ID",
                },
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "gmail_send",
        "description": "새 이메일을 작성하고 전송합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "수신자 이메일 주소",
                },
                "subject": {
                    "type": "string",
                    "description": "이메일 제목",
                },
                "body": {
                    "type": "string",
                    "description": "이메일 본문 내용",
                },
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "gmail_reply",
        "description": "기존 이메일에 답장합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "message_id": {
                    "type": "string",
                    "description": "답장할 이메일의 메시지 ID",
                },
                "body": {
                    "type": "string",
                    "description": "답장 내용",
                },
            },
            "required": ["message_id", "body"],
        },
    },
    {
        "name": "calendar_events",
        "description": "캘린더에서 향후 일정을 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "앞으로 며칠간의 일정을 조회할지 (기본값: 7)",
                },
                "limit": {
                    "type": "integer",
                    "description": "조회할 일정 수 (기본값: 10)",
                },
            },
        },
    },
    {
        "name": "calendar_search",
        "description": "캘린더에서 일정을 검색합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색할 일정 키워드",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "calendar_create",
        "description": "새 캘린더 일정을 생성합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "일정 제목",
                },
                "start": {
                    "type": "string",
                    "description": "시작 시간 (예: '2025-01-15 10:00' 또는 'tomorrow 12:00')",
                },
                "end": {
                    "type": "string",
                    "description": "종료 시간 (선택사항)",
                },
            },
            "required": ["title", "start"],
        },
    },
    {
        "name": "drive_list",
        "description": "Google Drive의 파일 목록을 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "조회할 파일 수 (기본값: 10)",
                },
            },
        },
    },
    {
        "name": "drive_search",
        "description": "Google Drive에서 파일을 검색합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색 쿼리 (예: \"name contains 'report'\")",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "run_shell",
        "description": "시스템 쉘 명령어를 실행합니다. gcloud, python 등 시스템 명령을 실행할 수 있습니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "실행할 쉘 명령어 (예: 'gcloud compute instances list')",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "로컬 파일의 내용을 읽습니다. PDCA 문서나 소스 코드를 읽을 때 사용합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "읽을 파일의 경로",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "로컬 파일을 생성하거나 덮어씁니다. PDCA 문서나 소스 코드를 저장할 때 사용합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "작성할 파일의 경로",
                },
                "content": {
                    "type": "string",
                    "description": "파일 내용",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "디렉토리 내의 파일 목록을 조회합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "조회할 디렉토리 경로 (기본값: '.')",
                },
            },
        },
    },
    {
        "name": "activate_skill",
        "description": "bkit에서 특정 도메인 지식(스킬)을 활성화하여 컨텍스트에 추가합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "활성화할 스킬 이름 (예: 'pdca', 'starter', 'phase-1-schema')",
                },
            },
            "required": ["skill_name"],
        },
    },
    {
        "name": "cokacdir_transfer",
        "description": "cokacdir을 사용하여 파일을 전송합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "src": {
                    "type": "string",
                    "description": "원본 파일 또는 디렉토리 경로",
                },
                "dest": {
                    "type": "string",
                    "description": "대상 경로",
                },
            },
            "required": ["src", "dest"],
        },
    },
    {
        "name": "gemini_cli_agent",
        "description": "공식 gemini CLI를 에이전트로 사용하여 복잡한 작업(bkit 워크플로우 등)을 수행합니다. 도구 호출 제한 문제를 해결할 수 있습니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "에이전트에게 전달할 명령",
                },
            },
            "required": ["prompt"],
        },
    },
]
