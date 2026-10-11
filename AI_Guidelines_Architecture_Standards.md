# AI Guidelines & Architecture Standards for [PROJECT_NAME]

> [!IMPORTANT]
> All AI assistants and developers contributing to this repository MUST read and strictly adhere to these guidelines before proposing or executing any code changes. These are not suggestions; they are strict project boundaries. Any deviation will result in rejected code.

**Repository Owner:** AlpC18  
**License:** MIT  
**Last Updated:** 2026  
**Status:** ACTIVE & ENFORCED

---

## Architecture and Operational Limits Summary

The following table defines the hard limits of the project structure. Exceeding these limits requires immediate refactoring.

| Criterion | Acceptable Limit | Critical Limit (Requires Refactor) | Violation (Code Rejected) |
| :--- | :--- | :--- | :--- |
| **Function Length** | < 50 lines | ~100 lines | > 100 lines (Must be split) |
| **File Length** | 200 - 400 lines | ~800 lines | > 800 lines (New module required) |
| **Directory Density** | 1 - 10 files | 10 - 20 files | > 30 files (Subdirectories required)|
| **`unsafe` Usage** | 0 (Zero) | Strictly Prohibited | System-wide ban |

---

## Core Guidelines

### 1. Zero Unsafe Policy
Memory safety is the absolute highest priority in [PROJECT_NAME].

* **Rule:** Do NOT use `unsafe` blocks under ANY circumstances.
* **Rationale:** Always prefer safe Rust abstractions over bypassing the borrow checker. Security and stability are never to be sacrificed for convenience.

---

### 2. Mandatory Documentation
Code explains how; documentation explains why. 

* **Rule:** Every new `pub mod`, `pub struct`, `pub enum`, `pub trait`, and `pub fn` MUST include `///` documentation headers.
* **Execution:** Documentation must clearly explain the purpose, responsibility, constraints, and intended usage of the component.
* **Example:**
  ```rust
  /// Validates user authentication token and returns decoded claims.
  /// 
  /// # Arguments
  /// * `token` - JWT token string to validate
  /// 
  /// # Returns
  /// `Ok(Claims)` if token is valid, `Err(TokenError)` if invalid or expired
  /// 
  /// # Panics
  /// Does not panic. All errors are returned as `Result`.
  pub fn validate_token(token: &str) -> Result<Claims, TokenError> {
      // implementation
  }
  ```

---

### 3. Persistent Knowledge Base
The system's memory must remain synchronized with the codebase.

* **Rule:** Update `docs/history/features.md` for every new feature. Update `docs/history/bug_fixes.md` for every bug fix.
* **Execution:** Keep all related documentation in the `docs/` directory synchronized. You must read the relevant documentation before initiating any work.
* **Files to maintain:**
  - `docs/projectbrief.md` - Project overview and goals
  - `docs/productContext.md` - Product requirements and scope
  - `docs/activeContext.md` - Current work in progress
  - `docs/systemPatterns.md` - Design patterns and architectural decisions
  - `docs/techContext.md` - Technology stack and dependencies
  - `docs/progress.md` - Development progress tracking

---

### 4. Modular Responsibility
Monolithic structures and God Objects are strictly forbidden.

* **Rule:** Keep `main.rs` extremely thin. It is a router, not a processor.
* **Execution:** Delegate logic to dedicated, isolated modules. 
* **Anti-Pattern:**
  ```rust
  // ❌ BAD: main.rs doing everything
  fn main() {
      let user = User::new();
      let validated = validate_user(&user);
      let response = handle_request(validated);
      let serialized = serde_json::to_string(&response);
      // ... 200 more lines
  }
  ```
* **Pattern:**
  ```rust
  // ✅ GOOD: main.rs delegates to modules
  fn main() {
      let app = router::setup();
      app.run();
  }
  ```

---

### 5. Verification Standards
Untested code is broken code.

* **Rule:** Always run `cargo check` and `cargo clippy` when repository access is available to verify changes.
* **Execution:** Avoid writing placeholders (e.g., "code goes here"). Deliver complete, compilable solutions.
* **Commands:**
  ```bash
  cargo check
  cargo clippy -- -D warnings
  cargo test
  ```

