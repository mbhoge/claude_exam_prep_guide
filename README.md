# Claude Certified Architect – Foundations Exam Prep Guide

> **Certification**: Claude Certified Architect – Foundations  
> **Passing Score**: 720 / 1000  
> **Format**: Multiple choice, scenario-based (4 of 6 scenarios per sitting)  
> **Target**: Solution architects with 6+ months hands-on Claude experience

This repository is a **complete study companion** for the Claude Certified Architect – Foundations certification. Every folder maps to a Task Statement from the official exam guide. Each contains concept notes, Python code examples drawn from real exam scenarios, and anti-pattern analyses.

---

## 📋 Exam Domain Weightings

| Domain | Topic | Weight |
|--------|-------|--------|
| **Domain 1** | Agentic Architecture & Orchestration | **27%** |
| **Domain 2** | Tool Design & MCP Integration | **18%** |
| **Domain 3** | Claude Code Configuration & Workflows | **20%** |
| **Domain 4** | Prompt Engineering & Structured Output | **20%** |
| **Domain 5** | Context Management & Reliability | **15%** |

---

## 🎯 Exam Scenarios (4 of 6 appear per sitting)

| # | Scenario | Primary Domains |
|---|----------|-----------------|
| 1 | Customer Support Resolution Agent | D1, D2, D5 |
| 2 | Code Generation with Claude Code | D3, D5 |
| 3 | Multi-Agent Research System | D1, D2, D5 |
| 4 | Developer Productivity with Claude | D2, D3, D1 |
| 5 | Claude Code for Continuous Integration | D3, D4 |
| 6 | Structured Data Extraction | D4, D5 |

---

## 📂 Repository Structure

```
claude_exam_prep_guide/
│
├── README.md                          ← You are here
│
├── domain_1_agentic_architecture/     ← 27% of exam
│   ├── 01_agentic_loops/              ← Task 1.1
│   ├── 02_multi_agent_orchestration/  ← Task 1.2 ⭐ Covered in depth
│   ├── 03_subagent_invocation/        ← Task 1.3
│   ├── 04_multi_step_workflows/       ← Task 1.4
│   ├── 05_agent_sdk_hooks/            ← Task 1.5
│   ├── 06_task_decomposition/         ← Task 1.6
│   └── 07_session_management/         ← Task 1.7
│
├── domain_2_tool_design_mcp/          ← 18% of exam
│   ├── 01_tool_interfaces/            ← Task 2.1
│   ├── 02_structured_error_responses/ ← Task 2.2
│   ├── 03_tool_distribution/          ← Task 2.3
│   ├── 04_mcp_server_integration/     ← Task 2.4
│   └── 05_builtin_tools/              ← Task 2.5
│
├── domain_3_claude_code/              ← 20% of exam
│   ├── 01_claude_md_configuration/    ← Task 3.1
│   ├── 02_slash_commands_skills/      ← Task 3.2
│   ├── 03_path_specific_rules/        ← Task 3.3
│   ├── 04_plan_mode_vs_direct/        ← Task 3.4
│   ├── 05_iterative_refinement/       ← Task 3.5
│   └── 06_cicd_integration/           ← Task 3.6
│
├── domain_4_prompt_engineering/       ← 20% of exam
│   ├── 01_explicit_criteria/          ← Task 4.1
│   ├── 02_few_shot_prompting/         ← Task 4.2
│   ├── 03_structured_output/          ← Task 4.3
│   ├── 04_validation_retry/           ← Task 4.4
│   ├── 05_batch_processing/           ← Task 4.5
│   └── 06_multi_instance_review/      ← Task 4.6
│
└── domain_5_context_management/       ← 15% of exam
    ├── 01_conversation_context/        ← Task 5.1
    ├── 02_escalation_patterns/         ← Task 5.2
    ├── 03_error_propagation/           ← Task 5.3
    ├── 04_codebase_exploration/        ← Task 5.4
    ├── 05_human_review/                ← Task 5.5
    └── 06_information_provenance/      ← Task 5.6
```

