#### Background
Currently topology.py offers a conic interpolation method. It doesn't guarantee that any point is the peak, so it's indeed conic interpolation, but not geometrically useful for curve construction.
"""
A useful family is the elliptical interpolation function used in interpolating-spline work by Cem Yuksel. The core idea is exactly to take three consecutive points and fit a local ellipse while forcing the middle point to lie on one of the ellipse’s axes. That makes the middle point a genuine extremal point of the ellipse—not just an arbitrary point on it.
"""

#### Implementation example
Below is a self-contained NumPy/SciPy implementation. It gives you a practical **ellipse-like 3D bulge** with:
* exact interpolation of `p0`, `p1`, `p2`
* `p1` explicitly treated as the bulge tip
* tangent directions `slope0`, `slope2`
* equal tangent magnitude at `p0` and `p2`
* automatically chosen tangent magnitude at `p1`
* matching tangent and curvature through `p1` — actually (C^2) with this parameterization
* smooth parameters chosen by minimizing jerk.
```python
import numpy as np
from scipy.optimize import minimize


def _normalize(v, eps=1e-12):
    v = np.asarray(v, dtype=float)
    n = np.linalg.norm(v)
    if n < eps:
        raise ValueError("Cannot normalize a zero-length vector.")
    return v / n


def _quintic_coefficients(p0, v0, a0, p1, v1, a1):
    """
    Construct a quintic polynomial

        C(t) = c0 + c1*t + ... + c5*t^5

    for t in [0, 1], satisfying position, velocity and acceleration
    at both endpoints.

    Returns coefficients with shape (6, 3).
    """
    p0 = np.asarray(p0, float)
    v0 = np.asarray(v0, float)
    a0 = np.asarray(a0, float)
    p1 = np.asarray(p1, float)
    v1 = np.asarray(v1, float)
    a1 = np.asarray(a1, float)

    c0 = p0
    c1 = v0
    c2 = a0 / 2.0

    dp = p1 - (c0 + c1 + c2)
    dv = v1 - (c1 + 2.0 * c2)
    da = a1 - 2.0 * c2

    M = np.array([
        [1.0,  1.0,  1.0],
        [3.0,  4.0,  5.0],
        [6.0, 12.0, 20.0],
    ])

    c3, c4, c5 = np.linalg.solve(
        M,
        np.stack([dp, dv, da])
    )

    return np.vstack([c0, c1, c2, c3, c4, c5])


def _evaluate(coeff, t):
    """Evaluate quintic polynomial at scalar/array t."""
    t = np.asarray(t, dtype=float)

    powers = np.stack([
        np.ones_like(t),
        t,
        t**2,
        t**3,
        t**4,
        t**5
    ], axis=-1)

    return powers @ coeff


def _jerk_energy(coeff):
    """
    Exact integral

        integral_0^1 ||C'''(t)||^2 dt

    for a quintic polynomial.
    """
    c3 = coeff[3]
    c4 = coeff[4]
    c5 = coeff[5]

    # C'''(t) = A + B*t + C*t^2
    A = 6.0 * c3
    B = 24.0 * c4
    C = 60.0 * c5

    return (
        np.dot(A, A)
        + np.dot(A, B)
        + (2.0 / 3.0) * np.dot(A, C)
        + (1.0 / 3.0) * np.dot(B, B)
        + 0.5 * np.dot(B, C)
        + (1.0 / 5.0) * np.dot(C, C)
    )


def bulge_curve(
    p0,
    p1,
    p2,
    slope0,
    slope2,
    n_samples=100,
    return_info=False,
):
    """
    Build a smooth 3D bulge through p0 -> p1 -> p2.

    p1 is explicitly treated as the apex of the bulge relative
    to the straight line from p0 to p2.

    Parameters
    ----------
    p0, p1, p2 : array-like, shape (3,)
        The three interpolation points.

    slope0, slope2 : array-like, shape (3,)
        Tangent DIRECTIONS at p0 and p2.
        Their lengths are ignored.

        The resulting endpoint tangent vectors are given the
        same optimized magnitude.

    n_samples : int
        Number of output points over the entire curve.

    return_info : bool
        If True, also return useful geometric information.

    Returns
    -------
    points : ndarray, shape (n_samples, 3)

    info : dict, optional
        Only returned when return_info=True.
    """

    p0 = np.asarray(p0, dtype=float)
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)

    d0 = _normalize(slope0)
    d2 = _normalize(slope2)

    # ------------------------------------------------------------
    # 1. Baseline direction
    #
    #          p1
    #          *
    #         / \
    #        /   \
    #   p0 *-----* p2
    #
    # ------------------------------------------------------------

    chord = p2 - p0
    chord_length = np.linalg.norm(chord)

    if chord_length < 1e-12:
        raise ValueError("p0 and p2 must be different.")

    tangent_apex = chord / chord_length

    # ------------------------------------------------------------
    # 2. Work out the "height direction" of the bulge.
    #
    # Project p1 onto the p0-p2 baseline.
    #
    #             p1
    #              *
    #              |
    #              | height
    #              |
    #   p0 *-------+-------* p2
    #
    # ------------------------------------------------------------

    projection = (
        p0
        + np.dot(p1 - p0, tangent_apex) * tangent_apex
    )

    height_vector = p1 - projection
    height = np.linalg.norm(height_vector)

    if height < 1e-10:
        raise ValueError(
            "p1 is essentially on the p0-p2 line, so there is "
            "no well-defined bulge direction."
        )

    outward = height_vector / height

    # At the tip, acceleration points BACK toward the baseline.
    inward = -outward

    # ------------------------------------------------------------
    # Unknowns:
    #
    # endpoint_speed:
    #   ||C'(p0)|| = ||C'(p2)||
    #
    # apex_speed:
    #   ||C'(p1)||
    #
    # apex_curvature_force:
    #   magnitude of C'' at p1 toward the baseline
    #
    # We optimize them for minimum squared jerk.
    # ------------------------------------------------------------

    def build(parameters):
        endpoint_speed, apex_speed, apex_accel = np.exp(parameters)

        v0 = endpoint_speed * d0
        v1 = apex_speed * tangent_apex
        v2 = endpoint_speed * d2

        # Zero endpoint acceleration is a neutral boundary choice.
        a0 = np.zeros(3)
        a2 = np.zeros(3)

        # Both halves have EXACTLY the same second derivative at p1.
        a1 = apex_accel * inward

        left = _quintic_coefficients(
            p0, v0, a0,
            p1, v1, a1
        )

        right = _quintic_coefficients(
            p1, v1, a1,
            p2, v2, a2
        )

        return left, right

    def objective(parameters):
        left, right = build(parameters)

        return (
            _jerk_energy(left)
            + _jerk_energy(right)
        )

    # Reasonable geometry-based initial guesses.
    initial_endpoint_speed = chord_length * 0.5
    initial_apex_speed = chord_length * 0.5

    # For an arch/ellipse-like shape, curvature at the tip grows
    # roughly with bulge height.
    initial_apex_accel = max(4.0 * height, 1e-6)

    x0 = np.log([
        initial_endpoint_speed,
        initial_apex_speed,
        initial_apex_accel,
    ])

    result = minimize(
        objective,
        x0,
        method="L-BFGS-B",
        bounds=[
            (-20.0, 20.0),
            (-20.0, 20.0),
            (-20.0, 20.0),
        ],
    )

    if not result.success:
        raise RuntimeError(
            f"Curve optimization failed: {result.message}"
        )

    left, right = build(result.x)

    endpoint_speed, apex_speed, apex_accel = np.exp(result.x)

    # ------------------------------------------------------------
    # Sample both segments.
    # Avoid duplicating p1.
    # ------------------------------------------------------------

    n_left = n_samples // 2 + 1
    n_right = n_samples - n_left + 1

    t_left = np.linspace(0.0, 1.0, n_left)
    t_right = np.linspace(0.0, 1.0, n_right)

    points_left = _evaluate(left, t_left)
    points_right = _evaluate(right, t_right)

    points = np.vstack([
        points_left,
        points_right[1:]
    ])

    if not return_info:
        return points

    info = {
        "endpoint_speed": endpoint_speed,
        "apex_speed": apex_speed,
        "apex_acceleration": apex_accel,

        "tangent_p0": endpoint_speed * d0,
        "tangent_p1": apex_speed * tangent_apex,
        "tangent_p2": endpoint_speed * d2,

        "acceleration_p1": apex_accel * inward,

        "bulge_direction": outward,
        "bulge_height": height,
        "baseline_direction": tangent_apex,

        "left_coefficients": left,
        "right_coefficients": right,

        "optimization": result,
    }

    return points, info
```
this is only an example. bugs and errors expected. need format refactoring to fit this project.


#### Task
help me add a new method in `topology.py` after `interpolate_conic` called `interpolate_elliptical`:
1. it's not a strict conic anymore
2. it takes arguments p0, p1, p2, normal0 and normal2. p1 doesn't have a normal, and should be the peak/tip of the interpolated elliptical shape.
3. migrate `chelicerae.py` to use `interpolate_elliptical`.
4. verify the result