---

### 6. Strict File Boundary Enforcement
Do not break the existing structural hierarchy.

* **Rule:** Preserve existing module boundaries at all times.
* **Execution:** Do not merge unrelated modules into single files for the sake of convenience.

---

### 7. Scope Isolation Rule
Focus exclusively on the requested task.

* **Rule:** Only modify the explicitly requested files or modules.
* **Execution:** Do not expand the scope of your work or modify adjacent code without explicit user approval.

---

### 8. No Implicit Refactor Rule
Do not fix what was not requested.

* **Rule:** Refactor existing code ONLY when explicitly instructed to do so.
* **Execution:** While fixing a bug or adding a feature, leave unrelated legacy code in the same file untouched.

---

### 9. Architecture Preservation Rule
System architecture supersedes individual design choices.

* **Rule:** Preserve the existing architecture, design patterns, and file layouts unless instructed otherwise.
* **When to deviate:** Only after explicit discussion and approval with project maintainers.

---

### 10. Small Function Rule
Unreadable code is unmaintainable code.

* **Rule:** Keep functions ideally under 50 lines, and strictly under 100 lines.
* **Execution:** Split large responsibilities and complex logic into smaller, single-purpose helper functions.
* **Example:**
  ```rust
  // ❌ BAD: 120 lines, multiple responsibilities
  fn process_user_data(input: &str) -> Result<User> {
      // parsing
      // validation
      // transformation
      // database insertion
      // error logging
  }
  
  // ✅ GOOD: Smaller, focused functions
  fn parse_user_data(input: &str) -> Result<RawUser> { }
  fn validate_user(user: &RawUser) -> Result<ValidatedUser> { }
  fn transform_user(user: ValidatedUser) -> User { }
  ```

---

### 11. Multi-Module Coordination Rule
Do not execute blind cross-system changes.

* **Rule:** Analyze → Plan → Wait for approval → Implement.
* **Execution:** Before making cross-cutting changes that affect multiple modules, outline your architectural plan and wait for confirmation.

---

### 12. Anti-God Object Rule
Components that do everything, do nothing well.

* **Rule:** Keep structs and enums intensely focused on a single responsibility. Prevent data bloating.
* **Example:**
  ```rust
  // ❌ BAD: God Object
  struct User {
      id: String,
      email: String,
      password: String,
      posts: Vec<Post>,
      comments: Vec<Comment>,
      followers: Vec<User>,
      notifications: Vec<Notification>,
      preferences: UserPreferences,
      // ... 30 more fields
  }
  
  // ✅ GOOD: Separated concerns
  struct User {
      id: String,
      email: String,
      password_hash: String,
  }
  
  struct UserProfile {
      user_id: String,
      bio: String,
      avatar: Option<String>,
  }
  
  struct UserRelations {
      user_id: String,
      followers: Vec<String>,
      following: Vec<String>,
  }
  ```

---

### 13. AI Behavior Lock
Assumptions breed critical failures.

* **Rule:** Never assume missing context or guess intent.
* **Execution:** If requirements are ambiguous, immediately stop generation and ask clarifying questions.

---

### 14. Single Responsibility Per File
Files are not dumping grounds.

* **Rule:** Every `.rs` file must solve exactly one specific problem or represent one domain concept.
* **File Organization:**
  ```
  src/
  ├── main.rs              # Entry point only
  ├── lib.rs               # Library root
  ├── models/
  │   ├── user.rs          # User domain
  │   ├── post.rs          # Post domain
  │   └── comment.rs       # Comment domain
  ├── services/
  │   ├── auth.rs          # Authentication logic
  │   ├── user_service.rs  # User operations
  │   └── post_service.rs  # Post operations
  ├── handlers/
  │   ├── auth_handler.rs  # Auth endpoints
  │   └── post_handler.rs  # Post endpoints
  └── utils/
      ├── logger.rs        # Logging utilities
      └── validators.rs    # Validation helpers
  ```

---

### 15. Memory Bank Rule
You must understand the project's soul before altering its body.

