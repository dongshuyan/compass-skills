#!/usr/bin/env python3
"""Local onboarding questionnaire for user-profile-keeper."""

from __future__ import annotations

import argparse
import html
import json
import re
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import profile_store  # noqa: E402

CUSTOM_CHOICE_VALUE = "__custom__"

SECRET_PATTERNS = [
    ("private key block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE)),
    ("openai style api key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b")),
    ("github fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "credential assignment",
        re.compile(
            r"(?:api[_-]?key|token|secret|password|passwd|密码|口令|验证码)\s*[:：=]\s*['\"]?[^\s'\"]{6,}",
            re.IGNORECASE,
        ),
    ),
]

QUESTIONNAIRE_SECTIONS = [
    {
        "title": "基本背景信息",
        "fields": [
            {"name": "display_name", "label": "称呼", "type": "text", "autocomplete": "off", "profile": False},
            {
                "name": "language",
                "label": "主要语言",
                "type": "text",
                "placeholder": "例如：中文、英文、中英混合",
                "category": "communication_preference",
                "claim": "preferred_language",
                "sensitivity": "low",
            },
            {
                "name": "age_range",
                "label": "年龄段",
                "type": "choice",
                "options": ["18 岁以下", "18-24", "25-34", "35-44", "45-54", "55 岁及以上"],
                "category": "background_context",
                "claim": "age_range",
                "sensitivity": "private",
            },
            {
                "name": "education_level",
                "label": "最高学历或在读阶段",
                "type": "choice",
                "options": ["高中及以下", "本科在读/本科", "硕士在读/硕士", "博士在读/博士", "博士后或同等研究经历"],
                "category": "education_background",
                "claim": "education_level",
                "sensitivity": "private",
            },
            {
                "name": "major_field",
                "label": "专业、主修或研究方向",
                "type": "text",
                "placeholder": "例如：计算机、AI、系统、生命科学",
                "category": "education_background",
                "claim": "major_or_specialty",
                "sensitivity": "private",
            },
            {
                "name": "occupation_role",
                "label": "职业、角色或当前身份",
                "type": "text",
                "placeholder": "例如：学生、研究者、工程师、创业者",
                "category": "career_context",
                "claim": "occupation_or_role",
                "sensitivity": "private",
            },
            {
                "name": "experience_stage",
                "label": "经验阶段",
                "type": "choice",
                "options": ["刚开始学习", "有一定经验", "熟练/资深", "研究或专家级", "跨领域转入"],
                "category": "career_context",
                "claim": "experience_stage",
                "sensitivity": "private",
            },
            {
                "name": "domains",
                "label": "专业领域",
                "type": "text",
                "placeholder": "例如：AI、系统、论文写作、产品",
                "category": "domain_familiarity",
                "claim": "professional_domains",
                "sensitivity": "low",
            },
            {
                "name": "task_types",
                "label": "常见任务类型",
                "type": "text",
                "placeholder": "例如：代码、研究、skill 设计、发布",
                "category": "workflow_preference",
                "claim": "common_task_types",
                "sensitivity": "low",
            },
            {
                "name": "long_term_goals",
                "label": "长期目标或希望我长期帮助你的方向",
                "type": "textarea",
                "category": "learning_context",
                "claim": "long_term_goals",
                "sensitivity": "private",
            },
        ],
    },
    {
        "title": "沟通和澄清偏好",
        "note": "选择“用户自定义答案”后，文本框内容会作为该题答案进入待确认 proposal。",
        "fields": [
            {
                "name": "answer_length",
                "label": "回答长度和表达方式",
                "type": "choice",
                "options": ["短而直接", "结构化且中等详细", "完整详细", "视任务风险调整"],
                "category": "communication_preference",
                "claim": "answer_length",
                "sensitivity": "low",
            },
            {
                "name": "evidence_style",
                "label": "证据和来源要求",
                "type": "choice",
                "options": ["先结论，必要时给证据", "证据优先", "必须给来源和可复核路径"],
                "category": "communication_preference",
                "claim": "evidence_style",
                "sensitivity": "low",
            },
            {
                "name": "clarification_mode",
                "label": "我应该如何和你对齐需求",
                "type": "choice",
                "options": ["快速问关键问题", "先搜索/读文件再问", "一问一答深度对齐", "best guess 并标注假设"],
                "category": "clarification_style",
                "claim": "preferred_clarification_mode",
                "sensitivity": "low",
            },
            {
                "name": "challenge_style",
                "label": "我应该如何指出问题、反驳假设或提醒风险",
                "type": "choice",
                "options": ["只在明显有风险或错误时指出", "经常主动指出可能的问题和弱假设", "先按需求推进，最后集中列出风险"],
                "help": "这里指任务、方案、证据或假设，不是评价你本人。",
                "category": "communication_preference",
                "claim": "challenge_style",
                "sensitivity": "low",
            },
        ],
    },
    {
        "title": "能力边界和常见遗漏",
        "fields": [
            {
                "name": "clear_domains",
                "label": "哪些领域你通常表达得很清楚？",
                "type": "textarea",
                "category": "domain_familiarity",
                "claim": "clear_expression_domains",
                "sensitivity": "low",
            },
            {
                "name": "needs_scaffolding",
                "label": "哪些领域你需要更多结构化追问或例子？",
                "type": "textarea",
                "category": "capability_boundary",
                "claim": "needs_scaffolding_domains",
                "sensitivity": "low",
            },
            {
                "name": "common_omissions",
                "label": "你认为自己常漏掉哪些需求信息？",
                "type": "textarea",
                "placeholder": "例如：验收标准、非目标、证据边界、受众、输出格式、风险边界",
                "category": "common_omission",
                "claim": "self_reported_common_omissions",
                "sensitivity": "low",
            },
        ],
    },
    {
        "title": "风险和隐私边界",
        "fields": [
            {
                "name": "risk_confirmations",
                "label": "哪些动作前必须确认？",
                "type": "textarea",
                "placeholder": "例如：删除、覆盖、安装、发布、远程写入、credential、公开材料",
                "category": "risk_boundary",
                "claim": "actions_requiring_confirmation",
                "sensitivity": "low",
            },
            {
                "name": "never_save",
                "label": "哪些内容永远不要保存？",
                "type": "textarea",
                "category": "privacy_boundary",
                "claim": "never_save",
                "sensitivity": "private",
            },
            {
                "name": "confirm_before_save",
                "label": "哪些内容保存前必须再次确认？",
                "type": "textarea",
                "category": "privacy_boundary",
                "claim": "confirm_before_save",
                "sensitivity": "private",
            },
            {
                "name": "sensitive_blur",
                "label": "哪些主题你可能会下意识模糊表达？可只写抽象主题，不写细节。",
                "type": "textarea",
                "category": "clarification_style",
                "claim": "sensitive_topics_may_be_blurred",
                "sensitivity": "private",
            },
            {
                "name": "anti_bubble",
                "label": "希望 agent 如何避免信息茧房或提问模式茧房？",
                "type": "textarea",
                "category": "anti_bubble_rule",
                "claim": "avoid_profile_bubble",
                "sensitivity": "low",
            },
            {
                "name": "always_confirm_sensitive",
                "label": "保存 private/sensitive/intimate 内容前总是先确认",
                "type": "checkbox",
                "summary": "保存 private/sensitive/intimate 内容前总是先确认",
                "category": "privacy_boundary",
                "claim": "always_confirm_sensitive_storage",
                "sensitivity": "low",
            },
        ],
    },
]


