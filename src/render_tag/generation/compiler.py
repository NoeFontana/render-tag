"""
Deterministic Scene Compiler for render-tag.

Shifts all "decision-making" (random sampling, asset selection, pose calculation)
from the Blender runtime to the pure-Python preparation phase.
"""

import json
import math
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from ..core.config import CameraConfig, DirectionalLightConfig, GenConfig
from ..core.geometry.projection_math import has_active_distortion
from ..core.geometry.visibility import is_facing_camera
from ..core.logging import get_logger
from ..core.schema import (
    CameraIntrinsics,
    CameraRecipe,
    LightRecipe,
    SceneRecipe,
    SensorDynamicsRecipe,
    SensorNoiseConfig,
    WorldRecipe,
)
from ..core.seeding import derive_seed
from ..data_io.assets import AssetProvider
from .camera import sample_camera_pose
from .strategy.factory import get_occluder_strategy, get_subject_strategy

if TYPE_CHECKING:
    from .strategy.base import SubjectStrategy
    from .strategy.occluder import OccluderStrategy

logger = get_logger(__name__)

MAX_VALIDATION_RETRIES = 50

ISO_COUPLING_BASE_SIGMA = 0.002
ISO_COUPLING_ALPHA = 0.8
ISO_COUPLING_GAIN_FLOOR = 800.0
ISO_COUPLING_GAIN_CEILING = 6400.0

SUN_DISTANCE = 10.0


def _build_sun_light_recipe(cfg: DirectionalLightConfig) -> LightRecipe:
    """Encode azimuth/elevation as Blender location + XYZ-Euler pointing at the origin.

    Rotation derivation verified by ``test_sun_rotation_points_light_at_origin``.
    """
    x = SUN_DISTANCE * math.cos(cfg.elevation) * math.cos(cfg.azimuth)
    y = SUN_DISTANCE * math.cos(cfg.elevation) * math.sin(cfg.azimuth)
    z = SUN_DISTANCE * math.sin(cfg.elevation)
    return LightRecipe(
        type="SUN",
        location=[x, y, z],
        intensity=cfg.intensity,
        radius=0.0,
        color=list(cfg.color),
        rotation_euler=[math.pi / 2 - cfg.elevation, 0.0, math.pi / 2 + cfg.azimuth],
    )


def derive_iso_coupled_noise(
    camera_config: CameraConfig,
) -> tuple[float, SensorNoiseConfig | None]:
    """Derive effective (iso_noise, sensor_noise) from ``camera.iso``.

    Returns the user-configured values unchanged when ``iso_coupling`` is False.
    When coupling is enabled, fills only fields the user left at their schema
    defaults so explicit overrides always win.
    """
    if not camera_config.iso_coupling:
        return camera_config.iso_noise, camera_config.sensor_noise

    iso = camera_config.iso

    if camera_config.iso_noise == 0.0:
        span = ISO_COUPLING_GAIN_CEILING - ISO_COUPLING_GAIN_FLOOR
        effective_iso_noise = float(np.clip((iso - ISO_COUPLING_GAIN_FLOOR) / span, 0.0, 1.0))
    else:
        effective_iso_noise = camera_config.iso_noise

    if camera_config.sensor_noise is None:
        stddev = ISO_COUPLING_BASE_SIGMA * (iso / 100.0) ** ISO_COUPLING_ALPHA
        effective_sensor_noise: SensorNoiseConfig | None = SensorNoiseConfig(
            model="gaussian",
            stddev=stddev,
        )
    else:
        effective_sensor_noise = camera_config.sensor_noise

    return effective_iso_noise, effective_sensor_noise