* **Rule:** Read, maintain, and reference the following core documents for every decision:
  - `docs/projectbrief.md`
  - `docs/productContext.md`
  - `docs/activeContext.md`
  - `docs/systemPatterns.md`
  - `docs/techContext.md`
  - `docs/progress.md`
* **Execution:** These documents are the single source of truth. When in doubt, consult them first.

---

### 16. Documentation Quality Rule
Documentation must be engineered, not just written.

* **Rule:** Comments must be clear, technical, and precise. They must explain constraints, edge cases, and how the component integrates with the broader system.
* **Comment Levels:**
  ```rust
  /// PUBLIC API: Explain what this does and why
  /// Used by: module_name, other_module
  /// Constraints: Input must be UTF-8 encoded
  pub fn public_function() { }
  
  // Internal comment: Explain the "why" of implementation
  // This approach is chosen because...
  fn internal_helper() { }
  ```

---

### 17. Copyright & SPDX Header Rule
Legal and licensing standards are non-negotiable.

* **Rule:** Every single source file MUST begin with the exact following header:
  ```rust
  // SPDX-License-Identifier: MIT
  // Copyright (c) 2026 AlpC18 / [PROJECT_NAME]. All rights reserved.
  ```
* **Example for multiple files:**
  ```rust
  // SPDX-License-Identifier: MIT
  // Copyright (c) 2026 AlpC18 / KosovaTicket. All rights reserved.
  
  //! User authentication module.
  ```

---

### 18. Project Architecture (Unix Philosophy)
The foundational design vision.

* **Rule:** Modular First. Favor composition over monolithic implementations.
* **Execution:** 
  - One File = One Job
  - One Directory = One Subsystem
  - Split files before they reach ~800 lines
  - Prefer creating clear subsystem directories over flat, chaotic file layouts

---

### 19. Directory Complexity Rule
Navigation must be fast and predictable.

* **Rule:** Keep directories cohesive. Do not create vague dumping grounds like `misc/`, `helpers/`, or `common/`.
* **Capacity Limits:**
  - **1–10 files:** Ideal ✅
  - **10–20 files:** Healthy ✅
  - **20–30 files:** Consider subdirectories ⚠️
  - **30+ files:** Hard refactor/Reorganize required 🚫

* **Example structure (good):**
  ```
  src/
  ├── auth/          # 8 files - One subsystem
  ├── posts/         # 6 files - One subsystem
  ├── users/         # 5 files - One subsystem
  └── shared/        # 4 files - Shared utilities only
  ```

* **Example structure (bad):**
  ```
  src/
  ├── helpers/       # 45 vague files - Refactor needed
  ├── utils/         # 32 unclear files - Subsystem unknown
  └── common/        # 28 dumping ground files - Reorganize
  ```

---

### 20. Architecture Goals
The ultimate standard this repository must maintain:

1. **Modular:** Components can be replaced or isolated.
2. **Predictable:** Any developer (or AI) can guess where a file belongs.
3. **Scalable:** Grows without becoming sluggish or tangled.
4. **Self-documenting:** Naming conventions explain the functionality.
5. **AI-friendly:** Small, highly focused context windows.
6. **Easy to navigate:** Flawless hierarchical structure.
7. **Long-term maintainable:** Zero tolerance for accumulating technical debt.

---

## Enforcement & Review Process

### Before Submitting Code
- ✅ Run `cargo check` and `cargo clippy`
- ✅ Add/update documentation headers
- ✅ Verify function length < 100 lines
- ✅ Ensure file size < 800 lines
- ✅ Check SPDX headers on new files
- ✅ Update relevant knowledge base files

### During Code Review
- All guidelines will be strictly enforced
- Non-compliance = Request for Changes
- Multiple violations = Rejected PR

### Exceptions
- No exceptions without explicit maintainer approval
- Document any deviations in the PR description
- Requires discussion and consensus

---

## Scalable Enforcement Rules by Project Size

> **Core Principle:** Guidelines scale with project complexity. A 2K-line utility doesn't need the same rigor as a 40K-line backend. Rules adapt to prevent over-engineering small projects while maintaining discipline in large ones.