---

## Domain 1: Agentic Architecture & Orchestration (27%)

### Task 1.1 – Design and implement agentic loops for autonomous task execution

**Core Knowledge:**
- The agentic loop lifecycle: send request → inspect `stop_reason` (`"tool_use"` vs `"end_turn"`) → execute tools → append results → repeat
- Tool results appended to conversation history so the model can reason about the next action
- Model-driven decision-making vs pre-configured decision trees

**Key Skills:**
- Implement control flow: continue on `"tool_use"`, terminate on `"end_turn"`
- Append `tool_result` blocks correctly between iterations
- Avoid anti-patterns: never parse natural language to detect loop termination; don't use arbitrary iteration caps as primary stopping mechanism

**📁 Folder:** `domain_1_agentic_architecture/01_agentic_loops/`

---

### Task 1.2 – Orchestrate multi-agent systems with coordinator-subagent patterns ⭐

**Core Knowledge:**
- **Hub-and-spoke architecture**: coordinator manages all inter-subagent communication, error handling, and information routing
- **Context isolation**: subagents do NOT inherit the coordinator's conversation history automatically
- Coordinator's role: task decomposition, delegation, result aggregation, dynamic subagent selection
- **Critical risk**: overly narrow task decomposition leads to incomplete coverage of broad research topics

**Key Skills:**
- Design coordinators that dynamically select subagents rather than always routing through the full pipeline
- Partition research scope to minimize duplication (distinct subtopics per agent)
- Implement iterative refinement loops: coordinator evaluates gaps → re-delegates → re-invokes synthesis
- Route ALL subagent communication through coordinator for observability

**📁 Folder:** `domain_1_agentic_architecture/02_multi_agent_orchestration/`

---

### Task 1.3 – Configure subagent invocation, context passing, and spawning

**Core Knowledge:**
- `Task` tool is the mechanism for spawning subagents; `allowedTools` must include `"Task"`
- Subagent context must be **explicitly provided** in the prompt — no automatic parent context inheritance
- `AgentDefinition` configuration: descriptions, system prompts, tool restrictions
- `fork_session` for divergent approaches from shared baseline

**Key Skills:**
- Pass prior agent findings directly in the subagent prompt
- Use structured data formats to separate content from metadata (source URLs, page numbers)
- Spawn parallel subagents via multiple `Task` calls in a **single coordinator response**
- Write coordinator prompts that specify goals/quality criteria rather than step-by-step instructions

**📁 Folder:** `domain_1_agentic_architecture/03_subagent_invocation/`

---

### Task 1.4 – Implement multi-step workflows with enforcement and handoff patterns

**Core Knowledge:**
- Programmatic enforcement (hooks, gates) vs prompt-based guidance — prompt instructions have **non-zero failure rate**
- When deterministic compliance is required (e.g., identity verification before financial ops), use programmatic gates
- Structured handoff protocols for escalation: customer details, root cause, recommended actions

**Key Skills:**
- Implement prerequisite gates: block `process_refund` until `get_customer` returns verified ID
- Decompose multi-concern requests into parallel investigations with shared context
- Compile structured handoff summaries when escalating to humans who lack conversation access

**📁 Folder:** `domain_1_agentic_architecture/04_multi_step_workflows/`

---

### Task 1.5 – Apply Agent SDK hooks for tool call interception and data normalization

**Core Knowledge:**
- `PostToolUse` hooks: intercept tool results for transformation before model processes them
- Hook patterns that block outgoing tool calls to enforce compliance (e.g., refunds above threshold)
- Hooks = deterministic guarantees; prompt instructions = probabilistic compliance

**Key Skills:**
- `PostToolUse` hooks to normalize heterogeneous formats (Unix timestamps → ISO 8601, status codes → strings)
- Tool call interception hooks that block policy violations and redirect to alternative workflows
- Choose hooks when business rules require **guaranteed** compliance