def compute_overscan_intrinsics(
    k_target: list[list[float]],
    resolution: tuple[int, int],
    distortion_coeffs: list[float],
    distortion_model: str = "brown_conrady",
    n_samples: int = 32,
) -> tuple[list[list[float]], tuple[int, int]]:
    """
    Compute the linear overscan K-matrix and resolution needed to cover all
    rays sampled by the distorted target image.

    Samples the 4 edges of the target image at n_samples points each and
    applies iterative inverse distortion to find the maximum undistorted
    angular extent. The returned overscan K and resolution guarantee that
    Blender's linear render fully covers the field needed for the post-warp.

    Args:
        k_target: 3x3 target K-matrix [[fx,0,cx],[0,fy,cy],[0,0,1]].
        resolution: (width, height) of the target distorted image.
        distortion_coeffs: Distortion coefficients for the model.
        distortion_model: 'brown_conrady' or 'kannala_brandt'.
        n_samples: Number of sample points per edge.

    Returns:
        (k_linear, (W_lin, H_lin)): Overscan K-matrix and pixel dimensions.
    """
    W, H = resolution
    fx = k_target[0][0]
    fy = k_target[1][1]

    # Sample all 4 edges of the target image
    u_edge = np.linspace(0, W - 1, n_samples)
    v_edge = np.linspace(0, H - 1, n_samples)

    u_boundary = np.concatenate([u_edge, u_edge, np.zeros(n_samples), np.full(n_samples, W - 1)])
    v_boundary = np.concatenate([np.zeros(n_samples), np.full(n_samples, H - 1), v_edge, v_edge])

    # Delegate inverse distortion to OpenCV's C++ solver, same as compute_distortion_maps.
    K_tgt = np.array(k_target, dtype=np.float64)
    D = np.array(distortion_coeffs, dtype=np.float64)
    pts = np.stack([u_boundary, v_boundary], axis=-1).reshape(-1, 1, 2).astype(np.float64)
    if distortion_model == "kannala_brandt":
        undist = cv2.fisheye.undistortPoints(pts, K_tgt, D)
    else:
        undist = cv2.undistortPoints(pts, K_tgt, D)
    x_undist = undist[:, 0, 0]
    y_undist = undist[:, 0, 1]

    # Maximum angular extent in each axis
    max_x = float(np.max(np.abs(x_undist)))
    max_y = float(np.max(np.abs(y_undist)))

    # Build overscan resolution (rounded up to nearest even for codec compatibility)
    W_lin = 2 * math.ceil(max_x * fx + 1)
    H_lin = 2 * math.ceil(max_y * fy + 1)

    # Ensure overscan is at least as large as target
    W_lin = max(W_lin, W)
    H_lin = max(H_lin, H)

    cx_lin = W_lin / 2.0
    cy_lin = H_lin / 2.0

    k_linear: list[list[float]] = [
        [fx, 0.0, cx_lin],
        [0.0, fy, cy_lin],
        [0.0, 0.0, 1.0],
    ]

    return k_linear, (W_lin, H_lin)


def compute_spherical_overscan_params(
    k_target: list[list[float]],
    resolution: tuple[int, int],
    distortion_coeffs: list[float],
    margin_deg: float = 2.0,
    n_samples: int = 32,
) -> tuple[float, tuple[int, int]]:
    """
    Compute the FOV and square resolution for a Blender FISHEYE_EQUIDISTANT intermediate render.

    In the equidistant model, pixel radius is proportional to incidence angle θ, which
    stays bounded for any physically realisable lens (unlike tan(θ) in the pinhole model).
    This makes it the correct intermediate representation for Kannala-Brandt fisheye lenses.

    Samples the 4 edges of the target image, unprojects through the inverse Kannala-Brandt
    model to ideal normalised rays, converts to incidence angles θ = atan(‖ray‖), and adds
    a safety margin before computing render parameters.

    Args:
        k_target: 3x3 target K-matrix [[fx,0,cx],[0,fy,cy],[0,0,1]].
        resolution: (width, height) of the target distorted image.
        distortion_coeffs: Kannala-Brandt coefficients [k1, k2, k3, k4].
        margin_deg: Angular margin in degrees added beyond θ_max (default 2°).
        n_samples: Number of sample points per edge.

    Returns:
        (fov_spherical, (R, R)): full FOV in radians and square render resolution.
    """
    W, H = resolution
    fx = k_target[0][0]

    u_edge = np.linspace(0, W - 1, n_samples)
    v_edge = np.linspace(0, H - 1, n_samples)
    u_boundary = np.concatenate([u_edge, u_edge, np.zeros(n_samples), np.full(n_samples, W - 1)])
    v_boundary = np.concatenate([np.zeros(n_samples), np.full(n_samples, H - 1), v_edge, v_edge])

    K_tgt = np.array(k_target, dtype=np.float64)
    D = np.array(distortion_coeffs, dtype=np.float64)
    pts = np.stack([u_boundary, v_boundary], axis=-1).reshape(-1, 1, 2).astype(np.float64)

    undist = cv2.fisheye.undistortPoints(pts, K_tgt, D)
    rho = np.sqrt(undist[:, 0, 0] ** 2 + undist[:, 0, 1] ** 2)
    theta = np.arctan(rho)  # incidence angle; safe for rho → ∞ (→ π/2)

    theta_max_render = float(np.max(theta)) + math.radians(margin_deg)
    fov_spherical = 2.0 * theta_max_render

    # Resolution: ensure angular density ≥ fx pixels/radian (same as target image)
    R = 2 * math.ceil(fx * theta_max_render)
    return fov_spherical, (R, R)