### Size Categories & Rules

| Category | LOC Range | Function Limit | File Limit | Dir Density | Unsafe | Tests | Refactor | CI |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Micro** | <5K | ≤200 | ≤1500 | ≤50 files | Allowed (2-3) | Optional | As-needed | Warnings |
| **Small** | 5–15K | ≤150 | ≤1200 | ≤40 files | Minimal (1-2) | Core paths | Per 10K LOC | Soft block |
| **Medium** | 15–40K | ≤100 | ≤800 | ≤30 files | Banned (0) | Core + edge cases | Per 5K LOC | Hard block |
| **Large** | 40K+ | ≤75 | ≤500 | ≤20 files | Banned (0) | 80%+ coverage | Continuous | Hard block |

**Determine your category:**
```bash
# Count LOC
tokei src/
# or
find src -name "*.rs" -exec wc -l {} + | tail -1
```

---

### Detailed Rules by Category

#### **Micro Projects (<5K LOC)**
*Examples: CLI tools, config parsers, single-purpose utilities*

- **Philosophy:** Keep it simple. Over-engineering wastes time.
- **Function limit:** ≤200 lines (can be messy if needed)
- **File limit:** ≤1500 lines (one file is fine)
- **Directory:** No real structure needed; all in `src/` or one `src/module/`
- **Documentation:** Public APIs only; private code can be sparse
- **Unsafe:** Allowed sparingly (2-3 blocks OK if justified)
- **Tests:** Optional; manual testing is fine
- **CI:** Warnings only; don't fail builds
- **Refactoring:** "As-needed" — only when you feel pain

**Minimal .git/hooks/pre-commit:**
```bash
#!/bin/bash
cargo check
cargo clippy
```

---

#### **Small Projects (5–15K LOC)**
*Examples: API wrappers, DB clients, SDK modules*

- **Philosophy:** Start thinking about structure, but stay flexible.
- **Function limit:** ≤150 lines
- **File limit:** ≤1200 lines
- **Directory:** Start using `src/modules/` pattern; ≤40 files per dir
- **Documentation:** All public APIs documented; internal can be light
- **Unsafe:** Minimal (1-2 blocks max); must be documented
- **Tests:** Core paths covered; mocking encouraged
- **CI:** Soft block — tests must pass, but lint warnings don't block merge
- **Refactoring:** Every 10K LOC added, spend 1-2 days refactoring

**Pre-commit enforcement:**
```bash
#!/bin/bash
set -e
cargo check
cargo clippy -- -W warnings  # Warnings only, not -D
# Check for obvious violations
if grep -r "unsafe" src/ --include="*.rs"; then
  echo "⚠️  Unsafe blocks found — review carefully"
  # Still allows merge, just warns
fi
```

---

#### **Medium Projects (15–40K LOC)**
*Examples: KosovaTicket, Wellness House, web app backends*

- **Philosophy:** Strict discipline required. Multiple teams possible.
- **Function limit:** ≤100 lines (hard limit)
- **File limit:** ≤800 lines (hard limit)
- **Directory:** Clear domain structure; ≤30 files per dir
- **Documentation:** All public items `/// documented`; architecture docs required
- **Unsafe:** Completely banned (0 blocks)
- **Tests:** Core + edge cases; 60%+ coverage
- **CI:** Hard block — all checks must pass
- **Refactoring:** Every 5K LOC added, schedule 1-week sprint

**Pre-commit enforcement (strict):**
```bash
#!/bin/bash
set -e
# Hard stops
cargo check
cargo clippy -- -D warnings  # Errors on warnings

# File size check
python3 - <<'EOF'
import os
for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.rs'):
            path = os.path.join(root, file)
            with open(path) as f:
                lines = len(f.readlines())
            if lines > 800:
                print(f"❌ {path}: {lines} lines (exceeds 800)")
                exit(1)
EOF

# Unsafe check
if grep -r "unsafe" src/ --include="*.rs"; then
    echo "❌ Unsafe blocks not allowed"
    exit 1
fi

echo "✅ All checks passed"
```

---

#### **Large Projects (40K+ LOC)**
*Examples: Enterprise SaaS, microservices architectures, distributed systems*

- **Philosophy:** Maximum rigor. Every violation scales to 100+ lines of impact.
- **Function limit:** ≤75 lines (even stricter)
- **File limit:** ≤500 lines (small, focused files only)
- **Directory:** Explicit subsystem boundaries; ≤20 files per dir
- **Documentation:** All items documented, including private; ADRs required for decisions
- **Unsafe:** Absolutely banned (0 blocks, no exceptions)
- **Tests:** 80%+ coverage; mutation testing encouraged
- **CI:** Hard block + additional checks (security scan, performance regression)
- **Refactoring:** Continuous; every PR should include micro-refactors

**Pre-commit + CI (maximum enforcement):**
```bash
# Pre-commit (local gate)
cargo check
cargo clippy -- -D warnings
cargo test --lib
cargo test --doc

# File/function analysis
python3 scripts/analyze_code.py --strict

# GitHub Actions (remote gate)
- Run security scan (cargo-audit)
- Run performance benchmark
- Check coverage regression
- Verify documentation coverage
```

---

### Transition Checklist

**Your project is currently ~38K LOC → Medium/Large category**

**If you want to relax rules (move to Small):**
- ❌ Not recommended — you'd lose discipline
- You'd need to **reduce** to 5-15K first
- Option: Split into multiple Small projects instead

**If you want to stay at Medium (recommended):**
```
✅ Apply Medium rules strictly
✅ Functions ≤100 lines
✅ Files ≤800 lines
✅ Dirs ≤30 files
✅ 0 unsafe blocks
✅ Document everything public
✅ 60%+ test coverage
✅ Refactor every 5K LOC
```

**If you want to move to Large (advanced):**
```
✅ Already above 40K — you're there!
✅ Tighten to Large rules:
   - Functions ≤75 lines
   - Files ≤500 lines
   - Dirs ≤20 files
   - 80%+ test coverage
   - Continuous refactoring
✅ Add security + perf checks
```

---

### How to Check Your Current Category

```bash
# Total LOC
tokei src/ | grep "Rust" | awk '{print $4}' # Shows total lines

# Largest files
find src -name "*.rs" -exec wc -l {} \; | sort -rn | head -5

# File count
find src -name "*.rs" | wc -l

# Largest directories
for d in src/*/; do
  count=$(find "$d" -name "*.rs" | wc -l)
  echo "$d: $count files"
done | sort -t: -k2 -rn | head -5
```

**Result: You're at ~38K LOC → Medium category minimum, possibly Large**

---

### Adjusting Rules: The Config File Approach

Create `Codeguide.toml` in your project root:

```toml
[project]
name = "KosovaTicket"
loc_estimate = 38000

# Auto-select category (override with [rules])
[rules]
# Manual override if needed
category = "medium"  # or "large"

[limits]
function_lines = 100
file_lines = 800
dir_files = 30
unsafe_blocks = 0

[enforcement]
ci_mode = "hard_block"  # or "soft_block", "warnings"
test_coverage_required = 0.6  # 60%
unsafe_allowed = false
```

Use in CI:
```bash
# Load limits from Codeguide.toml
python3 scripts/validate.py --config Codeguide.toml
```

---

## Code Quality Automation & Enforcement

### 1. Detection Tools (Identify Violations)

#### **Measure Your Codebase**
```bash
# Install tokei (faster than cloc, Rust-optimized)
cargo install tokei

# Run analysis
tokei src/

# Output: file count, LOC per language, blank lines
# Example output:
#  Language            Files  Lines    Code    Comments
#  Rust                  34   38042   28500    4200
#  JSON                   3    450      400      0
```

