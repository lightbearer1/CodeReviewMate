"""Knowledge extractor — converts review issues into structured knowledge nodes."""

from __future__ import annotations

import json
import logging
from typing import Optional

from jinja2 import Environment, PackageLoader

from codereviewmate.core.llm.base import LLMProvider
from codereviewmate.core.models.knowledge import (
    EdgeType,
    KnowledgeEdge,
    KnowledgeExtraction,
    KnowledgeNode,
    NodeType,
)
from codereviewmate.core.models.review import Issue, ReviewReport

logger = logging.getLogger(__name__)

# Map rule IDs to pre-defined knowledge patterns
RULE_KNOWLEDGE_MAP: dict[str, dict] = {
    "no-hardcoded-secrets": {
        "label": "Never hardcode secrets in source code",
        "type": NodeType.ANTI_PATTERN,
        "description": "Secrets (passwords, API keys, tokens) must be stored in environment variables or secret managers, never in source code.",
        "tags": ["security", "secrets", "configuration"],
    },
    "no-debug-print": {
        "label": "Use logging instead of print()",
        "type": NodeType.STANDARD,
        "description": "Debug output should use the logging module with appropriate levels instead of print() statements.",
        "tags": ["logging", "debug", "python"],
    },
    "no-console-log": {
        "label": "Use logging instead of console.log()",
        "type": NodeType.STANDARD,
        "description": "Client-side debug output should use a proper logging utility instead of console.log().",
        "tags": ["logging", "debug", "javascript"],
    },
    "sql-injection-fstring": {
        "label": "Parameterize SQL queries — never use f-strings",
        "type": NodeType.ANTI_PATTERN,
        "description": "Building SQL queries with f-strings or string formatting opens the door to SQL injection. Always use parameterized queries.",
        "tags": ["security", "sql", "injection"],
    },
    "sql-injection-format": {
        "label": "Parameterize SQL queries — never use .format()",
        "type": NodeType.ANTI_PATTERN,
        "description": "Building SQL queries with string formatting opens the door to SQL injection. Always use parameterized queries.",
        "tags": ["security", "sql", "injection"],
    },
    "eval-usage": {
        "label": "Avoid eval() — use safe alternatives",
        "type": NodeType.ANTI_PATTERN,
        "description": "eval() executes arbitrary code and is a major security risk. Use json.loads(), ast.literal_eval(), or custom parsers instead.",
        "tags": ["security", "python", "code-execution"],
    },
    "shell-injection": {
        "label": "Avoid shell=True in subprocess calls",
        "type": NodeType.ANTI_PATTERN,
        "description": "Using shell=True with user-provided input enables command injection. Pass arguments as lists and avoid the shell.",
        "tags": ["security", "python", "command-injection"],
    },
    "bare-except": {
        "label": "Catch specific exceptions, not bare except",
        "type": NodeType.ANTI_PATTERN,
        "description": "Bare except clauses catch system exits and keyboard interrupts. Always catch specific exception types.",
        "tags": ["error-handling", "python", "bug-pattern"],
    },
    "mutable-default-arg": {
        "label": "Avoid mutable default arguments",
        "type": NodeType.ANTI_PATTERN,
        "description": "Using mutable objects as default argument values in Python creates shared state across calls. Use None as default and initialize inside the function.",
        "tags": ["python", "bug-pattern", "functions"],
    },
    "equality-none": {
        "label": "Use 'is None' instead of '== None'",
        "type": NodeType.STANDARD,
        "description": "None is a singleton in Python. Use 'is None' / 'is not None' for identity comparison instead of equality operators.",
        "tags": ["python", "style", "best-practice"],
    },
    "float-equality": {
        "label": "Avoid direct float equality comparison",
        "type": NodeType.ANTI_PATTERN,
        "description": "Floating-point arithmetic introduces rounding errors. Use math.isclose() or compare with a tolerance threshold.",
        "tags": ["python", "bug-pattern", "numerical"],
    },
    "no-trailing-whitespace": {
        "label": "Remove trailing whitespace",
        "type": NodeType.STANDARD,
        "description": "Trailing whitespace adds noise to diffs and should be stripped. Configure your editor to auto-trim on save.",
        "tags": ["style", "editor-config"],
    },
    "md5-weak-hash": {
        "label": "Use strong cryptographic hashes",
        "type": NodeType.STANDARD,
        "description": "MD5 and SHA1 are cryptographically broken. Use SHA-256 or stronger from hashlib for security-sensitive hashing.",
        "tags": ["security", "crypto", "hashing"],
    },
    "insecure-deserialization": {
        "label": "Avoid pickle for untrusted data",
        "type": NodeType.ANTI_PATTERN,
        "description": "pickle.load() can execute arbitrary code. Never unpickle data from untrusted sources. Use JSON or other safe formats.",
        "tags": ["security", "python", "deserialization"],
    },
    "open-redirect": {
        "label": "Validate redirect URLs",
        "type": NodeType.STANDARD,
        "description": "Open redirects enable phishing attacks. Always validate that redirect URLs are within allowed domains.",
        "tags": ["security", "web", "redirect"],
    },
    "debug-mode-enabled": {
        "label": "Disable debug mode in production",
        "type": NodeType.ANTI_PATTERN,
        "description": "Debug mode exposes stack traces and internal state. Always disable debug mode in production environments.",
        "tags": ["security", "configuration", "production"],
    },
    "no-hardcoded-connection-string": {
        "label": "Never hardcode connection strings",
        "type": NodeType.ANTI_PATTERN,
        "description": "Database connection strings contain credentials and should come from environment variables or secure configuration.",
        "tags": ["security", "database", "configuration"],
    },
    "assignment-in-condition": {
        "label": "Avoid assignment in condition expressions",
        "type": NodeType.ANTI_PATTERN,
        "description": "Assignment inside if/while conditions is error-prone and hard to read. Separate assignment from the condition check.",
        "tags": ["bug-pattern", "readability"],
    },
    "class-naming-convention": {
        "label": "Use PascalCase for class names",
        "type": NodeType.STANDARD,
        "description": "Python class names should follow PEP 8: PascalCase (e.g., DataProcessor, UserManager).",
        "tags": ["naming", "python", "style", "pep8"],
    },
    "function-naming-convention": {
        "label": "Use snake_case for function names",
        "type": NodeType.STANDARD,
        "description": "Python function names should follow PEP 8: snake_case (e.g., process_data, get_user_by_id).",
        "tags": ["naming", "python", "style", "pep8"],
    },
    "no-todo-without-ticket": {
        "label": "Always link TODOs to tracking tickets",
        "type": NodeType.STANDARD,
        "description": "Bare TODO comments rot. Always include a ticket reference: # TODO(PROJ-123): description.",
        "tags": ["process", "style", "project-management"],
    },
    "line-too-long": {
        "label": "Keep lines under 120 characters",
        "type": NodeType.STANDARD,
        "description": "Long lines hurt readability in side-by-side diffs and split-screen editors. Break long expressions across multiple lines.",
        "tags": ["style", "readability"],
    },
}