**📁 Folder:** `domain_1_agentic_architecture/05_agent_sdk_hooks/`

---

### Task 1.6 – Design task decomposition strategies for complex workflows

**Core Knowledge:**
- Fixed sequential pipelines (prompt chaining) vs dynamic adaptive decomposition
- Prompt chaining: break into sequential steps (per-file analysis → cross-file integration pass)
- Adaptive plans: generate subtasks based on intermediate discoveries

**Key Skills:**
- Prompt chaining for predictable multi-aspect reviews
- Dynamic decomposition for open-ended investigation tasks
- Split large code reviews: per-file local passes + separate cross-file integration pass
- Decompose open-ended tasks by first mapping structure, then creating adaptive plans

**📁 Folder:** `domain_1_agentic_architecture/06_task_decomposition/`

---

### Task 1.7 – Manage session state, resumption, and forking

**Core Knowledge:**
- `--resume <session-name>` to continue specific prior conversations
- `fork_session` for independent branches from shared analysis baseline
- Must inform agent about file changes when resuming after code modifications
- New session + structured summary is more reliable than resuming with stale tool results

**Key Skills:**
- Use `--resume` for named investigation sessions across work sessions
- Use `fork_session` for parallel exploration (comparing testing strategies, refactoring approaches)
- Choose resumption vs fresh start based on whether prior context is still valid

**📁 Folder:** `domain_1_agentic_architecture/07_session_management/`

---

## Domain 2: Tool Design & MCP Integration (18%)

### Task 2.1 – Design effective tool interfaces with clear descriptions and boundaries

**Core Knowledge:**
- Tool descriptions are the **primary mechanism** LLMs use for tool selection
- Minimal descriptions → unreliable selection among similar tools
- Include: input formats, example queries, edge cases, boundary explanations
- Ambiguous/overlapping descriptions cause misrouting

**Key Skills:**
- Write descriptions that clearly differentiate purpose, inputs, outputs, and when to use each
- Rename tools and descriptions to eliminate functional overlap
- Split generic tools into purpose-specific tools with defined input/output contracts

**📁 Folder:** `domain_2_tool_design_mcp/01_tool_interfaces/`

---

### Task 2.2 – Implement structured error responses for MCP tools

**Core Knowledge:**
- `isError` flag pattern for communicating tool failures to agents
- Error types: transient (timeouts), validation (invalid input), business (policy violations), permission
- Generic "Operation failed" messages prevent appropriate recovery decisions
- Retryable vs non-retryable errors must be clearly distinguished

**Key Skills:**
- Return structured metadata: `errorCategory`, `isRetryable`, human-readable description
- Include `retriable: false` flags for business rule violations
- Subagents recover transient errors locally; propagate only unresolvable errors to coordinator
- Distinguish access failures (needs retry) from valid empty results (no matches found)

**📁 Folder:** `domain_2_tool_design_mcp/02_structured_error_responses/`

---

### Task 2.3 – Distribute tools appropriately across agents and configure tool choice

**Core Knowledge:**
- Too many tools (18 vs 4-5) degrades tool selection reliability
- Agents with tools outside specialization tend to misuse them
- Scoped tool access: agents get only what they need
- `tool_choice`: `"auto"`, `"any"`, forced `{"type": "tool", "name": "..."}`

**Key Skills:**
- Restrict subagent tool sets to role-relevant tools only
- Replace generic tools with constrained alternatives (e.g., `fetch_url` → `load_document`)
- Provide scoped cross-role tools for high-frequency needs (e.g., `verify_fact` for synthesis)
- Use forced `tool_choice` to ensure specific tool called first
- Use `tool_choice: "any"` to guarantee model calls a tool rather than returning text

**📁 Folder:** `domain_2_tool_design_mcp/03_tool_distribution/`

---

### Task 2.4 – Integrate MCP servers into Claude Code and agent workflows

