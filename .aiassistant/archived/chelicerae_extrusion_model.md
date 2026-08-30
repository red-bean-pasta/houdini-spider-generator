# Chelicerae Extrusion Geometric Model Documentation

## 1. Overview & Architecture

The chelicera extrusion model in [`chelicerae._build_extrusion`](file:///home/xuh/Documents/git-him-back/one-day/models/spider/generator/chelicerae.py#L271-L365) generates a 3D curved tubular segment connecting the cephalothorax socket base to the fang tip base. 

The extrusion geometry is governed by three cross-sections (start, middle, end) lofted together with quadrilateral skinning. The trajectory and middle section orientation are analytically derived using an algebraic conic section passing through three 3D pivots with normal boundary constraints.

When start section is on YX plane, end section is rotated by -90 degrees and on XZ plane:
```
       [ Socket Face ] (Start Section: c1_1 -> c1_4)
              |
              v (P0: up_pivot, n0 = -Y)
               \
                \     (P2: middle_pivot, along = middle_section_dir)
                 *------> [ Middle Section: c2_1 -> c2_4 ]
                  \
                   \
                    v (P1: end_pivot, n1 = +Y)
              [ End Section: c3_1 -> c3_4 ]
```

---

## 2. Pivot Definition & Baseline Coordinates

### 2.1 Start Cross-Section ($c_{1}$) & Pivot ($P_0$)
From the socket base quadrilateral formed by classified points $c_{1\_1}, c_{1\_2}, c_{1\_3}, c_{1\_4}$:
- $x_{\text{min}} = c_{1\_1}.x, \quad x_{\text{max}} = c_{1\_4}.x \implies w = x_{\text{max}} - x_{\text{min}}$ (lateral width across X)
- $y_{\text{min}} = c_{1\_1}.y, \quad y_{\text{max}} = c_{1\_2}.y \implies h = y_{\text{max}} - y_{\text{min}}$ (longitudinal height across Y)
- $z = c_{1\_1}.z$

The start pivot $P_0$ (`up_pivot`) sits at the geometric center:
$$P_0 = \left(\frac{x_{\text{min}} + x_{\text{max}}}{2}, \frac{y_{\text{min}} + y_{\text{max}}}{2}, z\right)$$

Baseline scaling vector for offset parameters:
$$\mathbf{B} = (w, h, h)$$

### 2.2 End Pivot ($P_1$) & Middle Pivot ($P_2$)
Parameter offsets (`end_section_offset` and `middle_section_offset`) scale against baseline $\mathbf{B}$ with inversion along $Y$ and $Z$ to extend downwards and forwards:
$$P_1 = P_0 + \left(B_x \cdot \Delta x_{\text{end}}, -B_y \cdot \Delta y_{\text{end}}, -B_z \cdot \Delta z_{\text{end}}\right)$$
$$P_2 = P_0 + \left(B_x \cdot \Delta x_{\text{mid}}, -B_y \cdot \Delta y_{\text{mid}}, -B_z \cdot \Delta z_{\text{mid}}\right)$$

---

## 3. Conic Curve Trajectory & Boundary Normals

The central trajectory is defined by a 2D planar conic curve passing through $P_0, P_1, P_2$.

### 3.1 Normal Boundary Conditions
- **Start Section Face Normal**:
  $$\mathbf{n}_{\text{face, start}} = \text{get\_prim\_normal}(\text{socket\_prim}) = [0, 0, -1] \quad (-Z)$$
- **Start Pivot Conic Normal ($\mathbf{n}_0$)**:
  Points along the longitudinal direction from top to bottom of the start cross-section:
  $$\mathbf{n}_0 = \frac{c_{1\_1} - c_{1\_2}}{\|c_{1\_1} - c_{1\_2}\|} = [0, -1, 0] \quad (-Y)$$
- **End Section Face Normal**:
  Derived by applying the parameter rotation $R_{\text{end}}$ (default $-90^\circ$ around $X$):
  $$\mathbf{n}_{\text{face, end}} = \mathbf{n}_{\text{face, start}} \cdot R_{\text{end}} = [0, -1, 0] \quad (-Y)$$
- **End Pivot Conic Normal ($\mathbf{n}_1$)**:
  Opposes the end surface face normal:
  $$\mathbf{n}_1 = -\mathbf{n}_{\text{face, end}} = [0, 1, 0] \quad (+Y)$$

### 3.2 Conic Evaluation at Middle Pivot ($P_2$)
Calling [`utilities.topology.interpolate_conic`](file:///home/xuh/Documents/git-him-back/houdini-utility/topology.py#L130-L245) with $(P_0, P_1, P_2, \mathbf{n}_0, \mathbf{n}_1)$:
1. Solves the 2D conic system $A x^2 + B x y + C y^2 + D x + E y = 0$ via SVD.
2. Projects $P_2$ along the $P_0 \to P_1$ axis to evaluate the local curve normal $\mathbf{d}_{\text{mid}}$ (`middle_section_dir`).
3. `middle_section_dir` becomes the longitudinal axis $\mathbf{a}_{\text{mid}}$ ($c_{2\_1} - c_{2\_2}$) for the middle cross section.

---

## 4. Cross-Section Frame Construction

Every cross-section loop is constructed via [`_construct_section_loop(pivot, size, along, normal)`](file:///home/xuh/Documents/git-him-back/one-day/models/spider/generator/chelicerae.py#L371-L393):

### 4.1 Orthonormal Basis
Given longitudinal vector $\mathbf{a}$ (`along`) and face normal $\mathbf{n}$ (`normal`):
1. $\mathbf{n} \leftarrow \text{normalize}(\mathbf{n})$
2. $\mathbf{a} \leftarrow \text{normalize}(\mathbf{a} - \mathbf{n}(\mathbf{a} \cdot \mathbf{n}))$ (project $\mathbf{a}$ perpendicular to $\mathbf{n}$)
3. $\mathbf{s} = \mathbf{n} \times \mathbf{a}$ (`side`, lateral axis pointing towards $+X$)

### 4.2 Section Parameters & Corner Mapping
Let $h_{\text{half}} = \text{size.x} / 2$ (dimension along $\mathbf{a}$) and $w_{\text{half}} = \text{size.y} / 2$ (dimension along $\mathbf{s}$). The 4 corners maintain strict point ID ordering ($c_1 \to c_2 \to c_3 \to c_4$):

| Index | Corner ID | Relative Coordinate $(\mathbf{a}, \mathbf{s})$ | Spatial Position Description |
| :---: | :---: | :---: | :--- |
| **0** | $c_1$ | $(+h_{\text{half}}, +w_{\text{half}})$ | Bottom-Inner ($x_{\text{min}}, y_{\text{min}}$) |
| **1** | $c_2$ | $(-h_{\text{half}}, +w_{\text{half}})$ | Top-Inner ($x_{\text{min}}, y_{\text{max}}$) |
| **2** | $c_3$ | $(-h_{\text{half}}, -w_{\text{half}})$ | Top-Outer ($x_{\text{max}}, y_{\text{max}}$) |
| **3** | $c_4$ | $(+h_{\text{half}}, -w_{\text{half}})$ | Bottom-Outer ($x_{\text{max}}, y_{\text{min}}$) |

$$\mathbf{p}_i = P + \mathbf{a} \cdot a_i + \mathbf{s} \cdot s_i$$

---

## 5. Section Specifics

### Start Section ($c_1$)
- **Pivot**: $P_0$
- **Size**: $(h, w)$
- **Longitudinal ($\mathbf{a}$)**: $\mathbf{n}_0 = [0, -1, 0]$
- **Face Normal ($\mathbf{n}$)**: $\mathbf{n}_{\text{face, start}} = [0, 0, -1]$
- **Lateral ($\mathbf{s}$)**: $[0, 0, -1] \times [0, -1, 0] = [-1, 0, 0]$

### Middle Section ($c_2$)
- **Pivot**: $P_2$
- **Size**: $(h \cdot \text{middle\_ratio.y}, \; w \cdot \text{middle\_ratio.x})$
- **Longitudinal ($\mathbf{a}$)**: $\mathbf{d}_{\text{mid}}$ (evaluated conic normal at $P_2$)
- **Face Normal ($\mathbf{n}$)**: $\text{rot}(\mathbf{n}_0 \to \mathbf{d}_{\text{mid}}) \cdot \mathbf{n}_{\text{face, start}}$

### End Section ($c_3$)
- **Pivot**: $P_1$
- **Size**: $(h \cdot \text{end\_ratio.y}, \; w \cdot \text{end\_ratio.x})$
- **Longitudinal ($\mathbf{a}$)**: $\mathbf{n}_0 \cdot R_{\text{end}} = [0, 0, 1] \quad (+Z)$
- **Face Normal ($\mathbf{n}$)**: $\mathbf{n}_{\text{face, start}} \cdot R_{\text{end}} = [0, -1, 0] \quad (-Y)$
- **Lateral ($\mathbf{s}$)**: $[0, -1, 0] \times [0, 0, 1] = [-1, 0, 0]$

---

## 6. Topology & Skinning

1. **Side Quad Faces**:
   Iterate over adjacent loops $i \in \{0, 1\}$ (i.e. $c_1 \to c_2$ and $c_2 \to c_3$):
   For each corner $j \in \{0, 1, 2, 3\}$ and $j_{\text{next}} = (j + 1) \pmod 4$:
   $$\text{Quad}_j = [\text{loop}_i[j], \; \text{loop}_i[j_{\text{next}}], \; \text{loop}_{i+1}[j_{\text{next}}], \; \text{loop}_{i+1}[j]]$$
   This guarantees outward-pointing polygon surface normals across all 8 side quads.
2. **End Cap**:
   Closed with a single quad face `fill_face(geo, loops[-1])` over $c_{3\_1} \to c_{3\_2} \to c_{3\_3} \to c_{3\_4}$ facing down ($+Y$ in Houdini face winding).
3. **Socket Cleanup**:
   The internal socket polygons `socket_prims` are deleted to merge the extrusion seamlessly with the cephalothorax shell.

