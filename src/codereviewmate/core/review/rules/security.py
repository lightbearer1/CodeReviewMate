"""Security pattern rules — detect common vulnerabilities."""

from __future__ import annotations

import re

from codereviewmate.core.models.review import IssueCategory, Severity
from codereviewmate.core.review.rules.base import Rule, RuleMatch


def create_security_rules() -> list[Rule]:
    """Create the default set of security rules."""
    return [
        Rule(
            id="no-hardcoded-secrets",
            category=IssueCategory.SECURITY,
            severity=Severity.CRITICAL,
            description="代码中硬编码的密钥/密码/Token",
            pattern=r"(password|passwd|secret|api_key|api_secret|token|auth_token)\s*[:=]\s*['\"][^'\"]+['\"]",
            auto_fixable=False,
            suggestion_template="绝不要在代码中硬编码密钥！使用环境变量或密钥管理服务（如 Vault）",
        ),
        Rule(
            id="no-hardcoded-connection-string",
            category=IssueCategory.SECURITY,
            severity=Severity.CRITICAL,
            description="代码中硬编码的数据库连接字符串",
            pattern=r"(connection_string|conn_str|dsn|database_url)\s*[:=]\s*['\"]\w+://[^'\"]+['\"]",
            auto_fixable=False,
            suggestion_template="数据库连接字符串应通过环境变量注入，禁止硬编码",
        ),
        Rule(
            id="sql-injection-fstring",
            category=IssueCategory.SECURITY,
            severity=Severity.HIGH,
            description="潜在的 SQL 注入：使用 f-string 拼接 SQL 语句",
            pattern=r"(execute|cursor\.execute|executemany)\s*\(\s*f['\"]",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="使用参数化查询代替 f-string 拼接，例如: cursor.execute('SELECT * FROM t WHERE id=%s', (id,))",
        ),
        Rule(
            id="sql-injection-format",
            category=IssueCategory.SECURITY,
            severity=Severity.HIGH,
            description="潜在的 SQL 注入：使用 .format() 拼接 SQL 语句",
            pattern=r"\.execute\s*\(\s*['\"].*\{\}.*['\"]\s*\.\s*format\s*\(",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="使用参数化查询代替字符串格式化拼接",
        ),
        Rule(
            id="shell-injection",
            category=IssueCategory.SECURITY,
            severity=Severity.CRITICAL,
            description="潜在的命令注入：使用 shell=True 执行外部命令",
            pattern=r"shell\s*=\s*True",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="避免使用 shell=True，改用参数列表方式传递命令和参数",
        ),
        Rule(
            id="insecure-deserialization",
            category=IssueCategory.SECURITY,
            severity=Severity.HIGH,
            description="不安全的反序列化：使用 pickle.load()",
            pattern=r"pickle\.(load|loads)\s*\(",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="避免使用 pickle 反序列化不可信数据，改用 JSON 或其他安全格式",
        ),
        Rule(
            id="open-redirect",
            category=IssueCategory.SECURITY,
            severity=Severity.MEDIUM,
            description="潜在的重定向漏洞：使用用户输入构造重定向 URL",
            pattern=r"redirect\s*\(\s*(request\.(args|form|params|GET|POST))",
            auto_fixable=False,
            suggestion_template="对重定向 URL 进行白名单校验，或使用 django.utils.http.url_has_allowed_host_and_scheme",
        ),
        Rule(
            id="debug-mode-enabled",
            category=IssueCategory.SECURITY,
            severity=Severity.HIGH,
            description="调试模式开启（生产环境风险）",
            pattern=r"(DEBUG|debug)\s*=\s*True",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="生产环境中 DEBUG 必须设为 False，建议从环境变量读取",
        ),
        Rule(
            id="eval-usage",
            category=IssueCategory.SECURITY,
            severity=Severity.CRITICAL,
            description="使用 eval() 或 exec() 执行动态代码",
            pattern=r"\b(eval|exec)\s*\(",
            file_patterns=["*.py"],
            auto_fixable=False,
            suggestion_template="禁止使用 eval()/exec()，存在远程代码执行风险。考虑使用 ast.literal_eval() 或重构代码",
        ),
        Rule(
            id="md5-weak-hash",
            category=IssueCategory.SECURITY,
            severity=Severity.MEDIUM,
            description="使用弱哈希算法 MD5/SHA1",
            pattern=r"\b(MD5|SHA1|md5|sha1)\b",
            auto_fixable=False,
            suggestion_template="MD5/SHA1 已被破解，使用 SHA-256 或更强的哈希算法",
            check_fn=_check_weak_hash_context,
        ),
    ]


def _check_weak_hash_context(file_path: str, content: str) -> list[RuleMatch]:
    """Only flag weak hashes used for security purposes (not checksums)."""
    matches: list[RuleMatch] = []
    weak_pattern = re.compile(r"\b(MD5|SHA1|md5|sha1)\b")
    # Ignore if in safe contexts (file checksums, etag, etc.)
    safe_contexts = ["etag", "checksum", "cache", "digest"]

    for i, line in enumerate(content.splitlines(), 1):
        if weak_pattern.search(line):
            line_lower = line.lower()
            if any(ctx in line_lower for ctx in safe_contexts):
                continue
            matches.append(
                RuleMatch(
                    line_number=i,
                    line_content=line.strip(),
                    matched_text=weak_pattern.search(line).group(0),
                    suggestion="使用 SHA-256 或 bcrypt/scrypt/argon2 替代弱哈希算法",
                )
            )
    return matches