**Core Knowledge:**
- Project-level (`.mcp.json`) for shared team tooling vs user-level (`~/.claude.json`) for personal
- Environment variable expansion in `.mcp.json` (`${GITHUB_TOKEN}`) for credential management
- All configured MCP server tools discovered at connection time, available simultaneously
- MCP resources expose content catalogs to reduce exploratory tool calls

**Key Skills:**
- Configure shared servers in `.mcp.json` with env var expansion
- Configure personal servers in `~/.claude.json`
- Enhance MCP tool descriptions to prevent model preferring built-in tools
- Choose community MCP servers over custom for standard integrations
- Expose content catalogs as MCP resources

**📁 Folder:** `domain_2_tool_design_mcp/04_mcp_server_integration/`

---

### Task 2.5 – Select and apply built-in tools effectively

**Core Knowledge:**
- `Grep`: content search (function names, error messages, import statements)
- `Glob`: file path pattern matching (find files by name/extension)
- `Read`/`Write`: full file operations; `Edit`: targeted modifications via unique text matching
- When `Edit` fails (non-unique text), use `Read` + `Write` as fallback

**Key Skills:**
- `Grep` for searching code content; `Glob` for finding files by pattern
- `Read` → `Write` fallback when `Edit` cannot find unique anchor text
- Build codebase understanding incrementally: `Grep` entry points → `Read` imports → trace flows
- Never read all files upfront

**📁 Folder:** `domain_2_tool_design_mcp/05_builtin_tools/`

---

## Domain 3: Claude Code Configuration & Workflows (20%)

### Task 3.1 – Configure CLAUDE.md files with appropriate hierarchy and scoping

**Core Knowledge:**
- Hierarchy: user-level (`~/.claude/CLAUDE.md`) → project-level (`.claude/CLAUDE.md`) → directory-level
- User-level settings are NOT shared via version control
- `@import` syntax for referencing external files (modular CLAUDE.md)
- `.claude/rules/` directory for topic-specific rule files

**Key Skills:**
- Diagnose hierarchy issues (team member not receiving instructions → check user vs project level)
- Use `@import` to selectively include standards files per package
- Split large CLAUDE.md into focused files in `.claude/rules/`
- Use `/memory` command to verify loaded memory files

**📁 Folder:** `domain_3_claude_code/01_claude_md_configuration/`

---

### Task 3.2 – Create and configure custom slash commands and skills

**Core Knowledge:**
- Project-scoped commands: `.claude/commands/` (version-controlled, shared)
- User-scoped commands: `~/.claude/commands/` (personal)
- Skills: `.claude/skills/` with `SKILL.md` frontmatter (`context: fork`, `allowed-tools`, `argument-hint`)
- `context: fork` runs skill in isolated sub-agent context (prevents polluting main conversation)

**Key Skills:**
- Create project-scoped commands in `.claude/commands/` for team-wide availability
- Use `context: fork` for verbose/exploratory skills
- Configure `allowed-tools` to restrict tool access during skill execution
- Use `argument-hint` to prompt for required parameters when skill invoked without args
- Choose: skills (on-demand) vs CLAUDE.md (always-loaded universal standards)

**📁 Folder:** `domain_3_claude_code/02_slash_commands_skills/`

---

### Task 3.3 – Apply path-specific rules for conditional convention loading

**Core Knowledge:**
- `.claude/rules/` files with YAML frontmatter `paths` fields for conditional activation
- Path-scoped rules load only when editing matching files → reduces irrelevant context
- Glob-pattern rules vs directory-level CLAUDE.md: globs work across directories

**Key Skills:**
- Create `.claude/rules/` files with glob path scoping (`paths: ["terraform/**/*"]`)
- Use globs to apply conventions to file types regardless of directory (`**/*.test.tsx`)
- Choose path-specific rules when conventions span multiple directories

**📁 Folder:** `domain_3_claude_code/03_path_specific_rules/`

---

### Task 3.4 – Determine when to use plan mode vs direct execution

