# Native Python SOP migration

Use this guide when replacing inline VEX that constructs or edits geometry.

## Principle

- Use `sopify`, `hom_helper` and `sop_helper`. 
- Be much more modular. Each method represents a SOP. Therefore, don't be afraid to add SOP since `sopify` offers a convenient wrapper.
- Each SOP-representing method should ideally not break down into smaller methods. Modulation should not happen at SOP level, but orchestration. This rule enables debuging and experimenting in the GUI editor, with method content directly inside the SOP.
- Prefer to generalize and put reused/reusable/common methods in `hom_helper` or `sop_helper`. 
- This project heavily uses "id" for point identifier. "id" is a point level attribute. When referencing, prefer to use patterns similar as:
```python
class ID(StrEnum):
    STERNUMRIM = auto()
    STERNUMMIDDLE = auto()
    STERNUMSPINE = auto()

def sternumrim(*i: int | str) -> str:
    return affix_id(ID.STERNUMRIM, *i)
def sternummiddle(*i: int | str) -> str:
    return affix_id(ID.STERNUMMIDDLE, *i)
def sternumspine(*i: int | str) -> str:
    return affix_id(ID.STERNUMSPINE, *i)

def outer_loop_ids() -> tuple[str, str]:
    return ID.STERNUMRIM, ID.STERNUMMIDDLE
```
instead of `f"sternumrim{i}_{j}"` for easier referencing and debugging.
Tmporary attributes like "tmp_operation_reference_attribute" can elude this rule.
