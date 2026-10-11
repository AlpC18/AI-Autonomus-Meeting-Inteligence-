
# AI Guidelines for (Proje Adı) Development

> [!IMPORTANT]
> All AI assistants contributing to this repository MUST read and adhere to these guidelines before proposing or executing any code changes.

## 1. Zero Unsafe Policy
Memory safety is the highest priority in (Proje Adı).
- **Rule**: Do NOT use `unsafe` blocks under any circumstances.
- **Rationale**: Prefer safe Rust abstractions over bypassing the borrow checker.

## 2. Mandatory Documentation (///)
- Every new `pub mod`, `pub struct`, `pub enum`, `pub trait`, and `pub fn` MUST include `///` documentation.
- Documentation should explain purpose, responsibility, constraints, and usage.

## 3. Persistent Knowledge Base (.md)
- Update `knowledge/history/engine_features.md` for every feature.
- Update `knowledge/history/bug_fixes.md` for every bug fix.
- Keep all related documentation in `knowledge/` synchronized.
- Read the relevant documentation before starting work.

## 4. Modular Responsibility
- Keep `main.rs` thin.
- Delegate logic to dedicated modules.
- Avoid God Objects.

## 5. Verification Standards
- Run `cargo check` when repository access is available.
- Avoid placeholders whenever possible.

## 6. Strict File Boundary Enforcement
- Preserve existing module boundaries.
- Do not merge unrelated modules.

## 7. Scope Isolation Rule
- Only modify the requested files/modules.
- Do not expand scope without approval.

## 8. No Implicit Refactor Rule
- Refactor only when explicitly requested.

## 9. Architecture Preservation Rule
- Preserve the existing architecture unless instructed otherwise.

## 10. Small Function Rule
- Prefer functions under ~100 lines.
- Split large responsibilities into helpers.

## 11. Multi-Module Coordination Rule
- Analyze → Plan → Wait for approval → Implement.

## 12. Anti-God Object Rule
- Keep structs focused on one responsibility.

## 13. AI Behavior Lock
- Never assume missing context.
- Ask when uncertain.

## 14. Single Responsibility Per File
- Every `.rs` file should solve exactly one problem.

## 15. Memory Bank Rule
Read and maintain:
- projectbrief.md
- productContext.md
- activeContext.md
- systemPatterns.md
- techContext.md
- progress.md

## 16. Documentation Quality Rule
Documentation should clearly explain purpose, constraints, behavior, and integration.

## 17. Copyright & SPDX Header Rule
Every source file begins with:

```rust
// SPDX-License-Identifier: (License)-only
// Copyright (c) 2026 (Github) / (Project). All rights reserved.
```

## 18. Project Architecture
- Modular First
- Unix Philosophy
- One File, One Job
- One Directory, One Subsystem
- Favor composition over monolithic implementations.
- Split files before ~800 lines.
- Prefer subsystem directories over flat layouts.

## 19. Directory Complexity Rule
- Keep directories cohesive.
- 1–10 files: Ideal
- 10–20: Healthy
- 20–30: Consider subdirectories
- 30+: Reorganize
- Avoid misc/helpers/common dumping grounds.

## 20. Architecture Goals
- Modular
- Predictable
- Scalable
- Self-documenting
- AI-friendly
- Easy to navigate
- Long-term maintainable

Every directory represents one subsystem.
Every file has one responsibility.
Every function has one purpose.