**Core Knowledge:**
- Plan mode: complex tasks, large-scale changes, multiple valid approaches, architectural decisions, multi-file
- Direct execution: simple, well-scoped, single-file changes
- `Explore` subagent: isolates verbose discovery output, returns summaries to preserve main context

**Key Skills:**
- Plan mode for: microservice restructuring, library migrations (45+ files), architectural decisions
- Direct execution for: single-file bug fix with clear stack trace, adding one validation check
- Use `Explore` for verbose discovery phases to prevent context window exhaustion
- Combine: plan mode for investigation + direct execution for implementation

**📁 Folder:** `domain_3_claude_code/04_plan_mode_vs_direct/`

---

### Task 3.5 – Apply iterative refinement techniques for progressive improvement

**Core Knowledge:**
- Concrete input/output examples: most effective for consistent transformations
- Test-driven iteration: write tests first, iterate by sharing failures
- Interview pattern: Claude asks questions to surface unconsidered aspects
- All interacting issues in one message; sequential for independent issues

**Key Skills:**
- Provide 2-3 concrete I/O examples when natural language descriptions are inconsistent
- Write test suites before implementation, iterate using test failures
- Use interview pattern in unfamiliar domains
- Address interacting issues together; fix independent issues sequentially

**📁 Folder:** `domain_3_claude_code/05_iterative_refinement/`

---

### Task 3.6 – Integrate Claude Code into CI/CD pipelines

**Core Knowledge:**
- `-p` / `--print` flag: non-interactive mode for automated pipelines
- `--output-format json` + `--json-schema`: machine-parseable structured output for CI
- CLAUDE.md provides project context (testing standards, review criteria) to CI-invoked Claude Code
- Same session that generated code is **less effective** at reviewing its own changes

**Key Skills:**
- Use `-p` flag to prevent interactive input hangs in CI
- `--output-format json --json-schema` for inline PR comment posting
- Include prior review findings in context when re-running (report only new/unaddressed issues)
- Provide existing test files to avoid duplicate test generation
- Document standards in CLAUDE.md to improve CI output quality

**📁 Folder:** `domain_3_claude_code/06_cicd_integration/`

---

## Domain 4: Prompt Engineering & Structured Output (20%)

### Task 4.1 – Design prompts with explicit criteria to reduce false positives

**Core Knowledge:**
- Explicit criteria over vague instructions (specific categories vs "be conservative")
- General instructions like "only report high-confidence" don't improve precision
- High false positive categories undermine trust in accurate categories

**Key Skills:**
- Write criteria defining which issues to report (bugs, security) vs skip (minor style)
- Temporarily disable high false-positive categories while improving prompts
- Define explicit severity criteria with concrete code examples for consistent classification

**📁 Folder:** `domain_4_prompt_engineering/01_explicit_criteria/`

---

### Task 4.2 – Apply few-shot prompting for output consistency

**Core Knowledge:**
- Few-shot examples: most effective technique for consistently formatted, actionable output
- Demonstrate ambiguous-case handling (tool selection for ambiguous requests)
- Enables generalization to novel patterns beyond pre-specified cases
- Effective for reducing hallucination in extraction tasks

**Key Skills:**
- Create 2-4 targeted examples for ambiguous scenarios showing **reasoning** for choices
- Include examples demonstrating specific output format (location, issue, severity, fix)
- Show examples distinguishing acceptable patterns from genuine issues
- Use examples to demonstrate correct handling of varied document structures

**📁 Folder:** `domain_4_prompt_engineering/02_few_shot_prompting/`

---

### Task 4.3 – Enforce structured output using tool use and JSON schemas

