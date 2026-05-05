"""OccluderStrategy: analytical placement of half-plane plate occluders.

Given camera and tag positions, derive plate orientation θ such that no
plate body sits between any camera and any tag — making the placement safe
"by construction" rather than via rejection sampling.

The shadow edge/corner of each plate is anchored so that, under parallel-SUN
projection, it passes through the tag-cluster centroid. Four patterns:

- ``half``: 1 large plate, single straight shadow edge (half-plane).
- ``corner``: 1 large plate anchored at its corner, quadrant shadow.
- ``bar``: 1 narrow plate centered on anchor, shadow strip.
- ``slit``: 2 large plates with a gap, narrow lit strip.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal

import numpy as np

from render_tag.core.geometry.math import sun_lateral_axis, sun_unit_vector
from render_tag.core.schema.recipe import ObjectRecipe
from render_tag.core.seeding import derive_seed

if TYPE_CHECKING:
    from render_tag.core.schema.recipe import CameraRecipe
    from render_tag.core.schema.subject import OccluderConfig
    from render_tag.generation.context import GenerationContext


OccluderPattern = Literal["half", "corner", "bar", "slit"]


class OccluderStrategy:
    """Sample plate occluders that shadow the tag cluster without occluding cameras."""

    def __init__(self, config: OccluderConfig):
        self.config = config

    def prepare_assets(self, context: GenerationContext) -> None:
        pass

    def sample_pose(
        self,
        seed: int,
        context: GenerationContext,
        tag_positions: list[tuple[float, float, float]],
        camera_recipes: list[CameraRecipe] | None = None,
        target_radius: float = 0.1,
    ) -> list[ObjectRecipe]:
        """Return plate recipes whose shadow edges cross the tag cluster.

        Args:
            seed: Scene-specific random seed.
            context: Shared generation context (carries the resolved lighting).
            tag_positions: World-space positions representing the 'forbidden'
                culling zone. The first element is the centroid used for
                shadow anchoring.
            camera_recipes: List of camera recipes for frustum culling.
            target_radius: Approximate radius of the tag cluster (meters).
        """
        cfg = self.config
        if not cfg.enabled or not tag_positions:
            return []

        gen_config = context.gen_config
        if gen_config is None:
            raise ValueError("gen_config is required in GenerationContext")

        directional = gen_config.scene.lighting.directional
        if not directional:
            return []

        sun = directional[0]
        if sun.elevation <= 0.0:
            return []

        sun_dir = sun_unit_vector(sun.azimuth, sun.elevation)
        if sun_dir[2] <= 1e-6:
            return []

        cams = camera_recipes or []
        rng = np.random.default_rng(derive_seed(seed, "occluder_layout", 0))

        # First element is the centroid for shadow anchoring
        centroid = tag_positions[0]
        target_z = centroid[2]

        cam_positions = []
        for c in cams:
            mat = np.array(c.transform_matrix)
            cam_positions.append((float(mat[0, 3]), float(mat[1, 3]), float(mat[2, 3])))

        # Try patterns in order of preference, falling back to 'half' if others fail.
        # This ensures we almost always get a shadow even in tight camera setups.
        requested_pattern: OccluderPattern = cfg.patterns[int(rng.integers(0, len(cfg.patterns)))]
        patterns_to_try: list[OccluderPattern] = [requested_pattern]
        if requested_pattern != "half":
            patterns_to_try.append("half")

        for pattern in patterns_to_try:
            # Sample initial relative height (meters above the tag)
            h_rel_base = float(rng.uniform(cfg.height_min_m, cfg.height_max_m))
            h_shift = 0.0

            # Sliding Loop: Guaranteed camera clearance via sun-ray sliding.
            for _ in range(50):
                h_abs = target_z + h_rel_base + h_shift
                angles = _crossing_angles(cam_positions, tag_positions, sun_dir, h_abs, centroid)

                plates = self._build_plates(
                    pattern=pattern,
                    target=centroid,
                    radius=target_radius,
                    sun_dir=sun_dir,
                    h=h_abs,
                    angles=angles,
                    rng=rng,
                )

                if not plates:
                    # Arc-fitting failed for this height, slide UP and try again.
                    h_shift += 0.05
                    continue

                # Robust Frustum Culling
                is_visible = False
                for plate in plates:
                    for cam in cams:
                        if _is_plate_visible_to_camera(plate, cam):
                            is_visible = True
                            break
                    if is_visible:
                        break

                if not is_visible:
                    return plates

                h_shift += 0.05

        return []

    def _build_plates(
        self,
        *,
        pattern: OccluderPattern,
        target: tuple[float, float, float],
        radius: float,
        sun_dir: tuple[float, float, float],
        h: float,
        angles: list[float],
        rng: np.random.Generator,
    ) -> list[ObjectRecipe]:
        if pattern == "half":
            return self._build_half_plates(target, radius, sun_dir, h, angles, rng)

        if pattern == "corner":
            return self._build_corner_plates(target, radius, sun_dir, h, angles, rng)

        if pattern == "bar":
            return self._build_bar_plates(target, radius, sun_dir, h, angles, rng)

        if pattern == "slit":
            return self._build_slit_plates(target, radius, sun_dir, h, angles, rng)

        return []

    def _build_half_plates(self, target, radius, sun_dir, h, angles, rng) -> list[ObjectRecipe]:
        # Edge shift relative to radius
        offset = (
            float(rng.uniform(-self.config.edge_offset_max_r, self.config.edge_offset_max_r))
            * radius
        )

        # Try both signs of the edge (which side is shadowed)
        # Sign S avoids cameras if angles fit in a pi arc shifted by S*pi/2.
        # Let's try both signs.
        # Robust approach: sample a random orientation, then check if it avoids cameras.
        # If not, try the opposite side. If neither fits, arc-fitting failed for this theta.
        # To be analytical:
        options: list[tuple[float, float]] = []

        # Case A: extend_sign = 1.0 (shadow is in [theta, theta + pi])
        # Safe arc for cameras is [theta - pi, theta]. Size pi.
        safe_start_a = _sample_theta_in_arc(angles, math.pi, rng)
        if safe_start_a is not None:
            # safe arc [safe_start, safe_start + pi].
            # we need body [theta, theta + pi] to be in the OTHER pi.
            # so theta = safe_start + pi.
            options.append(((safe_start_a + math.pi) % (2.0 * math.pi), 1.0))

        # Case B: extend_sign = -1.0 (shadow is in [theta - pi, theta])
        # Safe arc for cameras is [theta, theta + pi]. Size pi.
        safe_start_b = _sample_theta_in_arc(angles, math.pi, rng)
        if safe_start_b is not None:
            # safe arc [safe_start, safe_start + pi].
            # we need body [theta - pi, theta] to be in the OTHER pi.
            # so theta = safe_start.
            options.append((safe_start_b, -1.0))

        if not options:
            return []

        # From valid options, pick the one that faces the centroid (compensating for offset)
        # If offset > 0, shadow edge is shifted in e_perp direction.
        # To hit the centroid, we should extend in -e_perp direction (extend_sign = -1).
        # Or if offset < 0, extend_sign = 1.
        # Basically, we want extend_sign * offset < 0.

        best_option = None
        for theta, sign in options:
            if sign * offset <= 0:
                best_option = (theta, sign)
                break

        if best_option is None:
            best_option = options[int(rng.integers(0, len(options)))]

        edge_theta, extend_sign = best_option
        return [
            self._make_plate(
                name="Occluder_half",
                target=target,
                sun_dir=sun_dir,
                height=h,
                edge_theta=edge_theta,
                edge_offset=offset,
                extend_sign=extend_sign,
                size_along=self.config.plate_size_m,
                size_across=self.config.plate_size_m,
                anchor_mode="edge",
            )
        ]

    def _build_corner_plates(self, target, radius, sun_dir, h, angles, rng) -> list[ObjectRecipe]:
        offset_a = (
            float(rng.uniform(-self.config.edge_offset_max_r, self.config.edge_offset_max_r))
            * radius
        )
        offset_b = (
            float(rng.uniform(-self.config.edge_offset_max_r, self.config.edge_offset_max_r))
            * radius
        )

        # Try all 4 extend directions (quadrants)
        # Corner pattern has 2 axes. We use extend_sign for both in make_plate.
        # Each quadrant is 'forbidden' for cameras. The other 270 deg is 'safe'.
        # We sample safe_start and set theta accordingly.
        safe_start = _sample_theta_in_arc(angles, 1.5 * math.pi, rng)
        if safe_start is None:
            return []

        # This safe_start allows ONE specific quadrant to be shadowed.
        # Forbidden quadrant is [safe_start - pi/2, safe_start].
        edge_theta = (safe_start - 0.5 * math.pi) % (2.0 * math.pi)

        return [
            self._make_plate(
                name="Occluder_corner",
                target=target,
                sun_dir=sun_dir,
                height=h,
                edge_theta=edge_theta,
                edge_offset=offset_a,
                along_offset=offset_b,
                extend_sign=1.0,
                size_along=self.config.plate_size_m,
                size_across=self.config.plate_size_m,
                anchor_mode="corner",
            )
        ]

    def _build_bar_plates(self, target, radius, sun_dir, h, angles, rng) -> list[ObjectRecipe]:
        width = (
            float(rng.uniform(self.config.bar_width_min_r, self.config.bar_width_max_r)) * radius
        )
        offset = (
            float(rng.uniform(-self.config.edge_offset_max_r, self.config.edge_offset_max_r))
            * radius
        )

        # Bar is like a narrow half-plane. Use half-plane arc-fitting.
        safe_start = _sample_theta_in_arc(angles, math.pi, rng)
        if safe_start is None:
            return []
        edge_theta = (safe_start + math.pi) % (2.0 * math.pi)

        return [
            self._make_plate(
                name="Occluder_bar",
                target=target,
                sun_dir=sun_dir,
                height=h,
                edge_theta=edge_theta,
                edge_offset=offset,
                extend_sign=1.0,
                size_along=self.config.plate_size_m,
                size_across=width,
                anchor_mode="center",
            )
        ]

    def _build_slit_plates(self, target, radius, sun_dir, h, angles, rng) -> list[ObjectRecipe]:
        slit_w = (
            float(rng.uniform(self.config.slit_width_min_r, self.config.slit_width_max_r)) * radius
        )
        offset = (
            float(rng.uniform(-self.config.edge_offset_max_r, self.config.edge_offset_max_r))
            * radius
        )

        # Slit uses two half-planes. Use half-plane arc-fitting.
        safe_start = _sample_theta_in_arc(angles, math.pi, rng)
        if safe_start is None:
            return []
        edge_theta = (safe_start + math.pi) % (2.0 * math.pi)

        e_perp = sun_lateral_axis(edge_theta)
        return [
            self._make_plate(
                name="Occluder_slit_0",
                target=(
                    target[0] + (slit_w / 2.0) * e_perp[0],
                    target[1] + (slit_w / 2.0) * e_perp[1],
                    target[2],
                ),
                sun_dir=sun_dir,
                height=h,
                edge_theta=edge_theta,
                edge_offset=offset,
                extend_sign=1.0,
                size_along=self.config.plate_size_m,
                size_across=self.config.plate_size_m,
                anchor_mode="edge",
            ),
            self._make_plate(
                name="Occluder_slit_1",
                target=(
                    target[0] - (slit_w / 2.0) * e_perp[0],
                    target[1] - (slit_w / 2.0) * e_perp[1],
                    target[2],
                ),
                sun_dir=sun_dir,
                height=h + 1.1 * self.config.plate_thickness_m,
                edge_theta=edge_theta,
                edge_offset=offset,
                extend_sign=-1.0,
                size_along=self.config.plate_size_m,
                size_across=self.config.plate_size_m,
                anchor_mode="edge",
            ),
        ]

    def _make_plate(
        self,
        *,
        name: str,
        target: tuple[float, float, float],
        sun_dir: tuple[float, float, float],
        height: float,
        edge_theta: float,
        edge_offset: float,
        extend_sign: float,
        size_along: float,
        size_across: float,
        anchor_mode: Literal["edge", "corner", "center"] = "edge",
        along_offset: float = 0.0,
    ) -> ObjectRecipe:
        cfg = self.config
        sx, sy, sz = sun_dir
        tx, ty, tz = target
        e_along = (math.cos(edge_theta), math.sin(edge_theta))
        e_perp = sun_lateral_axis(edge_theta)

        # 1. Project target to plate height along SUN ray
        # The projection is relative to the receiver height (tz)
        h_rel = height - tz
        edge_anchor_x = tx + (h_rel / sz) * sx
        edge_anchor_y = ty + (h_rel / sz) * sy

        # 2. Apply offsets
        cx = edge_anchor_x + edge_offset * e_perp[0] + along_offset * e_along[0]
        cy = edge_anchor_y + edge_offset * e_perp[1] + along_offset * e_along[1]

        # 3. Shift center based on anchor mode
        if anchor_mode == "edge":
            # edge_offset moves the edge. plate extends from edge in extend_sign*e_perp
            cx += extend_sign * (size_across / 2.0) * e_perp[0]
            cy += extend_sign * (size_across / 2.0) * e_perp[1]
        elif anchor_mode == "corner":
            # edge_offset and along_offset move the corner. plate extends in quadrant.
            cx += (
                extend_sign * (size_along / 2.0) * e_along[0]
                + extend_sign * (size_across / 2.0) * e_perp[0]
            )
            cy += (
                extend_sign * (size_along / 2.0) * e_along[1]
                + extend_sign * (size_across / 2.0) * e_perp[1]
            )
        # "center" mode needs no shift

        return ObjectRecipe(
            type="OCCLUDER",
            name=name,
            location=[cx, cy, height],
            rotation_euler=[0.0, 0.0, edge_theta],
            scale=[1.0, 1.0, 1.0],
            properties={
                "shape": "plate",
                "size_along_edge_m": size_along,
                "size_across_edge_m": size_across,
                "thickness_m": cfg.plate_thickness_m,
                "albedo": cfg.albedo,
                "roughness": cfg.roughness,
            },
        )


def _camera_ray_xy_at_height(
    cam: tuple[float, float, float],
    target: tuple[float, float, float],
    h: float,
) -> tuple[float, float] | None:
    """XY where the cam→target ray crosses ``z=h``; ``None`` if it doesn't."""
    cx, cy, cz = cam
    tx, ty, tz = target
    denom = cz - tz
    if abs(denom) < 1e-9:
        return None
    t = (cz - h) / denom
    if not (0.0 < t < 1.0):
        return None
    return (cx + t * (tx - cx), cy + t * (ty - cy))


