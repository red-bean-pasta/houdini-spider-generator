---
apply: always
---

# Summary 
This is a project that tries to model a spider in a biologically topology way in Houdini. It should generate SOP-based Houdini models.


## Working conventions
- Scoped under `~/Documents/git-him-back/one-day/models/spider/generator/`. Do not inspect outside.
- Inspect cooked SOP geometry before considering topology work complete. Do not treat a successful full build cook as proof that an intermediate SOP is correct. Run `hython test_builder.py` after SOP changes and retain the regenerated `test.hip` for manual inspection. No need for backing up. After cook, inspect the exact node's errors, point positions, primitive vertex order, and relevant attributes/groups. See more on `debug.md`.
- Preserve user edits; do not revert or overwrite them unbased or unrequested. Do not over-rely on git history because many changes are not staged during development.

## SOP and VEX conventions
- Prefer dedicated, small SOP-building methods.
- Use built-in SOPs when they fit the task.
- Use stable temporary attributes only when needed to carry identity through multiple SOPs. Name temporary attributes with a `tmp_` prefix.

## Code style
- No code nesting like r'''HOM or VEX codes'''. Do not use VEX unless highly necessary. Use `sopify` method under `sop_helper.py`.
- No over-engineering or speculative future-proofing. No over-defensiveness; prefer assertions or explicit errors for invalid expected topology.
- Do not hardcode points, names, positions, variables repetitively... Prefer looping, array and array builder. Hardcoding is only acceptable when it highly simplifies the code and avoids over-engineering. 
- Do make methods decoupled and modular. Do not write long, repetitive and boilerplate methods. Write logically clear and separaed methods. 
- Do not do exhaust listing. Prefer extraction, pattern, and positions (if robust). Exhaust listing is only acceptable if the logic is naturally "identifier" based, instead of geometry based.
- New lines communicate grouping and logical separation; do not use them merely to wrap a short call or expression, especially in one liner methods that holds small significance like `assert` or `raise_error`. Abusing newlines only make navigation harder.
- prefer `assert` over `NodeError` as assertion is correctly shown in .hip file.
- Methods should be separated by 2 new lines for clean code navigation. However, submethods are separated from its parent and sibling methods by 1 new lines for better logic grouping. Submethods refers to methods further broke down from one methods, not nested methods. Small methods, e.g., one liners, should be separated by 1 new line or even no new line to avoid cluster.

## Agent
- Dynamically adjust the thinking chain based on task difficulty. If the task is small, bounded or obvious, don't over-think. Balance token efficiency, intelligence and development speed. 
- For file updating and editing, use ACP tools like `client_edit_file`. DO NOT USE MCP tool like `apply_patch` or `pycharm_execute_terminal_command`, or python `file.write`
- Do not use `sed` or `head` when the whole document is available for one-time reading, unless you are highly sure you can land all the needed info in one pass, else it's just wasting user's time and turns.
- Use MCP to read out-of-scope files.
- No LaTex output. Only Markdown. LaTex is not correctly rendered in PyCharm.
- You can stash or commit current unstaged changes, branch out, make direct changes, test and fix, then try merging. CODE + TRY + ERROR + DEBUG first. Do not waste forever on tool calling and file inspecting.
- You can always ask for clarification and option choices using ACP tools, or simply stop and ask.  

## Reiterate
- No newline abusing.
- DO NOT MAKE STRUCTURL CHANGE unless requested.
- Edit files with ACP tools.
- DO NOT ABUSE TOOLS.

