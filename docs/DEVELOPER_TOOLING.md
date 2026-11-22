# Developer tooling setup

This document records **verified** editor, agent-skill and MCP setup for RFinance. It was checked against official marketplace/docs pages on 2026-11-22. Tooling is optional: no tool listed here is required to build, test or run the application.

## 1. VS Code / Cursor extensions

VS Code and Cursor show `.vscode/extensions.json` automatically and offer to install the recommendations. Equivalent manual command:

```powershell
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension TheQtCompany.qt-python-pack
code --install-extension charliermarsh.ruff
code --install-extension ms-python.mypy-type-checker
code --install-extension tamasfe.even-better-toml
code --install-extension qwtel.sqlite-viewer
code --install-extension usernamehw.errorlens
code --install-extension eamodio.gitlens
code --install-extension gruntfuggly.todo-tree
code --install-extension hbenl.vscode-test-explorer
code --install-extension LittleFoxTeam.vscode-python-test-adapter
code --install-extension yzhang.markdown-all-in-one
code --install-extension shd101wyy.markdown-preview-enhanced
```

Why these:

| Tool | Purpose for RFinance |
|---|---|
| `TheQtCompany.qt-python-pack` / `.qt-python` | Official PySide6 build/run/debug, Qt Designer and documentation |
| `ms-python.python` + Pylance | Interpreter/venv management, IntelliSense, debugpy |
| `charliermarsh.ruff`, `ms-python.mypy-type-checker` | Same lint/format and strict typing as CI |
| `tamasfe.even-better-toml` | Validates `pyproject.toml` and its PEP 639 license fields |
| `qwtel.sqlite-viewer` | Inspect local SQLite without leaving the editor |
| `usernamehw.errorlens`, `eamodio.gitlens`, `gruntfuggly.todo-tree` | Inline diagnostics, history/blame, TODO tracking |
| `hbenl.vscode-test-explorer` + `LittleFoxTeam.vscode-python-test-adapter` | Visual pytest run/debug |
| Markdown extensions | Edit `AGENTS.md`, `ROADMAP.md`, ADRs and docs |

Note: `seanwu.vscode-qt-for-python` exists but its repository is **archived/deprecated** ("use the official Qt extensions instead"), so it is intentionally not recommended. Microsoft's `ms-python.python` already provides a Test view; the two Test Explorer extensions are optional if you prefer their UI.

Suggested `.vscode/settings.json` (local, not committed):

```json
{
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": { "source.organizeImports.ruff": "explicit" }
  },
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "mypy-type-checker.importStrategy": "fromEnvironment"
}
```

## 2. Project agent skills (installed in this repo)

OpenCode V2 discovers `.opencode/skills/<id>/SKILL.md`. These are committed and load automatically when relevant:

| Skill ID | Purpose |
|---|---|
| `rfinance-invariants` | Canonical product invariants and policy digest; load before code/data/AI/security/docs work |
| `rfinance-finance-qt` | Decimal finance, provenance, financial-sector handling and PySide6 layering patterns |
| `rfinance-quality` | Test/quality gates and verification commands |
| `rfinance-docs` | Handoff documentation policy for status files and ADRs |

Claude Code sees `AGENTS.md`/`CLAUDE.md` at the repository root; both remain canonical. To use the same rules as portable Claude skills, the directories above can be mirrored under `.claude/skills/` (OpenCode already reads both locations).

### External skill packs installed (2026-11-22)

- **Superpowers** ([obra/superpowers](https://github.com/obra/superpowers), MIT): installed as an OpenCode V2 plugin via `plugins: ["superpowers@git+https://github.com/obra/superpowers.git"]` in `~/.config/opencode/opencode.json` (global, outside the repo). It registers 15 process skills including `brainstorming`, `writing-plans`, `test-driven-development`, `systematic-debugging`, `requesting-code-review` and `verification-before-completion`. Verified: the skills appeared in the running session after the config change.
- **Matt Pocock skills** ([mattpocock/skills](https://github.com/mattpocock/skills), MIT): the portable `skills/engineering` and `skills/productivity` trees were copied into this repository's `.opencode/skills/` so every contributor receives them. User-invoked skills already carry `disable-model-invocation: true` upstream, so they stay out of automatic advertising.

Because both packs are present, treat them as complementary: Superpowers supplies the mandatory process workflow; Matt Pocock skills supply optional domain/CRISP-style disciplines (`domain-modeling`, `codebase-design`, `to-spec`, `to-tickets`, `improve-codebase-architecture`, `diagnosing-bugs`, `research`, etc.). **`AGENTS.md` remains canonical** — any skill instruction that conflicts with a product invariant (no broker access, no silent zero, evidence-first, simulation labelling, autonomous execution when the owner opted out of questions) loses to the repository policy.

Skill files added after a session starts may require `/reload` or a fresh session before the skill loader advertises them; this is a harness cache behaviour, not a missing installation.

## 3. MCP servers (OpenCode V2)

Servers consume model context, so enable only what you need. Prefer the CLI; it preserves unrelated project configuration:

```sh
opencode mcp add context7 --url https://mcp.context7.com/mcp
opencode mcp add filesystem -- npx -y @modelcontextprotocol/server-filesystem /absolute/path/to/RFinance
opencode mcp add git -- uvx mcp-server-git --repository /absolute/path/to/RFinance
opencode mcp add sequentialthinking -- npx -y @modelcontextprotocol/server-sequential-thinking
opencode mcp add memory -- npx -y @modelcontextprotocol/server-memory
opencode mcp add playwright -- npx -y @playwright/mcp@latest
opencode mcp list
```

GitHub's official remote MCP (`https://api.githubcopilot.com/mcp/`) uses OAuth. If `opencode mcp list` reports `needs authentication`, open the TUI, run `/mcps`, select the server and sign in. Credentials are stored outside the repository — never paste a token into config or chat.

A hand-written template is provided at `.opencode/opencode.jsonc.example`. It is deliberately **not** named `opencode.jsonc`, so it is inert until copied. In V2 the shape is `mcp.servers.<name>`; secrets use `{env:NAME}` substitution.

## 4. Security boundaries for agent tooling (non-negotiable)

These follow `AGENTS.md` and the `SECURITY_MODEL.md`:

- **No trading or broker MCP** (Alpaca, broker APIs, payment providers). RFinance never logs in, submits orders, or moves money.
- **Market/broker data MCPs are research-only**, never a production entitlement. Verify terms, licensing and rate limits before enabling one; do not let it become an ingestion path without a source-policy review.
- **Filesystem MCP must be scoped to the repository or explicit data directory.** Do not grant home-directory or drive-wide access; retrieved documents and model output are untrusted data.
- **Playwright MCP is for permitted public sources only**, against the source allowlist, with no auth bypass and no dynamic URL expansion by AI.
- **GitHub MCP must not be used to merge on red checks.** Verify CI state first.
- Never store PATs or OAuth secrets in repository files. Use environment substitution or OpenCode's OAuth storage.

## 5. References

- OpenCode skills: https://opencode.ai/docs/skills/
- OpenCode MCP servers: https://opencode.ai/docs/mcp-servers/
- OpenCode instructions: https://opencode.ai/docs/instructions/
- Official MCP reference servers: https://github.com/modelcontextprotocol/servers
- Playwright MCP: https://playwright.dev/docs/getting-started-mcp
- Qt Python extension: https://marketplace.visualstudio.com/items?itemName=TheQtCompany.qt-python
- Ruff extension: https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff
