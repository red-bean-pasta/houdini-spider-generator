---
apply: always
---

# Summary 
This is a project that tries to model a spider in a biologically topology way in Houdini. It should generate SOP-based Houdini models.


## Working conventions
- Scoped under `~/Documents/git-him-back/one-day/models/spider/generator/`. Do not inspect outside.
- Build the requested change instead of only proposing it.
- Inspect cooked SOP geometry before considering topology work complete. Do not treat a successful full build cook as proof that an intermediate SOP is correct.
- Run `hython test_builder.py` after SOP changes and retain the regenerated `test.hip` for manual inspection. No need for backing up.
- When debugging, inspect the exact node's errors, point positions, primitive vertex order, and relevant attributes/groups.
- Preserve user edits; do not revert or overwrite them unbased or unrequested.
- Do not over-rely on git history because many changes are not staged during development.

## SOP and VEX conventions
- Prefer dedicated, small SOP-building methods.
- Use built-in SOPs when they fit the task.
- Use stable temporary attributes only when needed to carry identity through multiple SOPs. Name temporary attributes with a `tmp_` prefix.

## Code style
- No code nesting like r'''HOM or VEX codes'''. Do not use VEX unless highly necessary. Use `sopify` method under `sop_helper.py`.
- No over-engineering or speculative future-proofing.
- No over-defensiveness; prefer assertions or explicit errors for invalid expected topology.
- Do not hardcode points, names, positions, variables repetitively... Prefer looping, array and array builder. Hardcoding is only acceptable when it highly simplifies the code and avoids over-engineering.
- Do not do exhaust listing. Prefer extraction, pattern, and positions (if robust). Exhaust listing is only acceptable if the logic is naturally "identifier" based, instead of geometry based.
- New lines communicate grouping and logical separation; do not use them merely to wrap a short call or expression, especially in one liner methods that holds small significance like `assert` or `raise_error`. Abusing newlines only make navigation harder.
- prefer `assert` over `NodeError` as assertion is correctly shown in .hip file.
- Methods should be separated by 2 new lines for clean code navigation. However, submethods are separated from its parent and sibling methods by 1 new lines for better logic grouping. Submethods refers to methods further broke down from one methods, not nested methods. Small methods, e.g., one liners, should be separated by 1 new line or even no new line to avoid cluster.

## Agent
- Dynamically adjust the thinking chain based on task difficulty. If the task is small, bounded or obvious, don't over-think. Balance token efficiency, intelligence and development speed. 
- Prefer code analyzing first, and only then use targeted commands and inspecting for debugging. Do not flood with useless and guessing commands.
- For file updating and editing, use ACP tools like `client_edit_file`. DO NOT USE MCP tool like `apply_patch` or `pycharm_execute_terminal_command`, or python `file.write`
- Do not use a lot of sed when reading the whole document is available. sed can easily miss and require a lot of back-and-forth. 

## Reiterate
- No newline abusing
- Choose between identifier, position or other pattern based construction based on the task's true nature.
- DO NOT REVERT USER CHANGES unless requested, broken, problematic or buggy, or if there's a better way. DO NOT MAKE TOO MUCH STRUCTURL CHANGE unless user requested or approved.
- DO NOT USE MCP or python script to edit files. They are only allowed if ACP tools are rejected due to scope control.