#### **Find Bloated Files (>800 lines)**
```bash
# Bash one-liner: find all .rs files exceeding 800 lines
find src -name "*.rs" -exec sh -c 'lines=$(wc -l < "$1"); if [ "$lines" -gt 800 ]; then echo "$1: $lines lines"; fi' _ {} \;

# Python script: more detailed report
#!/usr/bin/env python3
import os
import sys

LIMIT = 800
violations = []

for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.rs'):
            path = os.path.join(root, file)
            with open(path) as f:
                lines = len(f.readlines())
            if lines > LIMIT:
                violations.append((path, lines))

violations.sort(key=lambda x: x[1], reverse=True)
print(f"\n❌ Files exceeding {LIMIT} lines:")
for path, count in violations:
    percent = (count - LIMIT) / LIMIT * 100
    print(f"  {path}: {count} lines ({percent:+.0f}%)")
print(f"\nTotal violations: {len(violations)}")
sys.exit(1 if violations else 0)
```

#### **Find Bloated Functions (>100 lines)**
```bash
# Rust-specific: extract function definitions and line counts
# Uses regex to find "fn " and count until closing "}"
# (requires manual inspection, but gives a starting point)

# Simple grep approach:
grep -n "^fn " src/**/*.rs | while read line; do
  file="${line%%:*}"
  start="${line##*:}"
  start="${start% *}"
  # Count lines from function start to next top-level item
  # (imperfect but quick)
done

# Better: Use ast-based tools (see Tools section below)
```

#### **Find Bloated Directories (>30 files)**
```bash
# Bash
find src -type d -name "*" | while read dir; do
  count=$(find "$dir" -maxdepth 1 -name "*.rs" | wc -l)
  if [ "$count" -gt 30 ]; then
    echo "❌ $dir: $count files"
  fi
done

# Python (cleaner output)
#!/usr/bin/env python3
import os
from pathlib import Path

LIMIT = 30

for root, dirs, files in os.walk('src'):
    rs_files = [f for f in files if f.endswith('.rs')]
    if len(rs_files) > LIMIT:
        print(f"❌ {root}: {len(rs_files)} files ({len(rs_files)-LIMIT:+d})")
```

#### **Check for `unsafe` Blocks**
```bash
grep -r "unsafe" src/ --include="*.rs" || echo "✅ No unsafe blocks found"

# More detailed: show line numbers and context
grep -rn "unsafe" src/ --include="*.rs" -B2 -A2
```

#### **Check for Missing SPDX Headers**
```bash
#!/bin/bash
# Find .rs files WITHOUT the SPDX header
for file in $(find src -name "*.rs"); do
  if ! head -1 "$file" | grep -q "SPDX-License-Identifier"; then
    echo "❌ $file: Missing SPDX header"
  fi
done
```

#### **Check for Missing Documentation**
```bash
# Find public items without ///
grep -r "pub " src/ --include="*.rs" | grep -v "///" | head -20
```

---

### 2. Automated Enforcement (CI/CD & Hooks)

#### **Pre-commit Hook**
Save as `.git/hooks/pre-commit`:
```bash
#!/bin/bash
set -e

echo "🔍 Running pre-commit checks..."

# Check 1: No unsafe blocks
if grep -r "unsafe" src/ --include="*.rs"; then
    echo "❌ FAIL: unsafe blocks detected"
    exit 1
fi

# Check 2: No files > 800 lines
python3 - <<'EOF'
import os
violations = 0
for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.rs'):
            path = os.path.join(root, file)
            with open(path) as f:
                lines = len(f.readlines())
            if lines > 800:
                print(f"❌ {path}: {lines} lines (exceeds 800)")
                violations += 1
exit(violations)
EOF

# Check 3: Cargo check
cargo check --quiet
cargo clippy -- -D warnings

# Check 4: SPDX headers
python3 - <<'EOF'
import os
missing = 0
for file in os.popen('find src -name "*.rs"').read().strip().split('\n'):
    if file and not open(file).readline().strip().startswith('// SPDX'):
        print(f"❌ {file}: Missing SPDX header")
        missing += 1
exit(missing)
EOF

echo "✅ All checks passed!"
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

#### **GitHub Actions Workflow**
Save as `.github/workflows/code-quality.yml`:
```yaml
name: Code Quality Checks

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable
      
      - name: Check unsafe blocks
        run: |
          if grep -r "unsafe" src/ --include="*.rs"; then
            echo "❌ unsafe blocks detected"
            exit 1
          fi
      
      - name: Check file sizes
        run: |
          python3 - <<'EOF'
          import os
          violations = 0
          for root, dirs, files in os.walk('src'):
              for file in files:
                  if file.endswith('.rs'):
                      path = os.path.join(root, file)
                      with open(path) as f:
                          lines = len(f.readlines())
                      if lines > 800:
                          print(f"❌ {path}: {lines} lines")
                          violations += 1
          if violations:
              print(f"\nFix by splitting files into modules")
              exit(1)
          EOF
      
      - name: Check function sizes
        run: cargo install tokei && tokei src/
      
      - name: Cargo check
        run: cargo check
      
      - name: Clippy
        run: cargo clippy -- -D warnings
      
      - name: Check SPDX headers
        run: |
          python3 - <<'EOF'
          import os
          for file in os.popen('find src -name "*.rs"').read().strip().split('\n'):
              if file and not open(file).readline().startswith('// SPDX'):
                  print(f"❌ {file}")
                  exit(1)
          EOF