class KnowledgeExtractor:
    """Extracts structured knowledge from code review results.

    Supports two modes:
    - Rule-based: fast mapping from known rule IDs to knowledge nodes (no LLM)
    - LLM-based: uses Claude to identify novel patterns
    """

    def __init__(self, llm: Optional[LLMProvider] = None):
        self._llm = llm
        try:
            self._jinja = Environment(
                loader=PackageLoader("codereviewmate.core.llm", "prompts"),
            )
        except Exception:
            self._jinja = None

    def extract_from_issues(
        self,
        issues: list[Issue],
        existing_nodes: Optional[list[KnowledgeNode]] = None,
    ) -> KnowledgeExtraction:
        """Extract knowledge from a list of review issues using rule-based mapping."""
        new_nodes: list[KnowledgeNode] = []
        new_edges: list[KnowledgeEdge] = []
        seen_labels: set[str] = set()
        existing = existing_nodes or []

        for issue in issues:
            if not issue.rule_id or issue.rule_id not in RULE_KNOWLEDGE_MAP:
                continue

            mapping = RULE_KNOWLEDGE_MAP[issue.rule_id]
            if mapping["label"] in seen_labels:
                continue
            seen_labels.add(mapping["label"])

            node = KnowledgeNode(
                id=self._make_id(mapping["label"]),
                label=mapping["label"],
                type=NodeType(mapping["type"]),
                description=mapping["description"],
                tags=mapping.get("tags", []),
                source_review_ids=[issue.file_path],
            )
            new_nodes.append(node)

            # Link to related existing nodes by tag overlap
            for existing_node in existing:
                if existing_node.id == node.id:
                    continue
                overlap = set(node.tags) & set(existing_node.tags)
                if overlap:
                    edge_type = EdgeType.REFINES if existing_node.type == NodeType.STANDARD else EdgeType.RELATES_TO
                    new_edges.append(KnowledgeEdge(
                        source_id=node.id,
                        target_id=existing_node.id,
                        type=edge_type,
                        description=f"Shared tags: {', '.join(sorted(overlap))}",
                    ))

        summary = f"Extracted {len(new_nodes)} knowledge nodes from {len(issues)} issues"
        if new_nodes:
            summary += f": {', '.join(n.label for n in new_nodes[:3])}"
            if len(new_nodes) > 3:
                summary += f" and {len(new_nodes) - 3} more"

        return KnowledgeExtraction(
            new_nodes=new_nodes,
            new_edges=new_edges,
            summary=summary,
        )

    async def extract_with_llm(
        self,
        issues: list[Issue],
        team_name: str = "",
        existing_nodes: Optional[list[KnowledgeNode]] = None,
    ) -> KnowledgeExtraction:
        """Use LLM to extract novel knowledge patterns from review issues."""
        if not self._llm or not self._jinja:
            logger.warning("LLM or Jinja not available, falling back to rule-based extraction")
            return self.extract_from_issues(issues, existing_nodes)

        try:
            template = self._jinja.get_template("extract_knowledge.j2")
            prompt = template.render(
                team_name=team_name,
                issues=[i.model_dump() for i in issues],
                existing_nodes=[n.model_dump() for n in (existing_nodes or [])],
            )
        except Exception:
            logger.warning("Cannot render knowledge extraction template")
            return self.extract_from_issues(issues, existing_nodes)

        messages = self._llm.format_messages(
            system_prompt="You are a knowledge engineer. Output ONLY valid JSON.",
            user_message=prompt,
        )

        try:
            response = await self._llm.chat(messages, temperature=0.2, max_tokens=2048)
            data = self._parse_json(response.content)
        except Exception as e:
            logger.error("LLM knowledge extraction failed: %s", e)
            return KnowledgeExtraction(
                new_nodes=[],
                summary=f"LLM extraction failed: {e}",
            )

        new_nodes: list[KnowledgeNode] = []
        for item in data.get("new_nodes", []):
            try:
                new_nodes.append(KnowledgeNode(
                    id=self._make_id(item["label"]),
                    label=item["label"],
                    type=NodeType(item.get("type", "pattern")),
                    description=item.get("description", ""),
                    tags=item.get("tags", []),
                ))
            except Exception:
                logger.debug("Skipping malformed LLM node: %s", item)

        new_edges: list[KnowledgeEdge] = []
        label_to_id = {n.label: n.id for n in new_nodes}
        for existing_node in (existing_nodes or []):
            label_to_id[existing_node.label] = existing_node.id

        for item in data.get("new_edges", []):
            try:
                src = label_to_id.get(item["source_label"])
                tgt = label_to_id.get(item["target_label"])
                if src and tgt:
                    new_edges.append(KnowledgeEdge(
                        source_id=src,
                        target_id=tgt,
                        type=EdgeType(item.get("type", "relates_to")),
                        description=item.get("description", ""),
                    ))
            except Exception:
                logger.debug("Skipping malformed LLM edge: %s", item)

        return KnowledgeExtraction(
            new_nodes=new_nodes,
            new_edges=new_edges,
            summary=data.get("summary", f"LLM extracted {len(new_nodes)} nodes"),
        )

    @staticmethod
    def _parse_json(content: str) -> dict:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            end = next((i for i, line in enumerate(lines[1:], 1) if line.startswith("```")), len(lines))
            content = "\n".join(lines[1:end])
        return json.loads(content)

    @staticmethod
    def _make_id(label: str) -> str:
        import re
        node_id = label.lower().strip()
        node_id = re.sub(r'[^\w]+', '_', node_id)
        return node_id.strip('_') or 'node'