class SceneCompiler:
    """Compiles a high-level JobSpec/GenConfig into a list of rigid SceneRecipes.

    This class owns all randomness and ensures that the resulting recipes
    are purely execution-ready instructions for a "dumb" worker.

    Attributes:
        config: The generation configuration.
        global_seed: Master seed for deterministic derivations.
        output_dir: Path to storage for recipes and textures.
        asset_provider: Resolver for textures and HDRI environments.
        strategy: Current subject rendering strategy (e.g., TagStrategy).
    """

    def __init__(
        self,
        config: GenConfig,
        global_seed: int = 42,
        output_dir: Path | None = None,
        asset_provider: AssetProvider | None = None,
    ):
        self.config = config
        self.global_seed = global_seed
        self.output_dir = output_dir
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        self.asset_provider = asset_provider or AssetProvider()

        # Initialize Subject Strategy
        self.strategy: SubjectStrategy = get_subject_strategy(self.config.scenario.subject)
        self.occluder_strategy: OccluderStrategy | None = get_occluder_strategy(
            self.config.scenario.occluders
        )

        # If it's a TagStrategy, we might need to synchronize its config with GenConfig
        # (Though ideally SubjectConfig should already be correct)
        from .strategy.tags import TagStrategy

        if isinstance(self.strategy, TagStrategy):
            # Update strategy config to match GenConfig if needed
            # For now, we assume SubjectConfig is the source of truth for the strategy
            pass

        # Prepare assets for the subject once per compiler instance
        from render_tag.generation.context import GenerationContext

        ctx = GenerationContext(
            gen_config=self.config, output_dir=self.output_dir or Path("output")
        )
        self.strategy.prepare_assets(ctx)
        if self.occluder_strategy is not None:
            self.occluder_strategy.prepare_assets(ctx)

        # Cache textures
        self.textures = []
        if self.config.scene.texture_dir and self.config.scene.texture_dir.exists():
            valid_exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
            self.textures = [
                p
                for p in self.config.scene.texture_dir.rglob("*")
                if p.suffix.lower() in valid_exts
            ]

    def compile_shards(
        self,
        shard_index: int,
        total_shards: int,
        exclude_ids: set[int] | None = None,
        *,
        total_scenes: int | None = None,
        validate: bool = False,
    ) -> list[SceneRecipe]:
        """Compile a specific shard of scenes.

        Args:
            shard_index: The zero-based index of the current shard.
            total_shards: The total number of shards the job is split into.
            exclude_ids: Optional set of scene IDs to skip.
            total_scenes: Total scenes across all shards. Defaults to
                ``config.dataset.num_scenes``; callers that shard a job spec
                with a different scope can override it.
            validate: If True, each scene is built under the retry-on-invalid
                loop (see ``compile_scene``). Defaults to False to preserve
                existing direct-compile behavior.

        Returns:
            A list of compiled SceneRecipe objects for this shard.
        """
        exclude_ids = exclude_ids or set()
        if total_scenes is None:
            total_scenes = self.config.dataset.num_scenes

        if total_shards > total_scenes:
            total_shards = total_scenes
            if shard_index >= total_shards:
                return []

        scenes_per_shard = total_scenes // total_shards
        start_idx = shard_index * scenes_per_shard
        end_idx = total_scenes if shard_index == total_shards - 1 else start_idx + scenes_per_shard

        recipes = []
        for i in range(start_idx, end_idx):
            if i in exclude_ids:
                continue
            recipes.append(self.compile_scene(i, validate=validate))
        return recipes

    def compile_scene(self, scene_id: int, *, validate: bool = False) -> SceneRecipe:
        """Compile a single scene recipe with full determinism.

        Args:
            scene_id: The unique identifier for the scene.
            validate: When True, run ``RecipeValidator`` on each attempt and
                re-sample (with a new ``derive_seed(..., "attempt", n)`` seed)
                until the recipe is free of errors and non-cache warnings.
                Raises ``RuntimeError`` if 50 attempts all fail. Defaults to
                False, which returns the first build deterministically.

        Returns:
            A fully resolved SceneRecipe with all randomness removed.
        """
        scene_seed = derive_seed(self.global_seed, "scene", scene_id)

        if not validate:
            return self._build_recipe(scene_id, scene_seed)

        from ..core.validator import CACHE_PENDING_WARNING_PREFIX, RecipeValidator

        scene_logger = logger.bind(scene_id=scene_id, seed=scene_seed)

        for attempt in range(MAX_VALIDATION_RETRIES):
            attempt_seed = derive_seed(scene_seed, "attempt", attempt)
            recipe = self._build_recipe(scene_id, attempt_seed)

            validator = RecipeValidator(recipe)
            validator.validate()

            # Cache-pending warnings are expected: the TagStrategy references
            # PNGs that prep_stage._pregenerate_tags writes immediately after
            # compilation. They are not a reason to re-sample.
            relevant_warnings = [
                w for w in validator.warnings if CACHE_PENDING_WARNING_PREFIX not in w
            ]

            if not validator.errors and not relevant_warnings:
                return recipe

            scene_logger.debug(
                f"Scene {scene_id} attempt {attempt} failed validation "
                f"(Errors: {len(validator.errors)}, "
                f"Warnings: {len(validator.warnings)}). Re-sampling...",
                attempt=attempt,
            )

        errors_preview = "; ".join(validator.errors[:3]) or "(no errors)"
        warnings_preview = "; ".join(relevant_warnings[:3]) or "(no warnings)"
        raise RuntimeError(
            f"Could not generate a valid scene for ID {scene_id} after "
            f"{MAX_VALIDATION_RETRIES} attempts. "
            f"Last errors: {errors_preview}. Last warnings: {warnings_preview}."
        )

    def save_recipe_json(
        self, recipes: list[SceneRecipe], filename: str = "scene_recipes.json"
    ) -> Path:
        """Serialize a list of recipes to ``{output_dir}/{filename}``."""
        if self.output_dir is None:
            raise ValueError("SceneCompiler.save_recipe_json requires output_dir to be set.")
        path = self.output_dir / filename
        data = [r.model_dump(mode="json") for r in recipes]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def _build_recipe(self, scene_id: int, seed: int) -> SceneRecipe:
        """Internal build logic that resolves all ranges into absolute values."""
        recipe = SceneRecipe(
            scene_id=scene_id,
            random_seed=seed,
            renderer=self.config.renderer,
        )

        world_seed = derive_seed(seed, "world", 0)
        recipe.world = self._build_world_recipe(scene_id, world_seed)

        from render_tag.generation.context import GenerationContext

        ctx = GenerationContext(
            gen_config=self.config, output_dir=self.output_dir or Path("output")
        )
        objects = self.strategy.sample_pose(seed, ctx)

        # Cameras must be sampled before occluders so the occluder strategy can
        # pick plate placements that avoid sitting between any camera and the tag.
        recipe.cameras = self._sample_camera_recipes(scene_id, seed, objects)

        if self.occluder_strategy is not None:
            tag_anchors: list[tuple[float, float, float]] = []
            max_r = 0.0
            for o in objects:
                if o.type not in {"TAG", "BOARD"}:
                    continue
                cx, cy, cz = float(o.location[0]), float(o.location[1]), float(o.location[2])
                tag_anchors.append((cx, cy, cz))
                
                # Approximate radius of this object
                size_m = float(
                    o.properties.get("tag_size")
                    or o.properties.get("size_along_edge_m")
                    or o.properties.get("square_size")
                    or 0.0
                )
                if size_m > 0.0:
                    # Bounding circle radius
                    obj_r = size_m / math.sqrt(2.0)
                    # Cluster radius is max distance from origin to any corner
                    dist_to_center = math.hypot(cx, cy)
                    max_r = max(max_r, dist_to_center + obj_r)

            if tag_anchors:
                # 1. Calculate the true cluster centroid
                anchors_np = np.array(tag_anchors)
                cluster_centroid = np.mean(anchors_np, axis=0)
                cx_c, cy_c, cz_c = float(cluster_centroid[0]), float(cluster_centroid[1]), float(cluster_centroid[2])

                # 2. For culling, we protect the entire cluster area
                culling_positions = []
                # First element MUST be the centroid for shadow anchoring
                culling_positions.append((cx_c, cy_c, cz_c))
                
                for cx, cy, cz in tag_anchors:
                    culling_positions.append((cx, cy, cz))
                    # Protect the 4 corners of the cluster bounding box
                    # (simplified as centroid +/- cluster_radius)
                    # Use a small set of points to represent the 'forbidden' zone.
                    for dx, dy in [(max_r, max_r), (max_r, -max_r), (-max_r, max_r), (-max_r, -max_r)]:
                        culling_positions.append((cx_c + dx, cy_c + dy, cz))

                objects.extend(
                    self.occluder_strategy.sample_pose(
                        seed, ctx, culling_positions, recipe.cameras, target_radius=max_r
                    )
                )

        recipe.objects = objects

        return recipe

    def _build_world_recipe(self, scene_id: int, seed: int) -> WorldRecipe:
        """Build the world/environment part of the recipe."""
        rng = np.random.default_rng(seed)
        scene_config = self.config.scene
        lighting_config = scene_config.lighting

        texture_path = None
        texture_scale = 1.0
        texture_rotation = 0.0

        if self.textures:
            pool = list(self.textures)
            rng.shuffle(pool)
            raw_path = str(pool[scene_id % len(pool)])
            texture_path = str(self.asset_provider.resolve_path(raw_path).absolute())

            min_s = scene_config.texture_scale_min
            max_s = scene_config.texture_scale_max
            if max_s / min_s > 10.0:
                log_min = math.log(min_s)
                log_max = math.log(max_s)
                texture_scale = math.exp(rng.uniform(log_min, log_max))
            else:
                texture_scale = rng.uniform(min_s, max_s)

            if scene_config.random_texture_rotation:
                texture_rotation = rng.uniform(0, 2 * np.pi)

        background_hdri = None
        if scene_config.background_hdri:
            background_hdri = str(
                self.asset_provider.resolve_path(str(scene_config.background_hdri)).absolute()
            )

        num_lights = 3
        lights = []
        for l_idx in range(num_lights):
            l_seed = derive_seed(seed, "light", l_idx)
            l_rng = np.random.default_rng(l_seed)

            theta = l_rng.uniform(0, 2 * math.pi)
            phi = l_rng.uniform(0.2, 0.8) * math.pi / 2
            radius = l_rng.uniform(2, 5)

            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.sin(phi) * math.sin(theta)
            z = radius * math.cos(phi)

            intensity = (
                l_rng.uniform(lighting_config.intensity_min, lighting_config.intensity_max)
                / num_lights
            )

            lights.append(
                LightRecipe(
                    location=[x, y, z],
                    intensity=intensity,
                    radius=l_rng.uniform(lighting_config.radius_min, lighting_config.radius_max),
                    color=[1.0, 1.0, 1.0],
                )
            )

        for cfg in lighting_config.directional:
            lights.append(_build_sun_light_recipe(cfg))

        return WorldRecipe(
            background_hdri=background_hdri,
            lights=lights,
            texture_path=texture_path,
            texture_scale=texture_scale,
            texture_rotation=texture_rotation,
        )

    def _calculate_ppm_distance(self, target_tag, np_rng) -> float | None:
        """Calculate override distance for a target PPM."""
        from ..core.geometry.projection_math import solve_distance_for_ppm

        camera_config = self.config.camera
        if not camera_config.ppm_constraint:
            return None

        f_px = camera_config.resolution[0] / (2.0 * np.tan(np.radians(camera_config.fov) / 2.0))
        target_ppm = np_rng.uniform(
            camera_config.ppm_constraint.min, camera_config.ppm_constraint.max
        )

        # Use active marker size (black border) for PPM calculation
        tag_size_m = target_tag.properties.get("tag_size", 0.1)
        if target_tag.type == "TAG":
            from render_tag.core.constants import TAG_GRID_SIZES

            family = target_tag.properties.get("tag_family", "tag36h11")
            margin_bits = target_tag.properties.get("margin_bits", 0)
            grid_size = TAG_GRID_SIZES.get(family, 8)
            total_bits = grid_size + (2 * margin_bits)
            tag_size_m = tag_size_m * (grid_size / total_bits)
        elif target_tag.type == "BOARD" and target_tag.board:
            tag_size_m = target_tag.board.marker_size

        from render_tag.core.constants import TAG_GRID_SIZES

        return solve_distance_for_ppm(
            target_ppm=target_ppm,
            tag_size_m=tag_size_m,
            focal_length_px=f_px,
            tag_grid_size=TAG_GRID_SIZES.get(
                target_tag.properties.get("tag_family", "tag36h11"), 8
            ),
        )

    def _sample_single_pose(self, np_rng, dist_override, elev_override, target_tag):
        """Sample a single valid camera pose using rejection sampling."""
        camera_config = self.config.camera
        scenario = self.config.scenario

        # Staff Engineer: Use target tag location as look-at point in random mode to
        # ensure visibility.
        # In sweep modes, we look at the origin [0,0,0] to maintain the geometric contract
        # relative to the center of the world.
        if scenario.sampling_mode == "random" and target_tag:
            look_at = np.array(target_tag.location)
        else:
            look_at = np.array([0.0, 0.0, 0.0])

        for _ in range(50):  # Increased retries for better coverage of edge cases
            # 1. Determine camera location parameters
            dist = (
                dist_override
                if dist_override is not None
                else np_rng.uniform(camera_config.min_distance, camera_config.max_distance)
            )
            elev = (
                elev_override
                if elev_override is not None
                else (
                    camera_config.elevation
                    if camera_config.elevation is not None
                    else np_rng.uniform(camera_config.min_elevation, camera_config.max_elevation)
                )
            )
            azim = (
                camera_config.azimuth
                if camera_config.azimuth is not None
                else np_rng.uniform(0, 2 * np.pi)
            )

            # 2. Sample target position in image frame if in random mode
            target_image_pos = None
            if scenario.sampling_mode == "random" and target_tag:
                # Estimate tag angular size to define a safe sampling margin.
                # Max extent from center is diagonal: size * sqrt(2) / 2 approx 0.707 * size.
                # We use a 1.0x factor to be very safe against roll and perspective distortion.
                tag_size = target_tag.properties.get("tag_size", 0.1)
                if target_tag.type == "BOARD" and target_tag.board:
                    tag_size = max(
                        target_tag.board.cols * target_tag.board.marker_size,
                        target_tag.board.rows * target_tag.board.marker_size,
                    )

                f_px = camera_config.resolution[0] / (
                    2.0 * np.tan(np.radians(camera_config.fov) / 2.0)
                )
                pixel_margin = (f_px * tag_size) / dist

                w, h = camera_config.resolution
                if pixel_margin * 2 < min(w, h):
                    u = np_rng.uniform(pixel_margin, w - pixel_margin)
                    v = np_rng.uniform(pixel_margin, h - pixel_margin)
                    target_image_pos = np.array([u, v])

            # 3. Sample roll
            roll = (
                np_rng.uniform(
                    np.radians(camera_config.min_roll), np.radians(camera_config.max_roll)
                )
                if abs(camera_config.max_roll - camera_config.min_roll) > 1e-6
                else 0.0
            )

            # 4. Generate candidate pose
            pose = sample_camera_pose(
                look_at_point=look_at,
                distance=dist,
                elevation=elev,
                azimuth=azim,
                inplane_rot=roll,
                target_image_pos=target_image_pos,
                k_matrix=camera_config.get_k_matrix(),
                rng=np_rng,
            )

            # 5. Validate all constraints
            if self._validate_pose_constraints(pose, target_tag):
                return pose

        return None

    def _sample_camera_recipes(self, scene_id: int, seed: int, objects: list) -> list[CameraRecipe]:
        """Sample multiple camera poses and create recipes."""
        camera_seed = derive_seed(seed, "camera", 0)
        np_rng = np.random.default_rng(camera_seed)
        camera_config = self.config.camera
        scenario = self.config.scenario

        # Find potential targets for orientation/sizing constraints
        # Prefer actual TAGs, fallback to any object
        all_tags = [obj for obj in objects if obj.type == "TAG"]

        camera_recipes = []

        effective_iso_noise, effective_sensor_noise = derive_iso_coupled_noise(camera_config)
        base_noise_dict = (
            effective_sensor_noise.model_dump() if effective_sensor_noise is not None else None
        )

        for cam_idx in range(camera_config.samples_per_scene):
            # Select target tag for this specific camera sample to maximize diversity
            target_tag = None
            if all_tags:
                target_tag = np_rng.choice(all_tags)
            elif objects:
                target_tag = objects[0]

            dist_override = None
            elev_override = None

            if self.config.dataset.num_scenes > 1:
                t = scene_id / (self.config.dataset.num_scenes - 1)
                if scenario.sampling_mode == "distance":
                    dist_override = camera_config.min_distance + t * (
                        camera_config.max_distance - camera_config.min_distance
                    )
                elif scenario.sampling_mode == "angle":
                    elev_override = camera_config.min_elevation + t * (
                        camera_config.max_elevation - camera_config.min_elevation
                    )

            # PPM constraint only applies if not already in a sweep mode
            if scenario.sampling_mode == "random" and camera_config.ppm_constraint and target_tag:
                dist_override = self._calculate_ppm_distance(target_tag, np_rng)
                # Ensure PPM distance respects configured bounds
                if dist_override is not None:
                    dist_override = np.clip(
                        dist_override, camera_config.min_distance, camera_config.max_distance
                    )

            pose = self._sample_single_pose(np_rng, dist_override, elev_override, target_tag)

            if not pose:
                # Proper fix: Raise error if we cannot find a valid iose after rejection sampling.
                # This ensures we don't generate invalid/incomplete recipes.
                raise ValueError(
                    f"Failed to sample a valid camera pose for scene {scene_id} "
                    f"after 20 attempts with constraints."
                )

            velocity = None
            if camera_config.velocity_mean > 0 or camera_config.velocity_std > 0:
                direction = np_rng.normal(size=3)
                norm = np.linalg.norm(direction)
                direction = direction / norm if norm > 1e-6 else np.array([0.0, 0.0, 1.0])
                magnitude = max(
                    0.0, np_rng.normal(camera_config.velocity_mean, camera_config.velocity_std)
                )
                velocity = (direction * magnitude).tolist()

            if base_noise_dict is not None:
                noise_recipe = {
                    **base_noise_dict,
                    "seed": derive_seed(camera_seed, "noise", cam_idx),
                }
            else:
                noise_recipe = None

            k_matrix = camera_config.get_k_matrix()
            dist_model = camera_config.intrinsics.distortion_model
            dist_coeffs = list(camera_config.intrinsics.get_distortion_coeffs())
            has_dist = has_active_distortion(dist_coeffs)

            k_overscan: list[list[float]] | None = None
            res_overscan: list[int] | None = None
            fov_spherical: float | None = None
            res_spherical: list[int] | None = None
            if has_dist:
                if dist_model == "kannala_brandt":
                    fov_sph, (r_w, r_h) = compute_spherical_overscan_params(
                        k_matrix, camera_config.resolution, dist_coeffs
                    )
                    fov_spherical = fov_sph
                    res_spherical = [r_w, r_h]
                else:
                    k_overscan, (w_lin, h_lin) = compute_overscan_intrinsics(
                        k_matrix, camera_config.resolution, dist_coeffs, distortion_model=dist_model
                    )
                    res_overscan = [w_lin, h_lin]

            camera_recipes.append(
                CameraRecipe(
                    transform_matrix=pose.transform_matrix.tolist(),
                    intrinsics=CameraIntrinsics(
                        resolution=list(camera_config.resolution),
                        k_matrix=k_matrix,
                        fov=camera_config.fov,
                        distortion_model=dist_model if has_dist else "none",
                        distortion_coeffs=dist_coeffs if has_dist else [],
                        k_matrix_overscan=k_overscan,
                        resolution_overscan=res_overscan,
                        fov_spherical=fov_spherical,
                        resolution_spherical=res_spherical,
                        eval_margin_px=camera_config.eval_margin_px,
                    ),
                    sensor_dynamics=SensorDynamicsRecipe(
                        velocity=velocity,
                        shutter_time_ms=camera_config.sensor_dynamics.shutter_time_ms,
                        rolling_shutter_duration_ms=camera_config.sensor_dynamics.rolling_shutter_duration_ms,
                    ),
                    fstop=camera_config.fstop,
                    focus_distance=camera_config.focus_distance,
                    min_tag_pixels=camera_config.min_tag_pixels,
                    max_tag_pixels=camera_config.max_tag_pixels,
                    iso_noise=effective_iso_noise,
                    sensor_noise=noise_recipe,
                    tone_mapping=camera_config.tone_mapping,
                    dynamic_range_db=camera_config.dynamic_range_db,
                )
            )
        return camera_recipes

    def _validate_pose_constraints(self, pose, target_tag) -> bool:
        """Validate orientation and sizing constraints for a sampled pose."""
        if not target_tag:
            return True

        from ..core.config import get_min_pixel_area
        from ..core.geometry.projection_math import (
            calculate_pixel_area,
            get_world_matrix,
            project_points,
        )

        camera_config = self.config.camera

        # 1. Orientation check
        tag_world_mat = get_world_matrix(
            target_tag.location, target_tag.rotation_euler, target_tag.scale
        )
        tag_normal = tag_world_mat[:3, 2]  # Z-up normal
        if not is_facing_camera(
            tag_location=np.array(target_tag.location),
            tag_normal=tag_normal,
            camera_location=pose.location,
            min_dot=0.1,  # Relaxed to ~84 degrees to support low-elevation tests/views
        ):
            return False

        # 2. Mandatory Frame Visibility check
        # All 4 corners of the tag (or target object) must be within the frame
        if target_tag.type == "BOARD" and target_tag.board:
            # Rigid Calibration Board (Strategy uses scale in recipe)
            hw, hh = 0.5, 0.5
        elif target_tag.type == "BOARD":
            # Background Board (TagStrategy uses unit scale in recipe)
            cols = target_tag.properties.get("cols", 1)
            rows = target_tag.properties.get("rows", 1)
            sq = target_tag.properties.get("square_size", 0.1)
            hw = (cols * sq) / 2.0
            hh = (rows * sq) / 2.0
        else:
            # Individual Tag
            size = target_tag.properties.get("tag_size", 0.1)
            hw = hh = size / 2.0

        corners_local = np.array([[-hw, -hh, 0], [hw, -hh, 0], [hw, hh, 0], [-hw, hh, 0]])
        corners_world = (tag_world_mat @ np.hstack([corners_local, np.ones((4, 1))]).T).T[:, :3]
        dist_coeffs = list(camera_config.intrinsics.get_distortion_coeffs())
        pixels = project_points(
            corners_world,
            pose.transform_matrix,
            list(camera_config.resolution),
            camera_config.get_k_matrix(),
            distortion_coeffs=dist_coeffs or None,
            distortion_model=camera_config.intrinsics.distortion_model,
        )

        # Strict boundary check (all corners must be visible)
        if not all(
            0 <= px <= camera_config.resolution[0] and 0 <= py <= camera_config.resolution[1]
            for px, py in pixels
        ):
            return False

        # 3. Optional Sizing constraints validation (Pixel Area)
        if camera_config.min_tag_pixels or camera_config.max_tag_pixels:
            family = target_tag.properties.get("tag_family", "tag36h11")
            min_allowed = camera_config.min_tag_pixels or get_min_pixel_area(family)
            max_allowed = camera_config.max_tag_pixels or (
                camera_config.resolution[0] * camera_config.resolution[1]
            )

            if not (min_allowed <= calculate_pixel_area(pixels) <= max_allowed):
                return False

        return True
