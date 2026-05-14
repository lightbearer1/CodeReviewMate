"""Multi-language AST analysis using tree-sitter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".sql": "sql",
}


class TreeSitterAnalyzer:
    """Multi-language code structure analyzer using tree-sitter."""

    def __init__(self, languages: Optional[list[str]] = None):
        self._parsers: dict[str, object] = {}
        self._languages_to_load = languages or ["python", "javascript", "typescript", "go", "java"]
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        import tree_sitter

        for lang_name in self._languages_to_load:
            try:
                lang = tree_sitter.Language(lang_name)
                parser = tree_sitter.Parser(lang)
                self._parsers[lang_name] = parser
                logger.debug("Loaded tree-sitter parser: %s", lang_name)
            except Exception:
                logger.debug("Tree-sitter language not available: %s", lang_name)

        self._loaded = True
        if not self._parsers:
            logger.warning("No tree-sitter parsers loaded. AST analysis will be skipped.")

    def get_parser(self, file_path: str) -> Optional[object]:
        """Get the appropriate parser for a file based on its extension."""
        self._ensure_loaded()
        ext = Path(file_path).suffix.lower()
        lang = LANGUAGE_MAP.get(ext)
        if lang:
            return self._parsers.get(lang)
        return None

    def parse_file(self, file_path: str, source: str) -> Optional[tuple]:
        """Parse a file and return (tree, root_node, source_bytes, parser)."""
        parser = self.get_parser(file_path)
        if parser is None:
            return None

        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)
        return (tree, tree.root_node, source_bytes, parser)

    def get_supported_extensions(self) -> list[str]:
        """Return file extensions that have available parsers."""
        self._ensure_loaded()
        result: list[str] = []
        for ext, lang in LANGUAGE_MAP.items():
            if lang in self._parsers:
                result.append(ext)
        return result

    def extract_functions(
        self, file_path: str, source: str
    ) -> list[dict]:
        """Extract function/method definitions from source code."""
        result = self.parse_file(file_path, source)
        if result is None:
            return []

        _, root, source_bytes, _ = result
        functions: list[dict] = []
        lang = LANGUAGE_MAP.get(Path(file_path).suffix.lower(), "")

        self._walk_functions(root, source_bytes, functions, lang)
        return functions

    def _walk_functions(
        self, node, source_bytes: bytes, functions: list[dict], lang: str
    ) -> None:
        """Recursively find function definitions in the AST."""
        func_types = {
            "python": ["function_definition"],
            "javascript": ["function_declaration", "method_definition", "arrow_function"],
            "typescript": ["function_declaration", "method_definition", "arrow_function"],
            "go": ["function_declaration", "method_declaration"],
            "java": ["method_declaration", "constructor_declaration"],
        }.get(lang, ["function_declaration"])

        if node.type in func_types:
            name_node = node.child_by_field_name("name")
            name = (
                name_node.text.decode("utf-8")
                if name_node and hasattr(name_node, "text")
                else source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                if name_node
                else "anonymous"
            )

            func_info = {
                "name": name,
                "line_start": node.start_point[0] + 1,
                "line_end": node.end_point[0] + 1,
                "type": node.type,
                "params": self._extract_params(node, source_bytes),
            }
            functions.append(func_info)

        for child in node.children:
            self._walk_functions(child, source_bytes, functions, lang)

    @staticmethod
    def _extract_params(node, source_bytes: bytes) -> list[str]:
        """Extract parameter names from function definition."""
        params_node = node.child_by_field_name("parameters")
        if params_node is None:
            return []
        params: list[str] = []
        for child in params_node.children:
            if child.type == "identifier":
                params.append(source_bytes[child.start_byte : child.end_byte].decode("utf-8"))
        return params

    def extract_classes(self, file_path: str, source: str) -> list[dict]:
        """Extract class/struct definitions."""
        result = self.parse_file(file_path, source)
        if result is None:
            return []
        _, root, source_bytes, _ = result
        classes: list[dict] = []
        self._walk_classes(root, source_bytes, classes)
        return classes

    def _walk_classes(self, node, source_bytes: bytes, classes: list[dict]) -> None:
        class_types = {
            "class_definition",
            "class_declaration",
            "type_declaration",
            "struct_declaration",
        }
        if node.type in class_types:
            name_node = node.child_by_field_name("name")
            if name_node:
                name = source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")
                classes.append(
                    {
                        "name": name,
                        "line_start": node.start_point[0] + 1,
                        "line_end": node.end_point[0] + 1,
                    }
                )
        for child in node.children:
            self._walk_classes(child, source_bytes, classes)

    def extract_imports(self, file_path: str, source: str) -> list[dict]:
        """Extract import/include statements."""
        result = self.parse_file(file_path, source)
        if result is None:
            return []
        _, root, source_bytes, _ = result
        imports: list[dict] = []
        self._walk_imports(root, source_bytes, imports)
        return imports

    def _walk_imports(self, node, source_bytes: bytes, imports: list[dict]) -> None:
        import_types = {
            "import_statement",
            "import_declaration",
            "import_from_statement",
            "require_call",
        }
        if node.type in import_types:
            imports.append(
                {
                    "statement": source_bytes[node.start_byte : node.end_byte].decode("utf-8"),
                    "line": node.start_point[0] + 1,
                }
            )
        for child in node.children:
            self._walk_imports(child, source_bytes, imports)
