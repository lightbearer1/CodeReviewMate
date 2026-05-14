# CodeReviewMate

智能代码审查与知识沉淀 Agent，解决团队两大痛点：
1. **审查经验无法积累** — 宝贵意见分散在 PR 中，无法被后续审查复用
2. **新人成长缓慢** — 缺乏系统化知识库，新人反复询问同样的问题

## 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    CodeReviewMate System                         │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: 上下文感知    Layer 2: 审查执行     Layer 3: 知识沉淀  │
│  RAG 文档检索          预提交检查 (<2s)      自动知识提取        │
│  混合语义+关键词搜索   深度架构合规审查      知识图谱构建        │
│  Cross-encoder 重排序  自动修复 Patch        智能辅导引擎        │
│  多文档摄入            审查报告生成          可视化 & 查询       │
├─────────────────────────────────────────────────────────────────┤
│  公共层: LLM 抽象 | Git 平台抽象 | 配置管理 | 事件总线           │
├─────────────────────────────────────────────────────────────────┤
│  接口: CLI (Typer) | Pre-commit Hook | CI 集成 | REST API       │
└─────────────────────────────────────────────────────────────────┘
```

### Layer 1 — 上下文感知

摄入团队架构文档、编码规范、历史 PR，构建向量化知识库。审查时自动检索相关上下文，确保每一条审查建议都有据可依。

### Layer 2 — 审查执行

- **Pre-commit 检查**：27 条内置规则（风格、安全、Bug 模式）+ 圈复杂度分析，自动拦截 60%+ 低级别问题并生成修复 patch
- **深度审查**：LLM 驱动的架构合规检查，验证分层、依赖方向、设计模式等

### Layer 3 — 知识沉淀

从审查结果中自动提取模式，构建结构化知识图谱。新人可通过智能辅导引擎自然语言提问，获得带示例的完整回答。

## 安装

```bash
pip install codereviewmate
```

或从源码安装：

```bash
git clone git@github.com:lightbearer1/CodeReviewMate.git
cd CodeReviewMate
pip install -e ".[dev]"
```

## 快速开始

### 1. 初始化配置

```bash
codereviewmate config init
```

在项目根目录生成 `.codereviewmate.yaml`，按需修改团队名称、LLM 提供者等。

### 2. 摄入团队文档

```bash
# 摄入架构文档
codereviewmate ingest directory docs/architecture --type architecture

# 摄入编码规范
codereviewmate ingest directory docs/standards --type coding_standard

# 摄入单个文档
codereviewmate ingest document docs/api-design.md --type architecture
```

### 3. 代码审查

```bash
# Pre-commit 快速检查（仅规则+AST，不需要 LLM）
codereviewmate review pre-commit --repo .

# 单文件检查
codereviewmate review check src/app.py

# 深度架构审查（需要 LLM）
codereviewmate review deep --repo . --base main

# 完整审查流程（Pre-commit + Deep）
codereviewmate review full --repo . --output report.md

# 审查 GitHub PR
codereviewmate review full --pr 42 --platform github
```

### 4. 知识库查询

```bash
# 查看知识库统计
codereviewmate ingest stats

# 搜索知识库
codereviewmate ingest search "数据库迁移最佳实践"

# 智能辅导
codereviewmate tutor ask "如何处理数据库迁移？"
```

## CLI 命令参考

| 命令 | 说明 |
|------|------|
| `codereviewmate review pre-commit` | Pre-commit 快速检查 |
| `codereviewmate review check <file>` | 单文件检查 |
| `codereviewmate review deep` | LLM 深度架构审查 |
| `codereviewmate review full` | 完整审查流程 |
| `codereviewmate ingest document <path>` | 摄入文档到知识库 |
| `codereviewmate ingest directory <dir>` | 批量摄入目录 |
| `codereviewmate ingest search <query>` | 搜索知识库 |
| `codereviewmate ingest stats` | 知识库统计 |
| `codereviewmate config show` | 查看当前配置 |
| `codereviewmate config init` | 初始化配置文件 |
| `codereviewmate config validate` | 验证配置文件 |
| `codereviewmate knowledge viz` | 生成知识图谱可视化 |
| `codereviewmate tutor ask <question>` | 智能辅导 |

## 配置

配置采用 5 层叠加，后者覆盖前者：

1. 内置默认值
2. 团队配置 `.codereviewmate.yaml`（仓库根目录）
3. 用户配置 `~/.config/codereviewmate/config.yaml`
4. 环境变量 `CRM_*`
5. CLI 参数

```yaml
team_name: "我的团队"

llm:
  provider: claude          # claude | openai | ollama
  model: claude-sonnet-4-6
  api_key: ""               # 留空则从 ANTHROPIC_API_KEY 环境变量读取
  temperature: 0.2
  max_tokens: 4096

