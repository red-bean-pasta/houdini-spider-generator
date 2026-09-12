# Refactor comparison baseline

Recorded before applying refactors. This is a static baseline; no source behavior was executed for this record.

- `LegParam.from_specs` is defined in `leg_builder.py:42-63` and has no callers. Manual `LegParam(...)` construction exists in `leg.py:300-310` and `pedipalp.py:478-488`.
- `utilities.common.add_point` already centralizes point creation plus optional attributes. Current non-utility modules still contain direct `createPoint`/`setPosition`/ID assignment sequences.
- `head._add_points` at `head.py:221-230` is a local geometry-rebuild helper. Similar clear/recreate loops remain in `../../spider_generator/base_sops.py`, `../../spider_generator/pedicel.py`, `../../spider_generator/abdomen.py`, `../../spider_generator/chelicerae.py`, and `../../spider_generator/sternum.py`.
- `utilities.topology.offset_point` already implements the repeated translation operation.
- `fill_face` followed by primitive-attribute assignment is repeated in the body builders.
- Cyclic four-point loop stitching is repeated in `../../spider_generator/chelicerae.py`, `../../spider_generator/leg_builder.py`, `../../spider_generator/abdomen.py`, and `../../spider_generator/sternum.py`.
- Primitive filtering by `region` and blank-region fallback loops are repeated across `../../spider_generator/base_sops.py`, `../../spider_generator/chelicerae.py`, `../../spider_generator/leg.py`, `../../spider_generator/spider.py`, `../../spider_generator/pedipalp.py`, `../../spider_generator/head.py`, and `../../spider_generator/pedicel.py`.
- `helper.position_from_geo` is defined but unused.
- Left-ID SOP adapters are duplicated in `../../spider_generator/head.py`, `../../spider_generator/abdomen.py`, and `../../spider_generator/chelicerae.py`.
- SOP-only build chains are explicit in `../../spider_generator/base.py`, `../../spider_generator/head.py`, `../../spider_generator/chelicerae.py`, and `../../spider_generator/pedipalp.py`; the requested `sopify_chain` should preserve module-level callback names because `sopify` derives Houdini node names from the callback.

The existing user changes in `.gitignore`, `.aiassistant/commit.md`, and the analysis artifacts are outside the refactor scope and should remain intact.