def choose_port(preferred: int) -> int:
    for port in [preferred, 48731, 49171, 50317, 53197, 0]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return sock.getsockname()[1]
    raise RuntimeError("No local port available.")


def choice_field(field: dict[str, Any]) -> str:
    name = field["name"]
    options = ['<option value="">不回答</option>']
    options.extend(f"<option>{html.escape(option)}</option>" for option in field["options"])
    options.append(f'<option value="{CUSTOM_CHOICE_VALUE}">用户自定义答案</option>')
    label = html.escape(field["label"])
    custom_name = html.escape(f"{name}_custom")
    custom_id = html.escape(f"{name}_custom_block")
    help_html = f'<p class="field-help">{html.escape(field["help"])}</p>' if field.get("help") else ""
    return f"""
        <div class="choice-block">
          <label>{label}
            <select name="{html.escape(name)}" data-custom-target="{custom_id}">{''.join(options)}</select>
          </label>
          {help_html}
          <div id="{custom_id}" class="custom-answer-block" hidden>
            <label class="custom-label">自定义答案
              <textarea name="{custom_name}" class="custom-answer" placeholder="请输入这个问题的自定义答案" disabled></textarea>
            </label>
          </div>
        </div>
    """


def field_html(field: dict[str, Any]) -> str:
    name = html.escape(field["name"])
    label = html.escape(field["label"])
    placeholder = html.escape(field.get("placeholder", ""))
    if field["type"] == "choice":
        return choice_field(field)
    if field["type"] == "textarea":
        return f'<label>{label}<textarea name="{name}" placeholder="{placeholder}"></textarea></label>'
    if field["type"] == "checkbox":
        return f'<label class="check"><input type="checkbox" name="{name}" value="yes"> <span>{label}</span></label>'
    autocomplete = f' autocomplete="{html.escape(field["autocomplete"])}"' if field.get("autocomplete") else ""
    return f'<label>{label}<input name="{name}" placeholder="{placeholder}"{autocomplete}></label>'