review:
  pre_commit_enabled: true
  deep_review_enabled: true
  auto_fix_enabled: true
  supported_extensions: [.py, .js, .ts, .tsx, .go, .java, .rs]
  ignore_patterns: []

rag:
  chunk_size: 512
  chunk_overlap: 64
  top_k_retrieval: 5
  rerank_enabled: true
```

环境变量：

| 变量 | 说明 |
|------|------|
| `CRM_LLM_PROVIDER` | LLM 提供者 |
| `CRM_LLM_MODEL` | 模型名称 |
| `CRM_LLM_API_KEY` | API Key |
| `CRM_LLM_API_BASE` | API 地址（Ollama 等） |
| `ANTHROPIC_API_KEY` | Anthropic API Key（自动读取） |
| `OPENAI_API_KEY` | OpenAI API Key（自动读取） |

## 内置规则（27 条）

### 风格规则
`no-debug-print` `no-console-log` `no-trailing-whitespace` `multiple-blank-lines` `line-too-long` `no-todo-without-ticket` `class-naming-convention` `function-naming-convention`

### 安全规则
`no-hardcoded-secrets` `no-hardcoded-connection-string` `sql-injection-fstring` `sql-injection-format` `shell-injection` `insecure-deserialization` `open-redirect` `debug-mode-enabled` `eval-usage` `md5-weak-hash`

### Bug 模式规则
`bare-except` `mutable-default-arg` `is-comparison-literal` `assignment-in-condition` `undefined-variable` `equality-none` `not-in-loop-collection-modification` `float-equality` `variable-shadowing`

## Pre-commit Hook

在 `.pre-commit-config.yaml` 中添加：

```yaml
repos:
  - repo: https://github.com/lightbearer1/CodeReviewMate
    rev: v0.1.0
    hooks:
      - id: codereviewmate-check
```

## CI 集成

项目自带 GitHub Actions workflow（`.github/workflows/codereviewmate.yml`），在 PR 时自动运行 Pre-commit 检查和深度审查，并将报告回贴到 PR。

```yaml
# 在你的仓库中创建 .github/workflows/code-review.yml
name: Code Review
on: [pull_request]
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: pip install codereviewmate
      - run: codereviewmate review full --pr ${{ github.event.pull_request.number }} --platform github --output report.md
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## 项目结构

```
CodeReviewMate/
├── src/codereviewmate/
│   ├── cli/                    # CLI 命令
│   │   ├── app.py              # Typer 主入口
│   │   ├── review_cmd.py       # review 命令组
│   │   ├── ingest_cmd.py       # ingest 命令组
│   │   ├── config_cmd.py       # config 命令组
│   │   ├── knowledge_cmd.py    # knowledge 命令组
│   │   └── tutor_cmd.py        # tutor 命令组
│   ├── core/                   # 核心领域逻辑
│   │   ├── models/             # Pydantic 领域模型
│   │   ├── config/             # 5 层配置叠加
│   │   ├── llm/                # LLM 抽象 + Claude/OpenAI/Ollama 适配器
│   │   ├── context/            # RAG 引擎、向量存储、检索器
│   │   ├── review/             # 审查引擎、规则、自动修复
│   │   ├── knowledge/          # 知识提取、图谱、辅导
│   │   └── events/             # 事件总线
│   └── integrations/           # 外部集成
│       ├── git/                # Git 平台适配器 (GH/GL/Gitee)
│       └── ci/                 # CI/CD 集成
├── tests/
│   └── unit/                   # 单元测试
├── .github/workflows/          # 自带 CI 配置
├── .pre-commit-hooks.yaml      # Pre-commit hook 配置
└── pyproject.toml
```

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.13+ |
| CLI | Typer + Rich |
| LLM | Anthropic Claude / OpenAI / Ollama |
| 向量库 | ChromaDB（嵌入式，零 Docker 依赖） |
| 嵌入模型 | BGE-M3（sentence-transformers） |
| 知识图谱 | NetworkX + pyvis |
| AST 分析 | tree-sitter（100+ 语言） |
| Git | GitPython + GitHub/GitLab/Gitee API |
| 测试 | pytest + pytest-asyncio |

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v

# 代码检查
ruff check src/
```

## 实施阶段

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 0 — 基础设施 | ✅ | 项目骨架、模型、配置、LLM 抽象、事件总线 |
| Phase 1 — 上下文感知 | ✅ | RAG 引擎、向量存储、混合检索 |
| Phase 2 — 快速检查 | ✅ | 27 条规则、AST 分析、自动修复 |
| Phase 3 — 深度审查 | ✅ | LLM 架构合规、Git 适配器、报告生成 |
| Phase 4 — 知识沉淀 | ⬜ | 知识提取、图谱管理、智能辅导 |
| Phase 5 — API & IDE | ⬜ | FastAPI、VS Code 扩展 |
| Phase 6 — 打磨 | ⬜ | 缓存、重试、文档 |

## License

MIT