def _crossing_angles(
    cams: list[tuple[float, float, float]],
    tags: list[tuple[float, float, float]],
    sun_dir: tuple[float, float, float],
    h: float,
    target: tuple[float, float, float],
) -> list[float]:
    """Polar angles of (cam, tag) ray crossings at z=h, around the SUN edge anchor.

    A crossing at world XY ``(gx, gy)`` is mapped to ``a = atan2(gy - ay,
    gx - ax)`` where ``(ax, ay)`` is the SUN-projected edge anchor.
    The anchor projection is relative to the target's height.
    """
    sx, sy, sz = sun_dir
    h_rel = h - target[2]
    ax = target[0] + (h_rel / sz) * sx
    ay = target[1] + (h_rel / sz) * sy
    out: list[float] = []
    for cam in cams:
        for tag in tags:
            xy = _camera_ray_xy_at_height(cam, tag, h)
            if xy is None:
                continue
            dx = xy[0] - ax
            dy = xy[1] - ay
            if math.hypot(dx, dy) < 1e-9:
                continue
            out.append(math.atan2(dy, dx))
    return out


def _sample_theta_in_arc(
    angles: list[float],
    max_arc: float,
    rng: np.random.Generator,
) -> float | None:
    """Sample θ uniformly such that (a - θ) mod 2π ∈ [0, max_arc] for all a.

    Returns ``None`` when no such θ exists — i.e., when the smallest cyclic
    arc covering ``angles`` (sum minus the largest gap) exceeds ``max_arc``.
    With an empty ``angles`` list, returns a uniform sample on ``[0, 2π)``.
    """
    if not angles:
        return float(rng.uniform(0.0, 2.0 * math.pi))

    sorted_b = sorted(a % (2.0 * math.pi) for a in angles)
    n = len(sorted_b)

    max_gap = sorted_b[0] + 2.0 * math.pi - sorted_b[-1]
    cluster_end = sorted_b[-1]
    for i in range(n - 1):
        gap = sorted_b[i + 1] - sorted_b[i]
        if gap > max_gap:
            max_gap = gap
            cluster_end = sorted_b[i]

    cluster_span = 2.0 * math.pi - max_gap
    if cluster_span > max_arc + 1e-12:
        return None

    valid_size = max_arc - cluster_span
    return float((cluster_end - max_arc + rng.uniform(0.0, valid_size)) % (2.0 * math.pi))


