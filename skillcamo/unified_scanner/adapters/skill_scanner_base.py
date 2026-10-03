"""
基于 Skill 的扫描器基础适配器

所有通过 Claude CLI 调用 skill 进行扫描的适配器都应继承此类。
"""

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from abc import abstractmethod
from pathlib import Path
from typing import Any

try:
    from ..models import Severity, ThreatCategory, UnifiedFinding
    from .base import BaseAdapter
except ImportError:
    from models import Severity, ThreatCategory, UnifiedFinding
    from adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class SkillBasedScannerAdapter(BaseAdapter):
    """
    基于 Skill 的扫描器基础适配器

    子类需要实现：
    - get_skill_name(): 返回 skill 名称
    - get_skill_source_path(): 返回 skill 目录路径
    - parse_findings(): 解析扫描结果为 UnifiedFinding 列表
    """

    # 类级别的信号量，所有子类共享
    _claude_cli_semaphore: threading.Semaphore | None = None
    _semaphore_lock = threading.Lock()
    _initialized = False  # 标记是否已初始化

    # 类级别的 API key 轮换池（用于 Claude CLI 子进程）
    _claude_cli_key_pool: "ApiKeyPool | None" = None

    # 重试配置
    MAX_RETRIES = 3  # 最大重试次数
    RETRYABLE_ERRORS = (
        "TimeoutExpired",
        "timeout",
        "ConnectionError",
        "ReadTimeout",
        "HTTPError",
        "APIError",
        "rate limit",
        "temporary failure",
        "error_during_execution",
    )

    def __init__(
        self,
        timeout: int | None = None,
        max_retries: int | None = None,
        model: str | None = None,
        provider_env: dict[str, str] | None = None,
    ):
        """
        初始化扫描器

        Args:
            timeout: CLI 调用超时时间（秒），由统一 config 注入
            max_retries: 最大重试次数，默认使用类级别的 MAX_RETRIES
            model: Claude CLI 模型 ID（如 claude-sonnet-4-6），None 走 Claude CLI 默认
            provider_env: 注入 claude 子进程的 ANTHROPIC_* 环境变量（来自 ccsw
                provider）。非空时该 provider 的 base_url/auth_token/model 生效，
                无需全局 ccsw switch。含明文 token，禁止写入日志/审计。
        """
        super().__init__()
        self.timeout = timeout
        self.max_retries = max_retries if max_retries is not None else self.MAX_RETRIES
        self.model = model
        self.provider_env = provider_env or {}
        self._last_claude_cli_audit: dict[str, Any] | None = None

    # ==================== Claude CLI 并发控制 ====================

    @classmethod
    def set_claude_cli_concurrent_limit(cls, limit: int, force: bool = False) -> None:
        """设置 Claude CLI 并发限制（线程安全，默认只设置一次）

        Args:
            limit: 最大并发数，必须大于 0
            force: 是否强制更新已有信号量（用于配置变更场景）
        """
        if limit <= 0:
            raise ValueError(f"Concurrent limit must be positive, got {limit}")

        with cls._semaphore_lock:
            if not cls._initialized or force:
                cls._claude_cli_semaphore = threading.Semaphore(limit)
                cls._initialized = True
                logger.info(f"Claude CLI concurrent limit set to: {limit} (force={force})")

    @classmethod
    def set_api_key_pool(cls, pool: "ApiKeyPool") -> None:
        """设置 Claude CLI 的 API key 轮换池。

        Args:
            pool: ApiKeyPool 实例，所有 Claude CLI 子进程调用将轮换使用其中的 key。
        """
        cls._claude_cli_key_pool = pool
        logger.info(f"Claude CLI API key pool set: {pool}")

    @classmethod
    def get_claude_cli_semaphore(cls) -> threading.Semaphore:
        """获取 Claude CLI 信号量

        Returns:
            信号量对象，如果未设置则返回默认限制（2）
        """
        if cls._claude_cli_semaphore is None:
            # 使用默认限制（2）
            return threading.Semaphore(2)
        return cls._claude_cli_semaphore

    @classmethod
    def reset_claude_cli_concurrent_limit(cls) -> None:
        """重置 Claude CLI 并发限制（用于测试）"""
        with cls._semaphore_lock:
            cls._claude_cli_semaphore = None
            cls._initialized = False

    # ========== 子类必须实现的方法 ==========

    @abstractmethod
    def get_skill_name(self) -> str:
        """返回 skill 名称（用于安装和调用）"""
        raise NotImplementedError

    @abstractmethod
    def get_skill_source_path(self) -> Path:
        """返回 skill 源文件路径（SKILL.md 所在目录）"""
        raise NotImplementedError

    @abstractmethod
    def parse_findings(self, content: str, skill_path: Path) -> list[dict]:
        """解析 LLM 返回的内容，提取 findings

        Args:
            content: LLM 返回的原始文本
            skill_path: 被扫描的技能路径

        Returns:
            UnifiedFinding 字典列表
        """
        raise NotImplementedError

    # ========== 可选覆盖的方法 ==========

    def get_skill_invocation_name(self) -> str:
        """返回 Claude 侧实际使用的 skill 名称。

        默认从 SKILL.md frontmatter 的 ``name`` 字段读取；读取失败时回退到
        适配器内部的 scanner id。
        """
        import yaml

        source_path = self.get_skill_source_path()
        skill_md_path = source_path / "SKILL.md" if source_path.is_dir() else source_path
        try:
            content = skill_md_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return self.get_skill_name()

        match = re.search(r"(?ms)^---\s*\n(.*?)\n---\s*", content)
        if not match:
            return self.get_skill_name()

        frontmatter_str = match.group(1)

        # Try YAML parsing first for proper handling of complex formats
        try:
            parsed = yaml.safe_load(frontmatter_str)
            if isinstance(parsed, dict) and "name" in parsed:
                skill_name = str(parsed["name"]).strip().strip("\"'")
                if skill_name:
                    return skill_name
        except yaml.YAMLError:
            pass

        # Fallback to regex for malformed YAML
        name_match = re.search(r"(?m)^name:\s*([^\n]+)$", frontmatter_str)
        if not name_match:
            return self.get_skill_name()

        skill_name = name_match.group(1).strip().strip("\"'")
        return skill_name or self.get_skill_name()

    def get_install_path(self) -> Path:
        """返回 skill 安装路径（默认 ~/.claude/skills/{frontmatter name}）"""
        return Path.home() / ".claude" / "skills" / self.get_skill_invocation_name()

    def _read_scanner_protocol(self) -> str:
        """读取扫描器自身 SKILL.md 正文，作为内联审查协议。

        内联协议取代「安装到 ~/.claude/skills 再激活」的旧机制：扫描在
        --disable-slash-commands 全量禁用 skill 的隔离环境下仍能遵循协议，
        且完全不受用户本机已安装 skill/plugin 的干扰。
        """
        source_path = self.get_skill_source_path()
        skill_md_path = source_path / "SKILL.md" if source_path.is_dir() else source_path
        try:
            return skill_md_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _build_isolated_prompt(self, skill_content: str, action_verb: str = "审查") -> str:
        """构建隔离扫描 prompt：内联协议 + 待审查内容，绝不写入目录名/路径。

        被测 skill 的目录名与绝对路径是测试 harness 强加的元数据，会成为污染
        模型判断的标签泄漏；被测 skill 自报的 name 已包含在 skill_content 的
        SKILL.md frontmatter 中，那才是应当保留的合法信号。
        """
        protocol = self._read_scanner_protocol()
        return f"""你是一个安全审查器，请严格遵循以下审查协议{action_verb}下面的目标技能。

无论结论是安全、可疑还是无法判断，你都必须输出一份最终文本报告。
不要只执行内部分析步骤后直接结束，也不要返回空结果。

=== 审查协议 ===
{protocol}

=== 待审查技能内容 ===
{skill_content}"""

    def build_scan_prompt(self, skill_path: Path, skill_content: str) -> str:
        """构建扫描 prompt（默认实现）。

        子类可覆盖以自定义措辞，但都应经由 _build_isolated_prompt 保证不泄漏
        目录名/路径并内联协议。``skill_path`` 仅供子类（如 KG 增强）使用，
        默认实现不将其写入 prompt。
        """
        return self._build_isolated_prompt(skill_content)

    def get_model(self) -> str | None:
        """返回使用的模型；None → Claude CLI 默认模型。"""
        return self.model

    def _effective_model(self) -> str | None:
        """实际传给 claude --model 的模型。

        配了 ccsw provider 时，优先用 provider 自带的模型（ANTHROPIC_MODEL，
        回退 ANTHROPIC_DEFAULT_SONNET_MODEL），从而让 config 里硬编码的
        claude-sonnet-4-6 在非官方端点上被自然忽略，避免 --model 与端点冲突。
        否则回退到显式配置的 self.model。
        """
        if self.provider_env:
            provider_model = (
                self.provider_env.get("ANTHROPIC_MODEL")
                or self.provider_env.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
            )
            if provider_model:
                return provider_model
        return self.model

    def get_max_tokens(self) -> int:
        """返回最大 token 数（可选）"""
        return 8000

    # ========== 通用实现 ==========

    def _check_availability(self) -> bool:
        """检查 Claude CLI 和 skill 是否可用"""
        # 检查 Claude CLI
        if shutil.which("claude") is None:
            print(f"Warning: Claude CLI not found for {self.scanner_name}")
            return False

        # 检查 skill 源文件存在
        skill_path = self.get_skill_source_path()
        if not skill_path.exists():
            print(f"Warning: {self.get_skill_name()} skill not found at {skill_path}")
            return False

        return True

    def scan(self, skill_path: str | Path, **kwargs) -> dict:
        """
        执行扫描

        Args:
            skill_path: 技能目录路径
            timeout: 可选的扫描超时时间（秒），覆盖默认超时配置

        Returns:
            {
                "findings": [...],
                "metadata": {...}
            }
        """
        # 支持从 kwargs 覆盖 timeout 配置
        original_timeout = self.timeout
        if "timeout" in kwargs:
            self.timeout = kwargs.pop("timeout")
        if self.timeout is None:
            raise ValueError(f"Missing timeout configuration for scanner: {self.scanner_name}")

        start_time = time.time()
        skill_path = Path(skill_path)

        if not skill_path.exists():
            self.timeout = original_timeout
            return {
                "findings": [],
                "metadata": {
                    "scanner": self.scanner_name,
                    "error": f"Skill path does not exist: {skill_path}",
                    "error_type": "PathNotFound",
                    "is_safe": None,  # None means unable to determine (technical error)
                },
            }

        try:
            self._last_claude_cli_audit = None
            # 1. 读取目标技能内容（协议已内联进 prompt，无需安装/激活 skill）
            skill_content = self._read_skill_content(skill_path)

            # 2. 构建 prompt
            prompt = self.build_scan_prompt(skill_path, skill_content)

            # 3. 调用 Claude CLI
            response_text = self._invoke_claude_cli(prompt)

            # 4. 解析结果
            findings = self.parse_findings(response_text, skill_path)

            # Calculate is_safe: no CRITICAL or HIGH severity findings
            is_safe = not any(
                f.get("severity") in ("CRITICAL", "HIGH")
                for f in findings
            )

            duration_ms = int((time.time() - start_time) * 1000)
            self.timeout = original_timeout
            return {
                "findings": findings,
                "metadata": {
                    "scanner": self.scanner_name,
                    "duration_ms": duration_ms,
                    "skill_path": str(skill_path),
                    "skill_used": self.get_skill_invocation_name(),
                    "is_safe": is_safe,
                },
                "raw_output_text": response_text,
                "claude_cli_audit": self._last_claude_cli_audit,
            }

        except Exception as e:
            self.timeout = original_timeout
            return {
                "findings": [],
                "metadata": {
                    "scanner": self.scanner_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "is_safe": None,  # None means unable to determine (technical error)
                },
                "raw_output_text": str(e),
                "claude_cli_audit": self._last_claude_cli_audit,
            }

    def _read_skill_content(self, skill_path: Path) -> str:
        """
        读取技能内容

        默认读取 SKILL.md 和主要代码文件
        子类可覆盖以自定义内容读取逻辑

        支持两种 SKILL.md 格式：
        1. 传统格式：内容在 markdown body 中
        2. 新格式：内容在 YAML front matter 字段中（goal, subgoals, skills, interaction_policy 等）
        """
        content_parts = []
        total_chars = 0
        max_chars = 15000

        # 读取 SKILL.md
        skill_md = skill_path / "SKILL.md"
        if skill_md.exists():
            with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                skill_content = f.read()[:10000]
                content_parts.append(f"# SKILL.md\n{skill_content}")
                total_chars += len(skill_content)

                # 检查是否为新格式（YAML front matter 中包含结构化内容）
                yaml_content = self._extract_yaml_frontmatter_content(skill_content)
                if yaml_content:
                    content_parts.append(f"\n# Structured Content (from YAML front matter)\n{yaml_content}")
                    total_chars += len(yaml_content) + 100

        # 读取主要代码文件（如果有剩余空间）
        if total_chars < max_chars - 2000:
            code_extensions = [".py", ".js", ".ts", ".sh", ".bash", ".json"]
            remaining = max_chars - total_chars - 1000
            per_file = min(2000, remaining // 5)

            for ext in code_extensions:
                if total_chars >= max_chars - 1000:
                    break
                files = list(skill_path.rglob(f"*{ext}"))[:5]
                for file_path in files:
                    if file_path.name == "SKILL.md":
                        continue
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            file_content = f.read()[:per_file]
                            rel_path = file_path.relative_to(skill_path)
                            content_parts.append(f"\n# {rel_path}\n{file_content}")
                            total_chars += len(file_content) + len(str(rel_path)) + 50
                    except Exception:
                        pass

        return "\n\n".join(content_parts)

    def _extract_yaml_frontmatter_content(self, content: str) -> str:
        """Extract structured content from YAML front matter fields.

        Returns formatted text from goal, subgoals, skills, interaction_policy
        fields if they exist, empty string otherwise.
        """
        import re
        import yaml

        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return ""

        yaml_content = match.group(1)
        try:
            parsed = yaml.safe_load(yaml_content)
            if not isinstance(parsed, dict):
                return ""

            # Extract structured content fields
            structured_fields = ["goal", "subgoals", "skills", "interaction_policy"]
            parts = []

            for field in structured_fields:
                if field in parsed:
                    value = parsed[field]
                    if isinstance(value, str):
                        parts.append(f"## {field.title()}\n{value}")
                    elif isinstance(value, list):
                        formatted_items = []
                        for item in value:
                            if isinstance(item, dict):
                                # Handle skill objects with name/description
                                name = item.get("name", "")
                                desc = item.get("description", "")
                                if name and desc:
                                    formatted_items.append(f"- {name}: {desc}")
                                elif name:
                                    formatted_items.append(f"- {name}")
                                else:
                                    formatted_items.append(f"- {json.dumps(item)}")
                            else:
                                formatted_items.append(f"- {item}")
                        parts.append(f"## {field.title()}\n" + "\n".join(formatted_items))
                    elif isinstance(value, dict):
                        formatted_lines = []
                        for k, v in value.items():
                            formatted_lines.append(f"- {k}: {v}")
                        parts.append(f"## {field.title()}\n" + "\n".join(formatted_lines))

            return "\n\n".join(parts) if parts else ""

        except yaml.YAMLError:
            return ""

    def _invoke_claude_cli(self, prompt: str) -> str:
        """
        调用 Claude CLI（带并发控制）

        使用临时文件传递 prompt 以避免命令行过长
        """
        # 获取信号量，控制并发
        semaphore = self.get_claude_cli_semaphore()

        with semaphore:  # 获取信号量，执行完成后自动释放
            return self._invoke_claude_cli_impl(prompt)

    def _extract_agent_output_from_streams(self, stdout: str, stderr: str) -> tuple[str, str]:
        """Build final agent output using SkillJect-style stdout/stderr semantics.

        Returns:
            (final_agent_output, primary_extracted_output)
        """
        primary_output = self._extract_content_from_cli_output(stdout)

        # SkillJect semantics: if structured extraction is empty, keep raw stdout as agent output.
        stdout_output = primary_output if primary_output.strip() else stdout

        if stderr.strip():
            if stdout_output.strip():
                final_output = f"{stdout_output}\n[STDERR]\n{stderr}"
            else:
                final_output = stderr
        else:
            final_output = stdout_output

        return final_output, primary_output

    def _is_retryable_error(self, error: Exception) -> bool:
        """
        判断错误是否可重试

        可重试的错误包括：
        - 超时错误
        - 网络连接错误
        - API 限流
        - 临时性失败
        """
        error_msg = str(error).lower()
        error_type = type(error).__name__

        # 检查错误类型
        if error_type in self.RETRYABLE_ERRORS:
            return True

        # 检查错误消息中的关键字
        for keyword in self.RETRYABLE_ERRORS:
            if keyword.lower() in error_msg:
                return True

        return False

    def _invoke_claude_cli_impl(self, prompt: str) -> str:
        """
        调用 Claude CLI 的实际实现（带重试机制）

        使用临时文件传递 prompt 以避免命令行过长
        对可重试的错误进行最多 max_retries 次重试
        """
        prompt_file = None
        last_error = None
        attempts: list[dict[str, Any]] = []

        # 重试循环
        for attempt in range(self.max_retries + 1):
            try:
                # 创建临时文件
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write(prompt)
                    prompt_file = f.name

                # 构建命令（完全自包含隔离）：
                # --bare                 关闭 hooks/LSP/plugin sync/auto-memory/CLAUDE.md 自动发现
                # --disable-slash-commands  禁用全部 skill（消除用户本机已装 skill 的干扰）
                # --strict-mcp-config + 空 --mcp-config  忽略所有用户 MCP server
                # --setting-sources ""   不加载任何 settings 源
                # 扫描器协议已内联进 prompt，故无需依赖 ~/.claude 中安装的 skill。
                # 注意：--bare 下鉴权严格走 ANTHROPIC_API_KEY（不读 OAuth/keychain）。
                # 沙盒账号登录模式（SCANNER_CLAUDE_NO_BARE=1）下去掉 --bare 以读取 OAuth，
                # 用等价的隔离 flag 组合（--setting-sources ""/--disable-slash-commands/
                # --strict-mcp-config 空 mcp）替代 --bare 的隔离作用；容器内无用户 CLAUDE.md，
                # 上下文污染面已被容器隔离消除。
                cmd = ["claude", "--print", "--no-chrome"]
                if not os.environ.get("SCANNER_CLAUDE_NO_BARE"):
                    cmd.append("--bare")
                cmd += [
                    "--disable-slash-commands",
                    "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                    "--setting-sources", "",
                    "--output-format", "json",
                    "--permission-mode", "bypassPermissions",
                ]

                # 让模型能读取扫描器自身的辅助文件（协议正文可能引用 src/ 脚本等）
                source_path = self.get_skill_source_path()
                if source_path.exists():
                    cmd.extend(["--add-dir", str(source_path)])

                # 添加模型参数（如果指定）；配了 ccsw provider 时用 provider 的模型
                model = self._effective_model()
                if model:
                    cmd.extend(["--model", model])

                # 添加 prompt 文件
                # "--" 必须先于 prompt：--add-dir/--mcp-config 等是 variadic 选项，
                # 若 prompt 紧跟其后（例如未指定 --model 时），会被贪婪吞成又一个目录，
                # CLI 随即报 "Input must be provided either through stdin or as a
                # prompt argument when using --print"。
                cmd.append("--")
                cmd.append(f"@{prompt_file}")

                # 计算当前尝试的超时时间（指数退避：每次增加 50%）
                current_timeout = self.timeout * (1 + 0.5 * attempt)

                # 解析 API key：优先使用轮换池，回退到环境变量
                api_key = (
                    type(self)._claude_cli_key_pool.get_next_key()
                    if type(self)._claude_cli_key_pool is not None
                    else os.environ.get("ANTHROPIC_API_KEY", "")
                )

                # 组装子进程环境：先叠加 ccsw provider 的 ANTHROPIC_* env（含
                # BASE_URL/AUTH_TOKEN/MODEL）。provider 自带 AUTH_TOKEN 时，移除
                # ANTHROPIC_API_KEY 以免空/官方 key 抢占该 provider 的鉴权；
                # 没有 provider 时维持原行为（注入 ANTHROPIC_API_KEY）。
                cli_env = {**os.environ, **self.provider_env}
                if os.environ.get("SCANNER_CLAUDE_NO_BARE"):
                    # 账号登录模式：走 ~/.claude OAuth，绝不注入（空）API key 抢占鉴权
                    cli_env.pop("ANTHROPIC_API_KEY", None)
                    cli_env.pop("ANTHROPIC_AUTH_TOKEN", None)
                elif self.provider_env.get("ANTHROPIC_AUTH_TOKEN"):
                    cli_env.pop("ANTHROPIC_API_KEY", None)
                else:
                    cli_env["ANTHROPIC_API_KEY"] = api_key

                # 执行命令
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=current_timeout,
                    env=cli_env,
                    stdin=subprocess.DEVNULL,
                )

                command_snapshot = [*cmd[:-1], "@<prompt-file>"] if cmd else []

                # 记录调试信息
                if attempt > 0:
                    logger.info(f"Claude CLI retry attempt {attempt} succeeded")
                logger.debug(f"Claude CLI command: {' '.join(cmd)}")
                logger.debug(f"Claude CLI return code: {result.returncode}")
                if result.stdout:
                    logger.debug(f"Claude CLI stdout (first 500 chars): {result.stdout[:500]}")
                if result.stderr:
                    logger.debug(f"Claude CLI stderr (first 500 chars): {result.stderr[:500]}")

                if result.returncode != 0:
                    attempts.append({
                        "attempt": attempt + 1,
                        "timeout_seconds": current_timeout,
                        "command": command_snapshot,
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "extracted_output": "",
                    })
                    self._last_claude_cli_audit = {
                        "command_template": command_snapshot,
                        "attempts": attempts,
                    }
                    # 组合 stderr 和 stdout 获取完整错误信息
                    error_parts = []
                    if result.stderr:
                        error_parts.append(f"stderr: {result.stderr}")
                    if result.stdout:
                        error_parts.append(f"stdout: {result.stdout}")
                    error_msg = f"Claude CLI failed (exit code {result.returncode})"
                    if error_parts:
                        error_msg += ": " + "; ".join(error_parts)
                    else:
                        error_msg += " (no error output captured)"
                    raise RuntimeError(error_msg)

                # 提取并返回内容（SkillJect-style: stdout primary, stderr appended）
                final_output, primary_output = self._extract_agent_output_from_streams(
                    result.stdout,
                    result.stderr,
                )
                attempts.append({
                    "attempt": attempt + 1,
                    "timeout_seconds": current_timeout,
                    "command": command_snapshot,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "primary_extracted_output": primary_output,
                    "final_agent_output": final_output,
                })
                self._last_claude_cli_audit = {
                    "command_template": command_snapshot,
                    "attempts": attempts,
                }
                return final_output

            except subprocess.TimeoutExpired as e:
                last_error = e
                command_snapshot = [*cmd[:-1], "@<prompt-file>"] if "cmd" in locals() and cmd else []
                attempts.append({
                    "attempt": attempt + 1,
                    "timeout_seconds": current_timeout if "current_timeout" in locals() else None,
                    "command": command_snapshot,
                    "returncode": None,
                    "stdout": e.stdout.decode(errors="ignore") if isinstance(e.stdout, bytes) else e.stdout,
                    "stderr": e.stderr.decode(errors="ignore") if isinstance(e.stderr, bytes) else e.stderr,
                    "primary_extracted_output": "",
                    "final_agent_output": "",
                    "error_type": type(e).__name__,
                    "error": str(e),
                })
                self._last_claude_cli_audit = {
                    "command_template": command_snapshot,
                    "attempts": attempts,
                }
                if attempt < self.max_retries and self._is_retryable_error(e):
                    wait_time = 2 ** attempt  # 指数退避：1s, 2s, 4s
                    logger.warning(
                        f"Claude CLI timeout ({int(current_timeout)}s), "
                        f"retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Claude CLI timeout after {self.max_retries} retries")
                    raise

            except Exception as e:
                last_error = e
                command_snapshot = [*cmd[:-1], "@<prompt-file>"] if "cmd" in locals() and cmd else []
                attempts.append({
                    "attempt": attempt + 1,
                    "timeout_seconds": current_timeout if "current_timeout" in locals() else None,
                    "command": command_snapshot,
                    "returncode": result.returncode if "result" in locals() and hasattr(result, "returncode") else None,
                    "stdout": result.stdout if "result" in locals() and hasattr(result, "stdout") else None,
                    "stderr": result.stderr if "result" in locals() and hasattr(result, "stderr") else None,
                    "primary_extracted_output": "",
                    "final_agent_output": "",
                    "error_type": type(e).__name__,
                    "error": str(e),
                })
                self._last_claude_cli_audit = {
                    "command_template": command_snapshot,
                    "attempts": attempts,
                }
                # 检查是否可重试
                if attempt < self.max_retries and self._is_retryable_error(e):
                    wait_time = 2 ** attempt  # 指数退避：1s, 2s, 4s
                    logger.warning(
                        f"Claude CLI error: {type(e).__name__}, "
                        f"retrying in {wait_time}s... (attempt {attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    # 不可重试或重试次数用尽
                    raise

            finally:
                # 清理临时文件
                if prompt_file:
                    try:
                        os.unlink(prompt_file)
                        prompt_file = None
                    except OSError:
                        pass

        # 所有重试都失败
        raise RuntimeError(f"Claude CLI failed after {self.max_retries} retries: {last_error}")

    def _extract_content_from_cli_output(self, cli_output: str) -> str:
        """
        从 CLI JSON 输出中提取实际的 LLM 响应内容

        CLI 返回格式：
        {
          "result": "实际的 LLM 输出文本（可能包含 Markdown 和 JSON）",
          ...
        }

        也会检测应用级错误（返回码为 0 但 is_error=true 或 subtype 包含 error），
        此时抛出 RuntimeError 触发重试机制。
        """
        try:
            data = json.loads(cli_output)

            # 检测 Claude CLI 应用级错误（进程返回码为 0 但输出包含错误标记）
            if data.get("is_error") is True or "error" in str(data.get("subtype", "")).lower():
                error_subtype = data.get("subtype", "unknown")
                stop_reason = data.get("stop_reason", "unknown")
                # 尝试从 result 字段获取更多错误详情
                error_detail = ""
                if isinstance(data.get("result"), str):
                    error_detail = f": {data['result'][:200]}"
                elif isinstance(data.get("result"), dict):
                    error_detail = f": {json.dumps(data['result'])[:200]}"
                raise RuntimeError(
                    f"Claude CLI error_during_execution "
                    f"(subtype={error_subtype}, stop_reason={stop_reason})"
                    f"{error_detail}"
                )

            if "result" in data:
                result = data["result"]
                # result 可能是字符串或对象
                if isinstance(result, str):
                    return result
                elif isinstance(result, dict):
                    # 尝试获取 content 或 text 字段
                    content = result.get("content") or result.get("text")
                    if content:
                        return content
                    # 如果都没有，返回整个 result 的字符串形式
                    return json.dumps(result)

            # 如果没有 result 字段，返回原始输出
            return cli_output

        except json.JSONDecodeError:
            # JSON 解析失败，返回原始输出
            return cli_output

    def _create_finding(
        self,
        title: str,
        description: str,
        severity: Severity,
        category: ThreatCategory | str,
        file_path: str | None = None,
        line_number: int | None = None,
        snippet: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """创建 UnifiedFinding 的便捷方法"""
        return UnifiedFinding(
            id=f"{self.scanner_name}-{uuid.uuid4().hex[:8]}",
            source_scanner=self.scanner_name,
            severity=severity,
            category=category,
            title=title,
            description=description,
            file_path=str(file_path) if file_path else None,
            line_number=line_number,
            snippet=snippet,
            metadata=metadata or {},
        ).to_dict()

    def _ensure_dict(self, parsed: Any) -> dict:
        """
        确保 JSON 解析结果总是返回 dict

        如果解析结果是 list，将其包装为 {"items": list}
        如果是其他类型或空，返回空 dict
        """
        if isinstance(parsed, dict):
            return parsed
        elif isinstance(parsed, list) and parsed:
            # LLM 返回了数组格式，包装成对象
            return {"items": parsed}
        return {}

    # ── Short-response normalization ──────────────────────────────────
    # Some LLM providers (notably Bedrock backends) return a terse JSON
    # like ``{"decision": "benign", "confidence": 100}`` instead of the
    # full schema expected by adapter parsers (findings[], risk_level,
    # verdict, red_flags, etc.).  The mapping below converts these short
    # forms into a canonical dict that the existing ``_parse_json_*``
    # family can consume without special-casing every adapter.

    _DECISION_TO_RISK_LEVEL: dict[str, str] = {
        "benign": "LOW",
        "safe": "LOW",
        "low": "LOW",
        "low_risk": "LOW",
        "ok": "LOW",
        "pass": "LOW",
        "clean": "LOW",
        "suspicious": "MEDIUM",
        "medium": "MEDIUM",
        "caution": "MEDIUM",
        "warning": "MEDIUM",
        "risky": "HIGH",
        "high": "HIGH",
        "high_risk": "HIGH",
        "dangerous": "HIGH",
        "malicious": "CRITICAL",
        "critical": "CRITICAL",
        "harmful": "CRITICAL",
        "reject": "CRITICAL",
        "blocked": "CRITICAL",
    }

    _DECISION_TO_VERDICT: dict[str, str] = {
        "benign": "SAFE",
        "safe": "SAFE",
        "low": "SAFE",
        "ok": "SAFE",
        "pass": "SAFE",
        "clean": "SAFE",
        "suspicious": "CAUTION",
        "medium": "CAUTION",
        "caution": "CAUTION",
        "warning": "CAUTION",
        "risky": "DO_NOT_INSTALL",
        "high": "DO_NOT_INSTALL",
        "high_risk": "DO_NOT_INSTALL",
        "dangerous": "DO_NOT_INSTALL",
        "malicious": "DO_NOT_INSTALL",
        "critical": "DO_NOT_INSTALL",
        "harmful": "DO_NOT_INSTALL",
        "reject": "DO_NOT_INSTALL",
        "blocked": "DO_NOT_INSTALL",
    }

    def _is_short_llm_response(self, data: dict) -> bool:
        """Detect short LLM responses that lack the expected schema fields.

        A "short response" has a ``decision`` key but none of the standard
        output keys (``risk_level``, ``verdict``, ``findings``,
        ``red_flags``, ``analysis``).
        """
        if not isinstance(data, dict):
            return False
        has_decision = "decision" in data
        has_standard = any(
            k in data
            for k in ("risk_level", "verdict", "findings", "red_flags", "analysis", "summary")
        )
        return has_decision and not has_standard

    def _normalize_short_llm_response(self, data: dict) -> dict:
        """Expand a short ``{"decision": …, "confidence": …}`` response.

        Returns a new dict with ``risk_level``, ``verdict``, ``confidence``
        and a synthetic ``summary`` field so downstream parsers produce at
        least one finding.
        """
        decision = str(data.get("decision", "")).strip().lower()

        # Map confidence: may be 0-100 (int) or 0.0-1.0 (float)
        raw_conf = data.get("confidence", 0)
        if isinstance(raw_conf, (int, float)):
            confidence = float(raw_conf)
            if confidence > 1.0:
                confidence = confidence / 100.0
        else:
            try:
                confidence = float(raw_conf)
            except (TypeError, ValueError):
                confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        risk_level = self._DECISION_TO_RISK_LEVEL.get(decision, "MEDIUM")
        verdict = self._DECISION_TO_VERDICT.get(decision, "CAUTION")

        # Build a summary string from whatever extra keys the provider sent
        extra_parts = []
        for key in ("reason", "explanation", "summary", "description", "note"):
            if key in data and data[key]:
                extra_parts.append(str(data[key]))
        summary = " ".join(extra_parts) if extra_parts else f"Decision: {data.get('decision', 'unknown')}"

        normalized = {
            "risk_level": risk_level,
            "verdict": verdict,
            "confidence": confidence,
            "summary": summary,
        }

        # Preserve any keys that might be useful downstream
        for key, value in data.items():
            if key not in normalized and key not in ("decision",):
                normalized[key] = value

        return normalized

    def _strip_json_fences(self, content: str) -> tuple[dict | None, str]:
        """Strip markdown fences from Claude output and parse JSON if present.

        This is the canonical entry point for adapters that need to parse
        structured JSON from Claude's response.  It handles:
        1. `````json ... ``` `` fenced blocks (last one wins)
        2. Bare ``````` ... ``` `` fenced blocks (last one wins)
        3. Raw JSON objects/arrays in the text

        Short responses like ``{"decision": "benign", "confidence": 100}``
        are automatically normalized into the expected schema before return.

        Returns:
            (parsed_dict, stripped_text):
            - *parsed_dict*: the parsed JSON as a dict (or None if no JSON found)
            - *stripped_text*: the content with fences removed
        """
        text = content.strip()

        # Try the last ```````json ... ``````` block first
        last_json_fence = text.rfind("```json")
        if last_json_fence >= 0:
            fence_end = text.find("```", last_json_fence + 7)
            if fence_end < 0:
                fence_end = len(text)
            inner = text[last_json_fence + 7 : fence_end].strip()
            try:
                parsed = self._ensure_dict(json.loads(inner))
                if self._is_short_llm_response(parsed):
                    parsed = self._normalize_short_llm_response(parsed)
                return parsed, inner
            except json.JSONDecodeError:
                pass

        # Try the last ``````` ... ``````` block (non-json tagged)
        last_fence = text.rfind("```")
        if last_fence >= 0 and last_fence != last_json_fence:
            # Find the matching closing fence
            search_start = last_fence + 3
            # Skip optional language tag on same line
            newline_pos = text.find("\n", search_start)
            if newline_pos >= 0:
                inner = text[newline_pos + 1:]
                fence_end = inner.rfind("```")
                if fence_end >= 0:
                    inner = inner[:fence_end].strip()
                try:
                    parsed = self._ensure_dict(json.loads(inner))
                    if self._is_short_llm_response(parsed):
                        parsed = self._normalize_short_llm_response(parsed)
                    return parsed, inner
                except json.JSONDecodeError:
                    pass

        # Try direct JSON parse (already clean)
        try:
            parsed = self._ensure_dict(json.loads(text))
            if self._is_short_llm_response(parsed):
                parsed = self._normalize_short_llm_response(parsed)
            return parsed, text
        except json.JSONDecodeError:
            pass

        # Fallback: use _extract_json_from_content for deeper heuristics
        extracted = self._extract_json_from_content(text)
        if extracted and self._is_short_llm_response(extracted):
            extracted = self._normalize_short_llm_response(extracted)
        return (extracted if extracted else None), text

    def _extract_json_from_content(self, content: str) -> dict:
        """
        从 LLM 返回的内容中提取 JSON 对象

        处理 JSON 前后的 Markdown 代码块标记，以及嵌套在 Markdown 中的 JSON
        始终返回 dict 类型，如果 LLM 返回数组则包装为 {"items": [...]}
        """
        # 首先尝试直接解析
        try:
            return self._ensure_dict(json.loads(content))
        except json.JSONDecodeError:
            pass

        # 查找 JSON 代码块
        json_start = content.rfind('```json')
        if json_start == -1:
            json_start = content.rfind('```')

        if json_start >= 0:
            # 找到代码块结束位置
            json_end = content.find('```', json_start + 7)
            if json_end == -1:
                json_end = len(content)

            json_str = content[json_start + 7:json_end].strip()
            try:
                return self._ensure_dict(json.loads(json_str))
            except json.JSONDecodeError:
                pass

        # 查找最后一个 JSON 对象（从 { 到 }）
        # 从 risk_level 或 red_flags 等关键字开始查找
        for keyword in ['"risk_level"', '"red_flags"', '"findings"', '"verdict"']:
            keyword_pos = content.rfind(keyword)
            if keyword_pos >= 0:
                # 从关键字往回扫描，找到最外层匹配的 {
                depth = 0
                json_start = -1
                for i in range(keyword_pos - 1, -1, -1):
                    if content[i] == '}':
                        depth += 1
                    elif content[i] == '{':
                        if depth == 0:
                            json_start = i
                            break
                        depth -= 1

                if json_start >= 0:
                    # 从 json_start 正向计数，找到匹配的 }
                    brace_count = 0
                    json_end = json_start
                    for i in range(json_start, len(content)):
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break

                    if json_end > json_start:
                        json_str = content[json_start:json_end]
                        try:
                            return self._ensure_dict(json.loads(json_str))
                        except json.JSONDecodeError:
                            pass

        # 策略 3: 从第一个 { 到最后一个 } 尝试提取（兜底）
        first_brace = content.find('{')
        last_brace = content.rfind('}')
        if first_brace >= 0 and last_brace > first_brace:
            json_str = content[first_brace:last_brace + 1]
            try:
                return self._ensure_dict(json.loads(json_str))
            except json.JSONDecodeError:
                pass

        # 策略 4: 尝试修复截断的 JSON（补全闭合括号）
        if first_brace >= 0:
            json_str = content[first_brace:]
            for suffix in ['}', ']}', '"}]}', '"]}', '"}]}', '\n}']:
                try:
                    return self._ensure_dict(json.loads(json_str + suffix))
                except json.JSONDecodeError:
                    continue

        return {}

    def _parse_text_severity(self, line: str) -> Severity:
        """
        从文本中解析严重性级别（支持英文和中文）

        支持的格式：
        - 英文: CRITICAL, Critical, critical, HIGH, High, high, MEDIUM, Medium, medium, LOW, Low, low
        - 中文: 严重, 高, 中, 低
        - 混合: Severity: CRITICAL, (严重性：CRITICAL), 【Critical】
        """
        line_lower = line.lower()

        # 检测 CRITICAL 级别
        critical_keywords = [
            'critical', 'crit',
            '严重', '严重性',
        ]
        if any(keyword in line_lower for keyword in critical_keywords):
            return Severity.CRITICAL

        # 检测 HIGH 级别
        high_keywords = [
            'high',
            '高',
        ]
        if any(keyword in line_lower for keyword in high_keywords):
            return Severity.HIGH

        # 检测 LOW 级别
        low_keywords = [
            'low',
            '低',
        ]
        if any(keyword in line_lower for keyword in low_keywords):
            return Severity.LOW

        # 默认返回 MEDIUM
        return Severity.MEDIUM

    def _parse_emoji_severity(self, line: str) -> Severity:
        """
        从 emoji 中解析严重性级别

        映射规则:
        - ⛔ → CRITICAL
        - 🔴 → HIGH
        - 🟡 → MEDIUM
        - 🟢 → LOW
        """
        emoji_map = {
            "⛔": Severity.CRITICAL,
            "🔴": Severity.HIGH,
            "🟡": Severity.MEDIUM,
            "🟢": Severity.LOW,
        }
        for emoji, severity in emoji_map.items():
            if emoji in line:
                return severity
        return Severity.MEDIUM

    def _parse_markdown_red_flags(self, content: str) -> list[dict]:
        """
        从 Markdown 格式的报告中提取 red flags

        适用于返回 Markdown 格式报告的扫描器（如 slowmist）

        严重性检测顺序：
        1. 文本形式 (CRITICAL/High/Low, 严重/高/低)
        2. Emoji 形式 (⛔🔴🟡🟢)
        3. 默认 MEDIUM
        """
        findings = []

        # 按行分割
        lines = content.split('\n')
        in_red_flags = False
        red_flag_lines = []

        for line in lines:
            if 'RED FLAGS' in line or 'RED FLAGS' in line.upper():
                in_red_flags = True
                continue
            if in_red_flags:
                # 检查是否到了下一个 section
                if line.startswith('═') or 'RISK:' in line or 'VERDICT:' in line or line.startswith('│'):
                    break
                # 收集 red flag 行
                if '•' in line or '-' in line or '*' in line:
                    red_flag_lines.append(line)

        # 解析每个 red flag
        for flag_line in red_flag_lines:
            # 移除 • 或 - 前缀
            flag_line = flag_line.lstrip('•-*').strip()
            lowered = flag_line.lower()
            if (
                lowered.startswith("none of the explicit")
                or lowered.startswith("none of the")
                or lowered.startswith("caution items")
                or "not found in the reviewed files" in lowered
            ):
                continue

            # 1. 首先检测文本形式的严重性
            severity = self._parse_text_severity(flag_line)

            # 2. 如果文本检测返回默认值 MEDIUM，再尝试 emoji 检测
            # (因为 emoji 可能更准确)
            emoji_severity = self._parse_emoji_severity(flag_line)
            if emoji_severity != Severity.MEDIUM:
                severity = emoji_severity

            # 清理描述（移除 emoji 和严重性标记）
            description = flag_line
            for emoji in ["🔴", "🟡", "🟢", "⛔"]:
                description = description.replace(emoji, "")
            # 移除常见的严重性标记
            description = re.sub(r'\(?\s*严重性\s*[:：]\s*(CRITICAL|HIGH|MEDIUM|LOW|严重|高|中|低)\s*\)?', '', description, flags=re.IGNORECASE)
            description = re.sub(r'\(?\s*Severity\s*[:：]\s*(CRITICAL|HIGH|MEDIUM|LOW)\s*\)?', '', description, flags=re.IGNORECASE)
            description = re.sub(r'\(?\s*【\[]?.*?(critical|high|medium|low).*?】\]?\)?', '', description, flags=re.IGNORECASE)
            description = re.sub(r'\([^)]*\)', '', description).strip()

            if description:
                findings.append({
                    "title": "Red Flag Detected",
                    "description": description,
                    "severity": severity,
                })

        return findings

    def _infer_report_severity(self, text: str) -> Severity:
        """Infer severity from mixed Chinese/English report prose."""
        lowered = text.lower()

        critical_markers = [
            "critical",
            "extreme",
            "reject",
            "不建议安装",
            "拒绝安装",
            "高危",
            "严重",
        ]
        if any(marker in lowered for marker in critical_markers):
            return Severity.CRITICAL

        high_markers = [
            "high-risk",
            "high risk",
            "风险等级：high",
            "risk level: high",
            "数据外泄",
            "data exfiltration",
            "泄密",
            "command injection",
            "命令注入",
            "exfiltration",
            "high",
        ]
        if any(marker in lowered for marker in high_markers):
            return Severity.HIGH

        medium_markers = [
            "medium",
            "中风险",
            "隐私",
            "privacy",
            "network",
            "外部资源",
            "install with caution",
            "caution",
        ]
        if any(marker in lowered for marker in medium_markers):
            return Severity.MEDIUM

        low_markers = ["low", "低风险", "safe"]
        if any(marker in lowered for marker in low_markers):
            return Severity.LOW

        return Severity.MEDIUM

    def _extract_first_location(self, text: str) -> tuple[str | None, int | None]:
        """Extract a file path and first line number from free-form text."""
        match = re.search(r'(?:file_path:)?((?:/|\w:)[^\s()]+?):(\d+)(?:-\d+)?', text)
        if not match:
            return None, None
        return match.group(1), int(match.group(2))