**Core Knowledge:**
- `tool_use` with JSON schemas: most reliable approach, eliminates JSON syntax errors
- `tool_choice` distinction: `"auto"` (may return text), `"any"` (must call a tool), forced (specific tool)
- Strict schemas eliminate syntax errors but NOT semantic errors (values in wrong fields, sums don't match)
- Schema design: required vs optional, `enum` + `"other"` + detail string for extensible categories

**Key Skills:**
- Define extraction tools with JSON schemas; extract from `tool_use` response
- `tool_choice: "any"` when document type is unknown
- Force specific tool with `tool_choice: {"type": "tool", "name": "extract_metadata"}`
- Make fields optional/nullable when source may not contain the info (prevents fabrication)
- Add `"unclear"` enum values and `"other"` + detail fields for extensible categorization

**📁 Folder:** `domain_4_prompt_engineering/03_structured_output/`

---

### Task 4.4 – Implement validation, retry, and feedback loops for extraction quality

**Core Knowledge:**
- Retry-with-error-feedback: append specific validation errors to prompt on retry
- Retries ineffective when information is **absent** from source (vs format/structural errors)
- `detected_pattern` field tracks which code constructs trigger findings
- Semantic validation errors vs schema syntax errors (eliminated by tool use)

**Key Skills:**
- Follow-up requests include: original doc + failed extraction + specific validation errors
- Identify when retry will succeed (format mismatch) vs fail (info absent from source)
- Add `detected_pattern` fields to enable false positive pattern analysis
- Design self-correction flows: `calculated_total` vs `stated_total`, `conflict_detected` booleans

**📁 Folder:** `domain_4_prompt_engineering/04_validation_retry/`

---

### Task 4.5 – Design efficient batch processing strategies

**Core Knowledge:**
- Message Batches API: 50% cost savings, up to 24-hour window, no guaranteed latency SLA
- Appropriate for: overnight reports, weekly audits, nightly test generation
- Inappropriate for: blocking workflows (pre-merge checks)
- Does NOT support multi-turn tool calling within a single request
- `custom_id` fields for correlating request/response pairs

**Key Skills:**
- Match API to latency requirements: synchronous for blocking, batch for overnight
- Calculate batch submission frequency based on SLA constraints
- Handle failures: resubmit only failed docs by `custom_id` with modifications
- Prompt refinement on sample set before large-volume batch submission

**📁 Folder:** `domain_4_prompt_engineering/05_batch_processing/`

---

### Task 4.6 – Design multi-instance and multi-pass review architectures

**Core Knowledge:**
- Self-review limitation: model retains reasoning context → less likely to question own decisions
- Independent review instances (no prior reasoning) more effective than self-review
- Multi-pass: per-file local analysis + separate cross-file integration passes

**Key Skills:**
- Use second independent Claude instance to review generated code
- Split large multi-file reviews: focused per-file passes + integration passes for cross-file data flow
- Run verification passes where model self-reports confidence per finding

**📁 Folder:** `domain_4_prompt_engineering/06_multi_instance_review/`

---

## Domain 5: Context Management & Reliability (15%)

### Task 5.1 – Manage conversation context across long interactions

**Core Knowledge:**
- Progressive summarization risks: loses numerical values, dates, customer-stated expectations
- "Lost in the middle" effect: models process beginning and end reliably, middle sections may be omitted
- Tool results accumulate and consume tokens disproportionately to their relevance
- Must pass complete conversation history in all subsequent API requests

**Key Skills:**
- Extract transactional facts (amounts, dates, order numbers) into persistent "case facts" block
- Trim verbose tool outputs to only relevant fields before they accumulate
- Place key findings summaries at the **beginning** of aggregated inputs
- Require subagents to include metadata in structured outputs for downstream synthesis

**📁 Folder:** `domain_5_context_management/01_conversation_context/`

---

### Task 5.2 – Design effective escalation and ambiguity resolution patterns

**Core Knowledge:**
- Appropriate triggers: customer requests human, policy exceptions/gaps, inability to progress
- Sentiment-based escalation and self-reported confidence scores are **unreliable** complexity proxies
- Multiple customer matches → request additional identifiers, don't use heuristic selection

**Key Skills:**
- Add explicit escalation criteria with few-shot examples to system prompt
- Honor explicit customer requests for human agents **immediately** without attempting investigation
- Acknowledge frustration while offering resolution; escalate only if customer reiterates
- Escalate when policy is ambiguous or silent on the specific request
- Ask for additional identifiers when tool returns multiple matches

**📁 Folder:** `domain_5_context_management/02_escalation_patterns/`

---

### Task 5.3 – Implement error propagation strategies across multi-agent systems

**Core Knowledge:**
- Structured error context enables intelligent coordinator recovery decisions
- Access failures (timeouts) vs valid empty results (no matches) must be distinguished
- Generic statuses ("search unavailable") hide valuable context
- Both silent suppression and full workflow termination on single failures are anti-patterns

**Key Skills:**
- Return: failure type + attempted query + partial results + potential alternatives
- Distinguish access failures from valid empty results
- Subagents implement local recovery; propagate only unresolvable errors to coordinator
- Structure synthesis output with coverage annotations (well-supported vs gap areas)

**📁 Folder:** `domain_5_context_management/03_error_propagation/`

---

### Task 5.4 – Manage context effectively in large codebase exploration

**Core Knowledge:**
- Context degradation: model gives inconsistent answers, references "typical patterns" vs specific findings
- Scratchpad files persist key findings across context boundaries
- Subagent delegation isolates verbose exploration output
- Structured state persistence for crash recovery (manifests)

**Key Skills:**
- Spawn subagents for specific questions while main agent preserves high-level coordination
- Maintain scratchpad files recording key findings for reference in subsequent questions
- Summarize findings before spawning next-phase subagents
- Design crash recovery: agents export state manifests; coordinator loads on resume
- Use `/compact` during extended exploration sessions

**📁 Folder:** `domain_5_context_management/04_codebase_exploration/`

---

### Task 5.5 – Design human review workflows and confidence calibration

**Core Knowledge:**
- Aggregate accuracy (97% overall) may mask poor performance on specific document types
- Stratified random sampling for measuring error rates in high-confidence extractions
- Field-level confidence scores calibrated using labeled validation sets
- Validate by document type and field segment before automating

**Key Skills:**
- Implement stratified random sampling of high-confidence extractions
- Analyze accuracy by document type and field before reducing human review
- Output field-level confidence scores; calibrate thresholds with labeled validation sets
- Route low-confidence and ambiguous/contradictory extractions to human review

**📁 Folder:** `domain_5_context_management/05_human_review/`

---

### Task 5.6 – Preserve information provenance and handle uncertainty in multi-source synthesis

**Core Knowledge:**
- Source attribution is lost during summarization when findings are compressed without claim-source mappings
- Synthesis agent must preserve and merge claim-source mappings when combining findings
- Conflicting statistics: annotate conflicts with source attribution, don't arbitrarily select one value
- Temporal data: require publication/collection dates to prevent temporal differences appearing as contradictions

**Key Skills:**
- Require subagents to output structured claim-source mappings (URLs, names, excerpts)
- Structure reports to distinguish well-established findings from contested ones
- Complete analysis with conflicting values **included and annotated** — coordinator decides reconciliation
- Require publication dates in structured outputs
- Render content types appropriately: financial data as tables, news as prose, technical as lists

**📁 Folder:** `domain_5_context_management/06_information_provenance/`

---

## ✅ Exam Anti-Patterns to Know

| Anti-Pattern | Why It Fails | Correct Approach |
|---|---|---|
| Parsing natural language to detect loop termination | Unreliable, brittle | Check `stop_reason == "end_turn"` |
| Arbitrary iteration cap as primary stopping mechanism | May terminate prematurely | Use `stop_reason` as primary signal |
| Passing full coordinator context to subagents | Context bloat, distraction | Pass only task-relevant context |
| Subagent-to-subagent direct communication | Violates hub-and-spoke | Route through coordinator |
| Generic error messages ("Operation failed") | Prevents intelligent recovery | Return structured error metadata |
| Prompt-only enforcement for critical business rules | Non-zero failure rate | Use programmatic hooks/gates |
| Over-decomposition (8+ tiny tasks) | Context loss, bottleneck | 3-4 coherent, balanced tasks |
| Sentiment-based escalation | Doesn't correlate with complexity | Use explicit categorical criteria |
| Same session reviews its own generated code | Reasoning context bias | Use independent review instance |
| `tool_choice: "auto"` for required extraction | May return text instead | Use `"any"` or force specific tool |
| Required fields when source data may be absent | Model fabricates values | Use optional/nullable fields |
| Batch API for pre-merge blocking checks | Up to 24-hour latency | Use synchronous API for blocking |
| Global large CLAUDE.md for all conventions | All conventions always loaded | Use path-scoped rules in `.claude/rules/` |

---

## 🛠️ Technologies & APIs Quick Reference

| Technology | Key Concepts |
|---|---|
| **Claude Agent SDK** | Agent definitions, agentic loops, `stop_reason`, hooks (`PostToolUse`), `Task` tool, `allowedTools` |
| **MCP** | Servers, tools, resources, `isError` flag, `.mcp.json`, env var expansion |
| **Claude Code** | CLAUDE.md hierarchy, `.claude/rules/`, `.claude/commands/`, `.claude/skills/`, plan mode, `/compact`, `--resume`, `fork_session` |
| **Claude Code CLI** | `-p`/`--print`, `--output-format json`, `--json-schema` |
| **Claude API** | `tool_use`, `tool_choice` (`"auto"`, `"any"`, forced), `stop_reason` (`"tool_use"`, `"end_turn"`), `max_tokens`, system prompts |
| **Message Batches API** | 50% savings, 24h window, `custom_id`, no multi-turn tool calling |
| **JSON Schema** | Required/optional, nullable, `enum` + `"other"`, strict mode |

---

## 📖 Out-of-Scope (Won't Appear on Exam)

- Fine-tuning or training custom models
- Claude API authentication, billing, account management
- MCP server infrastructure/deployment
- Claude's internal architecture or training process
- Constitutional AI, RLHF methodologies
- Embedding models or vector database details
- Computer use (browser/desktop automation)
- Vision/image analysis capabilities
- Streaming API implementation
- Rate limiting, quotas, pricing calculations
- OAuth, API key rotation
- Specific cloud provider configurations (AWS, GCP, Azure)
- Prompt caching implementation details
- Token counting algorithms

---

## 🚀 Quick Start Learning Path

**Week 1 — Foundation (Highest Weight Domains)**
- Read Domain 1 (agentic loops + multi-agent orchestration) — 27%
- Read Domain 3 (Claude Code configuration) — 20%

**Week 2 — Core Skills**
- Read Domain 4 (prompt engineering + structured output) — 20%
- Read Domain 2 (tool design + MCP) — 18%

**Week 3 — Reliability + Practice**
- Read Domain 5 (context management) — 15%
- Work through all 12 sample questions in the exam guide
- Complete all 4 preparation exercises

---

## 📝 Sample Question Analysis

The exam tests **practical judgment**, not memorization. Key patterns from sample questions:

**Q7 (Multi-Agent Research)** — "Impact of AI on creative industries" only covered visual arts because the coordinator decomposed "creative industries" into only visual arts subtasks. **Root cause: coordinator's narrow task decomposition**, not downstream subagent failures.

**Q1 (Customer Support)** — Agent skips `get_customer` in 12% of cases. **Correct fix: programmatic prerequisite** blocking downstream calls until verification completes — not prompt instructions or few-shot examples.

**Q10 (CI/CD)** — Pipeline hangs. **Correct fix: `-p` flag** for non-interactive mode. `CLAUDE_HEADLESS=true` and `--batch` don't exist.

**Q11 (Batch API)** — Pre-merge checks must stay synchronous; only overnight reports suit batch API.

---

*Repository maintained alongside active exam preparation. Each folder contains detailed notes, code examples, and practice exercises aligned to the corresponding Task Statement.*