def _plate_contains_xy(plate: ObjectRecipe, xy: tuple[float, float]) -> bool:
    px, py = plate.location[0], plate.location[1]
    theta = (plate.rotation_euler or [0.0, 0.0, 0.0])[2]
    along = float(plate.properties["size_along_edge_m"])
    across = float(plate.properties["size_across_edge_m"])
    dx, dy = xy[0] - px, xy[1] - py
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    return (
        abs(dx * cos_t + dy * sin_t) <= along / 2.0
        and abs(-dx * sin_t + dy * cos_t) <= across / 2.0
    )


def _is_plate_visible_to_camera(plate: ObjectRecipe, cam: CameraRecipe) -> bool:
    """Rigorous check: is ANY part of the plate visible to the camera?

    Uses 3D-to-2D projection, near-plane clipping, and 2D Separating Axis
    Theorem (SAT) to check for intersection with the image rectangle.
    """
    px, py, pz = plate.location[0], plate.location[1], plate.location[2]
    theta = (plate.rotation_euler or [0.0, 0.0, 0.0])[2]
    along = float(plate.properties["size_along_edge_m"])
    across = float(plate.properties["size_across_edge_m"])

    # 1. Plate World Corners
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    # Plate local axes in world XY
    ax = (cos_t, sin_t)
    ay = (-sin_t, cos_t)

    l_along = along / 2.0
    l_across = across / 2.0
    corners_world = [
        (px + l_along * ax[0] + l_across * ay[0], py + l_along * ax[1] + l_across * ay[1], pz),
        (px - l_along * ax[0] + l_across * ay[0], py - l_along * ax[1] + l_across * ay[1], pz),
        (px - l_along * ax[0] - l_across * ay[0], py - l_along * ax[1] - l_across * ay[1], pz),
        (px + l_along * ax[0] - l_across * ay[0], py + l_along * ax[1] - l_across * ay[1], pz),
    ]

    # 2. Project to Camera Space
    # Camera Matrix (T_cw: camera-to-world)
    # We need T_wc (world-to-camera) to project points into camera space.
    t_cw = np.array(cam.transform_matrix)
    t_wc = np.linalg.inv(t_cw)

    corners_cam = []
    for cw in corners_world:
        cc = t_wc @ np.array([cw[0], cw[1], cw[2], 1.0])
        corners_cam.append(cc[:3])

    # 3. Near-Plane Clipping (z < 0 in Blender camera space)
    # Blender camera looks down -Z. NEAR plane is slightly below 0.
    # We clip against Z_cam = -1e-4.
    NEAR = -1e-4
    if all(c[2] > NEAR for c in corners_cam):
        # Entirely behind camera
        return False

    clipped_cam = []
    for i in range(len(corners_cam)):
        c1 = corners_cam[i]
        c2 = corners_cam[(i + 1) % len(corners_cam)]
        if c1[2] <= NEAR:
            clipped_cam.append(c1)
        # Edge crosses near plane
        if (c1[2] <= NEAR and c2[2] > NEAR) or (c1[2] > NEAR and c2[2] <= NEAR):
            t = (NEAR - c1[2]) / (c2[2] - c1[2])
            inter = c1 + t * (c2 - c1)
            clipped_cam.append(inter)

    if not clipped_cam:
        return False

    # 4. Project to 2D Pixels
    k = np.array(cam.intrinsics.k_matrix)
    fx, fy = k[0, 0], k[1, 1]
    cx, cy = k[0, 2], k[1, 2]
    res_w, res_h = cam.intrinsics.resolution

    poly_2d = []
    for X, Y, Z in clipped_cam:
        # Perspective divide (Z is negative, looking down -Z)
        x_ndc = X / -Z
        y_ndc = Y / -Z
        px_2d = fx * x_ndc + cx
        py_2d = fy * y_ndc + cy
        poly_2d.append((px_2d, py_2d))

    # 5. SAT Intersection Check
    # Image box: [0, 0] to [W, H]
    image_box = [(0.0, 0.0), (float(res_w), 0.0), (float(res_w), float(res_h)), (0.0, float(res_h))]

    return _polygons_intersect_2d(poly_2d, image_box)


def _polygons_intersect_2d(
    poly1: list[tuple[float, float]], poly2: list[tuple[float, float]]
) -> bool:
    """Separating Axis Theorem for two 2D convex polygons."""
    for poly in (poly1, poly2):
        for i in range(len(poly)):
            p1 = poly[i]
            p2 = poly[(i + 1) % len(poly)]
            # Edge normal
            nx, ny = -(p2[1] - p1[1]), p2[0] - p1[0]
            mag = math.hypot(nx, ny)
            if mag < 1e-9:
                continue
            nx /= mag
            ny /= mag

            # Project both polygons
            min1 = min(p[0] * nx + p[1] * ny for p in poly1)
            max1 = max(p[0] * nx + p[1] * ny for p in poly1)
            min2 = min(p[0] * nx + p[1] * ny for p in poly2)
            max2 = max(p[0] * nx + p[1] * ny for p in poly2)

            if max1 < min2 or max2 < min1:
                return False  # Found separating axis
    return True