```

#### **Metrics Dashboard (Track Over Time)**
```python
# scripts/metrics.py
#!/usr/bin/env python3
import os
import json
from datetime import datetime
from pathlib import Path

OUTPUT_FILE = "docs/metrics.json"

def collect_metrics():
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "files_total": 0,
        "lines_total": 0,
        "unsafe_count": 0,
        "files_over_800": [],
        "dirs_over_30": [],
    }
    
    # Count files and lines
    for root, dirs, files in os.walk('src'):
        rs_files = [f for f in files if f.endswith('.rs')]
        metrics["files_total"] += len(rs_files)
        
        # Check directory density
        if len(rs_files) > 30:
            metrics["dirs_over_30"].append({"path": root, "count": len(rs_files)})
        
        for file in rs_files:
            path = os.path.join(root, file)
            with open(path) as f:
                content = f.read()
                lines = len(content.split('\n'))
                metrics["lines_total"] += lines
                
                # Count unsafe
                metrics["unsafe_count"] += content.count('unsafe')
                
                # Check file size
                if lines > 800:
                    metrics["files_over_800"].append({"path": path, "lines": lines})
    
    # Load history
    history = []
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            history = json.load(f).get("history", [])
    
    history.append(metrics)
    
    # Write report
    with open(OUTPUT_FILE, 'w') as f:
        json.dump({"history": history, "current": metrics}, f, indent=2)
    
    # Print summary
    print(f"\n📊 Metrics as of {metrics['timestamp']}")
    print(f"   Total lines: {metrics['lines_total']}")
    print(f"   Total files: {metrics['files_total']}")
    print(f"   Unsafe blocks: {metrics['unsafe_count']}")
    print(f"   Files >800 LOC: {len(metrics['files_over_800'])}")
    print(f"   Dirs >30 files: {len(metrics['dirs_over_30'])}")
    
    if metrics['files_over_800']:
        print(f"\n   ⚠️  Large files (need refactoring):")
        for item in metrics['files_over_800'][:5]:
            print(f"      {item['path']}: {item['lines']} lines")

if __name__ == "__main__":
    collect_metrics()
```

Run periodically:
```bash
python3 scripts/metrics.py
git add docs/metrics.json
git commit -m "chore: update code quality metrics"
```

---

### 3. IDE Integration (Real-time Warnings)

#### **VS Code Settings (`.vscode/settings.json`)**
```json
{
  "[rust]": {
    "editor.rulers": [100],
    "editor.codeActionsOnSave": {
      "source.fixAll.clippy": true
    }
  },
  "rust-analyzer.checkOnSave.command": "clippy",
  "rust-analyzer.checkOnSave.extraArgs": ["-D", "warnings"]
}
```

#### **Custom Warning: File Size**
VS Code doesn't natively warn on large files, but you can use this extension:
- Install: **File Size** extension
- Shows file size in status bar; manually check when editing large files

---

### 4. Refactoring Workflow

#### **When You Hit a Limit (e.g., 850 lines)**

**Step 1: Identify splittable units**
```rust
// current_file.rs - 850 lines