def sections_html() -> str:
    sections = []
    for section in QUESTIONNAIRE_SECTIONS:
        fields = "\n".join(field_html(field) for field in section["fields"])
        note = f'<p class="field-note">{html.escape(section["note"])}</p>' if section.get("note") else ""
        sections.append(
            f"""
    <section class="card">
      <h2>{html.escape(section["title"])}</h2>
      <div class="grid">
        {fields}
      </div>
      {note}
    </section>
            """
        )
    return "\n".join(sections)


def page(user_id: str, result: dict | None = None) -> str:
    result_html = ""
    if result:
        redaction_note = ""
        if result.get("redaction_count"):
            redaction_note = f"<p>已脱敏 {int(result['redaction_count'])} 个疑似 credential 字段；原文未写入 proposal。</p>"
        result_html = f"""
        <section class="result">
          <h2>已生成待确认画像更新</h2>
          <p>这些内容还没有自动写入 active profile。请回到 Codex 查看 proposal，并决定是否应用。</p>
          {redaction_note}
          <pre>{html.escape(json.dumps(result, ensure_ascii=False, indent=2))}</pre>
        </section>
        """
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>User Profile Keeper 初始化问卷</title>
<style>
:root{{color-scheme:light;--bg:#f7f7f4;--panel:#fffefb;--text:#20242a;--muted:#66707a;--line:#d8ded9;--accent:#236b6a;--soft:#edf5f3;--warn:#fff6df}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.55}}
header{{padding:28px clamp(16px,5vw,64px) 18px;background:#fbfbf7;border-bottom:1px solid var(--line)}}
main{{padding:20px clamp(16px,5vw,64px) 48px;max-width:1120px;margin:0 auto}}
h1{{margin:0 0 8px;font-size:28px;line-height:1.15;letter-spacing:0}}
h2{{font-size:18px;margin:0 0 10px;letter-spacing:0}}
p{{margin:0 0 10px;color:var(--muted)}}
.notice,.result{{border:1px solid #b9d3ce;background:var(--soft);border-radius:8px;padding:12px 14px;margin:14px 0}}
.warning{{border:1px solid #e3cf98;background:var(--warn);border-radius:8px;padding:12px 14px;margin:14px 0}}
form{{display:grid;gap:14px}}
section.card{{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:16px;display:grid;gap:12px}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}
label{{display:grid;gap:5px;font-size:13px;color:var(--muted)}}
input,select,textarea{{width:100%;border:1px solid var(--line);border-radius:8px;padding:10px 11px;font:inherit;background:#fff;color:var(--text)}}
textarea{{min-height:86px;resize:vertical}}
.choice-block{{display:grid;gap:8px}}
.custom-label{{color:#52606b}}
.custom-answer-block[hidden]{{display:none}}
.custom-answer{{min-height:62px;background:#fff}}
.field-note{{font-size:12px;color:var(--muted);margin-top:-4px}}
.check{{display:flex;gap:8px;align-items:flex-start;color:var(--text)}}
.check input{{width:auto;margin-top:5px}}
button{{width:max-content;border:1px solid var(--accent);background:var(--accent);color:white;border-radius:8px;padding:10px 14px;font:inherit;cursor:pointer}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px}}
@media(max-width:720px){{.grid{{grid-template-columns:1fr}}button{{width:100%}}}}
</style>
</head>
<body>
<header>
  <h1>User Profile Keeper 初始化问卷</h1>
  <p>用户：<code>{html.escape(user_id)}</code>。问卷只在本地运行，提交后只生成待确认 proposal，不自动写入敏感画像。</p>
</header>
<main>
  <div class="notice">所有问题都可以留空。选择题如果没有合适选项，请选择“用户自定义答案”，再填写出现的文本框。</div>
  <div class="warning">不要填写密码、token、私钥、验证码或任何可直接滥用的 credential。</div>
  {result_html}
  <form method="post" action="/submit">
    {sections_html()}
    <button type="submit">生成待确认画像更新</button>
  </form>
</main>
<script>
document.querySelectorAll("select[data-custom-target]").forEach((select) => {{
  const block = document.getElementById(select.dataset.customTarget);
  const textarea = block ? block.querySelector("textarea") : null;
  const sync = () => {{
    const show = select.value === "{CUSTOM_CHOICE_VALUE}";
    if (block) block.hidden = !show;
    if (textarea) {{
      textarea.disabled = !show;
      if (!show) textarea.value = "";
    }}
  }};
  select.addEventListener("change", sync);
  sync();
}});
</script>
</body>
</html>"""


def secret_reason(value: str) -> str | None:
    for reason, pattern in SECRET_PATTERNS:
        if pattern.search(value):
            return reason
    return None


def text_value(
    form: dict[str, list[str]],
    key: str,
    redactions: list[dict[str, str]] | None = None,
    label: str | None = None,
) -> str:
    value = (form.get(key) or [""])[0].strip()
    if not value:
        return ""
    reason = secret_reason(value)
    if reason:
        if redactions is not None:
            redactions.append(
                {
                    "field": label or key,
                    "reason": reason,
                    "summary": f"初始化问卷字段“{label or key}”包含疑似 credential，原文未保存。",
                }
            )
        return "[REDACTED: potential credential omitted]"
    return value


def choice_value(form: dict[str, list[str]], field: dict[str, Any], redactions: list[dict[str, str]]) -> str:
    key = field["name"]
    label = field["label"]
    selected = text_value(form, key, redactions, f"{label} - 预设选项")
    if selected == CUSTOM_CHOICE_VALUE:
        return text_value(form, f"{key}_custom", redactions, f"{label} - 用户自定义答案")
    return selected


def field_value(form: dict[str, list[str]], field: dict[str, Any], redactions: list[dict[str, str]]) -> str:
    field_type = field["type"]
    if field_type == "choice":
        return choice_value(form, field, redactions)
    if field_type == "checkbox":
        return field["summary"] if text_value(form, field["name"]) == "yes" else ""
    return text_value(form, field["name"], redactions, field["label"])


def add_candidate(candidates: list[dict], *, category: str, claim: str, summary: str, source: str = "self_report", sensitivity: str = "low", confidence: float = 0.9) -> None:
    if not summary:
        return
    candidates.append(
        {
            "category": category,
            "claim": claim,
            "value": {"summary": summary},
            "scope": "global",
            "source_type": source,
            "confidence": confidence,
            "sensitivity": sensitivity,
            "evidence": {"summary": f"初始化问卷填写：{summary}", "context": "local onboarding questionnaire"},
        }
    )


def candidates_from_form(form: dict[str, list[str]]) -> tuple[str | None, list[dict], list[dict[str, str]]]:
    candidates: list[dict] = []
    redactions: list[dict[str, str]] = []
    display_name = text_value(form, "display_name", redactions, "称呼") or None
    for section in QUESTIONNAIRE_SECTIONS:
        for field in section["fields"]:
            if field.get("profile") is False:
                continue
            add_candidate(
                candidates,
                category=field["category"],
                claim=field["claim"],
                summary=field_value(form, field, redactions),
                sensitivity=field.get("sensitivity", "low"),
                confidence=float(field.get("confidence", 0.9)),
            )
    return display_name, candidates, redactions


class Handler(BaseHTTPRequestHandler):
    server_version = "UserProfileKeeper/1.0"

    def do_GET(self) -> None:  # noqa: N802
        self.respond_html(page(self.server.user_id))  # type: ignore[attr-defined]

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/submit":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        form = parse_qs(body, keep_blank_values=True)
        display_name, candidates, redactions = candidates_from_form(form)
        user_id = self.server.user_id  # type: ignore[attr-defined]
        result = {
            "ok": True,
            "user_id": user_id,
            "proposal_id": None,
            "candidate_count": len(candidates),
            "redaction_count": len(redactions),
            "redactions": redactions,
        }
        profile_store.init_user(user_id, display_name)
        if candidates or redactions:
            conn = profile_store.connect(user_id)
            with conn:
                for redaction in redactions:
                    profile_store.insert_redaction(
                        conn,
                        user_id,
                        {
                            "category": "privacy_boundary",
                            "claim": "onboarding_questionnaire_secret_redacted",
                            "value": {"summary": redaction["summary"]},
                            "scope": "user-profile-keeper",
                            "source_type": "self_report",
                            "confidence": 0.9,
                            "sensitivity": "secret",
                            "evidence": {
                                "summary": redaction["summary"],
                                "context": "local onboarding questionnaire",
                                "privacy_tags": ["secret", "redacted"],
                            },
                        },
                        "potential credential omitted from onboarding questionnaire",
                    )
                if not candidates:
                    self.respond_html(page(user_id, result))
                    return
                conflicts: list[str] = []
                for candidate in candidates:
                    normalized = profile_store.normalize_candidate(candidate, "local onboarding questionnaire")
                    conflicts.extend(profile_store.conflicts_for(conn, user_id, normalized))
                proposal_id = profile_store.create_proposal(conn, user_id, candidates, "local onboarding questionnaire", sorted(set(conflicts)))
                result["proposal_id"] = proposal_id
        self.respond_html(page(user_id, result))

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def respond_html(self, body: str) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start local onboarding questionnaire")
    parser.add_argument("--user", default="default")
    parser.add_argument("--port", type=int, default=48731)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    user_id = profile_store.safe_user_id(args.user)
    port = choose_port(args.port)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.user_id = user_id  # type: ignore[attr-defined]
    url = f"http://127.0.0.1:{port}/"
    print(json.dumps({"ok": True, "url": url, "user_id": user_id, "note": "Press Ctrl-C to stop."}, ensure_ascii=False), flush=True)
    if not args.no_open:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
