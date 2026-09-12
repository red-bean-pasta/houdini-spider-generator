# Refactor comparison baseline

Recorded before applying refactors. This is a static baseline; no source behavior was executed for this record.

- `LegParam.from_specs` is defined in `leg_builder.py:42-63` and has no callers. Manual `LegParam(...)` construction exists in `leg.py:300-310` and `pedipalp.py:478-488`.
- `utilities.common.add_point` already centralizes point creation plus optional attributes. Current non-utility modules still contain direct `createPoint`/`setPosition`/ID assignment sequences.
- `head._add_points` at `head.py:221-230` is a local geometry-rebuild helper. Similar clear/recreate loops remain in `base_sops.py`, `pedicel.py`, `abdomen.py`, `chelicerae.py`, and `sternum.py`.
- `utilities.topology.offset_point` already implements the repeated translation operation.
- `fill_face` followed by primitive-attribute assignment is repeated in the body builders.
- Cyclic four-point loop stitching is repeated in `chelicerae.py`, `leg_builder.py`, `abdomen.py`, and `sternum.py`.
- Primitive filtering by `region` and blank-region fallback loops are repeated across `base_sops.py`, `chelicerae.py`, `leg.py`, `spider.py`, `pedipalp.py`, `head.py`, and `pedicel.py`.
- `helper.position_from_geo` is defined but unused.
- Left-ID SOP adapters are duplicated in `head.py`, `abdomen.py`, and `chelicerae.py`.
- SOP-only build chains are explicit in `base.py`, `head.py`, `chelicerae.py`, and `pedipalp.py`; the requested `sopify_chain` should preserve module-level callback names because `sopify` derives Houdini node names from the callback.

The existing user changes in `.gitignore`, `.aiassistant/commit.md`, and the analysis artifacts are outside the refactor scope and should remain intact.
