## Task
i need add some more sections in chelicerae extrusion for smoother shape:
- after `_add_middle_section` but before `_connect_sections`, add method `_add_upper_middle_section`
- `_add_upper_middle_section` follows the similar construction as `_add_middle_section` but it doesn't have parameter handles. it's interpolated between start section and middle section:
    - get the conic evaluation callable same as `_add_middle_section`
    - get the middle `x` between start_pivot and middle_pivot on the `along_axis`, the `end_pivot - start_pivot` one
    - get the `upper_middle_pivot` and its conic_normal
    - get the size of upper_middle_section by interpolating between the (w, h) of start_section to the (w, h) of middle_section. it should lean over the size of middle_section, so the weight is more like `(middle_pivot_along - get_conic_along(middle_pivot_across - upper_middle_pivot_across)) / middle_pivot_along`. I hope you know what interpolation curve i'm talking about. you can have a more efficient way if you find one.
    - consturct the upper_middle_section, similar as middle_section. attributed as `celiceraeuppermiddle[i]`, then fill it reversed