mod models;          // 120 lines
mod service;         // 250 lines ← TOO BIG
mod handlers;        // 230 lines ← TOO BIG
mod error;           // 50 lines
```

**Step 2: Split large modules**
```
current_file/
├── mod.rs           # Re-exports only
├── models.rs        # Unchanged
├── service/
│   ├── mod.rs       # Main service
│   ├── email.rs     # Email-specific
│   └── webhook.rs   # Webhook-specific
├── handlers/
│   ├── mod.rs
│   ├── auth.rs
│   ├── users.rs
│   └── posts.rs
├── error.rs
```

**Step 3: Update lib.rs**
```rust
pub mod current_file {
    pub use self::models::*;
    pub use self::service::Service;
    pub use self::error::Error;
    
    mod models;
    mod service;
    mod handlers;
    mod error;
}
```

---

### 5. Quick Reference (Updated with Automation)

| Guideline | Check Command | Enforce How | Fix Threshold |
| :--- | :--- | :--- | :--- |
| **Unsafe** | `grep -r "unsafe"` | Pre-commit hook | 0 blocks |
| **Functions** | cargo clippy (custom lint) | CI check | <100 lines |
| **Files** | `python3 scripts/check_files.py` | Pre-commit + CI | <800 lines |
| **Directories** | `python3 scripts/check_dirs.py` | Pre-commit + CI | <30 files |
| **Documentation** | Manual review (for now) | PR review | 100% public items |
| **Headers** | `grep "SPDX"` | Pre-commit | All files |
| **Modules** | Code review | PR review | 1 responsibility |
| **Imports** | `cargo tree --duplicates` | CI check | No cycles |

---

### 6. Continuous Improvement

**Monthly Review (First Friday of each month):**
```bash
# Generate metrics
python3 scripts/metrics.py

# Review trends
cat docs/metrics.json | jq '.history[-5:] | .[] | {date: .timestamp, files_over_800: (.files_over_800 | length)}'

# If trend is ↑ (getting worse), schedule refactoring sprint
```

**Quarterly Refactoring Sprint:**
- Target the 5 largest files
- Goal: get all files <800 lines (Medium) or <500 (Large)
- Allocate 2-3 days per sprint

---

### 7. Updated Quick Reference (Scalable)

**For YOUR project (38K LOC = Medium/Large category):**

| Guideline | Quick Check | Medium Limit | Large Limit |
| :--- | :--- | :--- | :--- |
| Unsafe | `grep -r "unsafe"` | 0 blocks (banned) | 0 blocks (banned) |
| Functions | All < 100 lines | ≤100 lines | ≤75 lines |
| Files | All < 800 lines | ≤800 lines | ≤500 lines |
| Directories | All < 30 files | ≤30 files | ≤20 files |
| Documentation | `/// ...` on all public | All pub items | All + private |
| Headers | SPDX on all files | Required | Required |
| Modules | One per file | One per file | One per file |
| Imports | No circular deps | No cycles | No cycles |
| Tests | Core paths | 60%+ coverage | 80%+ coverage |
| Refactoring | Per 5K LOC | Every 5K LOC sprint | Continuous |
| CI | Hard block | Hard block | Hard block |

**If your project will stay small (<5K LOC):**
- Use **Micro** rules: relax to ≤200 line functions, ≤1500 line files
- CI: warnings only
- Refactoring: as-needed

**If your project grows beyond 40K (→ Large):**
- Tighten to **Large** rules
- Add security + performance checks
- Implement continuous refactoring
- Target 80%+ test coverage

---

**Implementation Priority:**
1. ✅ **Week 1:** Determine your category (run tokei); update Codeguide.toml
2. ✅ **Week 2:** Add pre-commit hooks (category-appropriate)
3. ✅ **Week 3:** Add GitHub Actions (category-appropriate CI)
4. ✅ **Week 4:** Set up metrics tracking
5. ⏳ **Week 5+:** Review & refactor as needed

---

## Changelog

| Date | Change | Author |
| :--- | :--- | :--- |
| 2026-01-XX | Initial guidelines document created | AlpC18 |

---

**Questions?** Open an issue or discuss in the project's main communication channel.  
**License:** MIT © 2026 AlpC18
