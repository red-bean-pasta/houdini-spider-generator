# Summary 
This is a project that tries to model a spider in a biologically topology way in Houdini. It should generate SOP-based Houdini models.


## Working conventions

- Scoped under `~/Documents/git-him-back/one-day/models/spider/generator/`. Do not inspect outside.
- Build the requested change instead of only proposing it.
- Inspect cooked SOP geometry before considering topology work complete. Do not treat a successful full build cook as proof that an intermediate SOP is correct.
- Run `hython test_builder.py` after changes and retain the regenerated `test.hip` for manual inspection. No need for backing up.
- When debugging, inspect the exact node's errors, point positions, primitive vertex order, and relevant attributes/groups.
- Preserve user edits; do not revert or overwrite them.

## SOP and VEX conventions

- Prefer dedicated, small SOP-building methods.
- Use built-in SOPs when they fit the task.
- Use stable temporary attributes only when needed to carry identity through multiple SOPs. Name temporary attributes with a `tmp_` prefix.

## Code style

- No code nesting like r'''HOM or VEX codes'''. Do not use VEX unless highly necessary. Use `sopify` method under `sop_helper.py`.
- No over-engineering or speculative future-proofing.
- No over-defensiveness; prefer assertions or explicit errors for invalid expected topology.
- Do not hardcode points, names, positions, variables repetitively... Prefer looping, array and array builder. Hardcoding is only acceptable when it highly simplifies the code and avoids over-engineering.
- New lines communicate grouping and logical separation; do not use them merely to wrap a short call or expression, especially in one liner methods that holds small significance like `assert` or `raise_error`. Abusing newlines only make navigation harder.
- prefer `assert` over `NodeError` as assertion is correctly bundled in .hip file.

## Reiterate

- Use `sopify`
- No newline abusing
