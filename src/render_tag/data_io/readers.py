"""Structured readers for render-tag datasets.

Provides Pydantic-validated ingestion of ``rich_truth.json`` with convenience
accessors for calibration workflows.  The :class:`CalibrationFrame` class
yields matched 2D/3D point pairs ready for ``cv2.solvePnP`` or
``cv2.calibrateCamera``.
"""

from __future__ import annotations

import functools
import json
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from render_tag.core.schema.base import (
    KEYPOINT_SENTINEL,
    DetectionRecord,
    is_sentinel_keypoint,
)
from render_tag.core.schema.board import BoardDefinition, BoardType


class CalibrationFrame:
    """A single image's calibration data with matched 2D-3D point pairs.

    Args:
        board_record: The BOARD-type DetectionRecord for this image.
    """

    def __init__(self, image_id: str, board_record: DetectionRecord) -> None:
        if board_record.board_definition is None:
            raise ValueError(f"BOARD record for {image_id} has no board_definition")
        self.record = board_record
        self._bd: BoardDefinition = board_record.board_definition

    @property
    def image_id(self) -> str:
        """Image identifier (derived from the underlying record)."""
        return self.record.image_id

    @property
    def board_definition(self) -> BoardDefinition:
        """The board geometry descriptor."""
        return self._bd

    @functools.cached_property
    def k_matrix(self) -> np.ndarray:
        """3x3 camera intrinsic matrix."""
        if self.record.k_matrix is None:
            raise ValueError(f"BOARD record for {self.image_id} has no k_matrix")
        return np.array(self.record.k_matrix)

    @property
    def resolution(self) -> tuple[int, int]:
        """(width, height) in pixels."""
        if self.record.resolution is None:
            raise ValueError(f"BOARD record for {self.image_id} has no resolution")
        return (self.record.resolution[0], self.record.resolution[1])

    def get_valid_calibration_pairs(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Extract matched 2D image points and 3D object points, filtering sentinels.

        Returns:
            Tuple of ``(obj_pts_3d, img_pts_2d, valid_ids)`` where:

            - ``obj_pts_3d``: ``(N, 3)`` float64 array in mm (board-local frame)
            - ``img_pts_2d``: ``(N, 2)`` float64 array in pixels
            - ``valid_ids``:  ``(N,)`` int32 array of keypoint indices
        """
        if self.record.keypoints is None:
            return (
                np.empty((0, 3), dtype=np.float64),
                np.empty((0, 2), dtype=np.float64),
                np.empty((0,), dtype=np.int32),
            )

        all_obj_pts = _compute_object_points_3d(self._bd)
        keypoints = self.record.keypoints

        valid_ids: list[int] = []
        img_pts: list[tuple[float, float]] = []
        obj_pts: list[tuple[float, float, float]] = []

        for i, (x, y) in enumerate(keypoints):
            if is_sentinel_keypoint(x, y):
                continue
            if i < len(all_obj_pts):
                valid_ids.append(i)
                img_pts.append((x, y))
                obj_pts.append(all_obj_pts[i])

        return (
            np.array(obj_pts, dtype=np.float64).reshape(-1, 3),
            np.array(img_pts, dtype=np.float64).reshape(-1, 2),
            np.array(valid_ids, dtype=np.int32),
        )

    def get_all_keypoints_with_visibility(
        self,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return all keypoints and a boolean visibility mask.

        Returns:
            Tuple of ``(keypoints_2d, visibility)`` where:

            - ``keypoints_2d``: ``(total_keypoints, 2)`` array (sentinels preserved)
            - ``visibility``:   ``(total_keypoints,)`` bool array
        """
        if self.record.keypoints is None:
            n = self._bd.total_keypoints
            return (
                np.full((n, 2), -1.0, dtype=np.float64),
                np.zeros(n, dtype=bool),
            )

        kp = np.array(self.record.keypoints, dtype=np.float64)
        vis = ~np.all(kp == KEYPOINT_SENTINEL, axis=1)
        return kp, vis


class RenderTagDataset:
    """Structured reader for ``rich_truth.json`` datasets.

    Loads and validates all detection records through Pydantic, providing
    typed access to tags, boards, and calibration data.

    Args:
        dataset_path: Directory containing ``rich_truth.json``.
    """

    def __init__(self, dataset_path: Path | str) -> None:
        self._path = Path(dataset_path)
        self._records = _load_records(self._path / "rich_truth.json")
        self._index = _build_index(self._records)

    @classmethod
    def from_json(cls, path: Path | str) -> RenderTagDataset:
        """Load from a specific ``rich_truth.json`` file path.

        Handles backward compatibility: if loaded JSON has ``board_definition``
        nested inside ``metadata`` (old format), it is migrated to the top-level
        field before validation.
        """
        path = Path(path)
        instance = object.__new__(cls)
        instance._path = path.parent
        instance._records = _load_records(path)
        instance._index = _build_index(instance._records)
        return instance

    @classmethod
    def from_records(cls, records: list[DetectionRecord]) -> RenderTagDataset:
        """Create from an existing list of DetectionRecords."""
        instance = object.__new__(cls)
        instance._path = Path(".")
        instance._records = list(records)
        instance._index = _build_index(instance._records)
        return instance

    @property
    def records(self) -> list[DetectionRecord]:
        """All detection records in the dataset."""
        return list(self._records)

    @property
    def image_ids(self) -> list[str]:
        """Unique image IDs in insertion order."""
        return list(self._index.keys())

    def get_records(self, image_id: str) -> list[DetectionRecord]:
        """All records for a given image."""
        return list(self._index.get(image_id, ()))

    def get_board_record(self, image_id: str) -> DetectionRecord | None:
        """The BOARD record for an image, or None."""
        for r in self._index.get(image_id, ()):
            if r.record_type == "BOARD":
                return r
        return None

    def get_tag_records(self, image_id: str) -> list[DetectionRecord]:
        """All TAG records for an image."""
        return [r for r in self._index.get(image_id, ()) if r.record_type == "TAG"]

    def iter_calibration_frames(self) -> Iterator[CalibrationFrame]:
        """Yield a :class:`CalibrationFrame` for each image that has a BOARD record."""
        for image_id in self.image_ids:
            board = self.get_board_record(image_id)
            if board is not None and board.board_definition is not None:
                yield CalibrationFrame(image_id, board)

    def get_calibration_frame(self, image_id: str) -> CalibrationFrame | None:
        """Return a CalibrationFrame for the given image, or None."""
        board = self.get_board_record(image_id)
        if board is not None and board.board_definition is not None:
            return CalibrationFrame(image_id, board)
        return None

    @property
    def board_definition(self) -> BoardDefinition | None:
        """The board definition shared by all frames (from the first BOARD record)."""
        for r in self._records:
            if r.record_type == "BOARD" and r.board_definition is not None:
                return r.board_definition
        return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_records(path: Path) -> list[DetectionRecord]:
    """Load and validate records from a ``rich_truth.json`` file."""
    with open(path) as f:
        raw_records: list[dict] = json.load(f)

    records: list[DetectionRecord] = []
    for raw in raw_records:
        # Migrate old format where board_definition was nested inside metadata
        if "board_definition" not in raw and "metadata" in raw:
            bd = raw.get("metadata", {}).pop("board_definition", None)
            if bd is not None:
                raw["board_definition"] = bd
        records.append(DetectionRecord.model_validate(raw))
    return records


def _build_index(
    records: list[DetectionRecord],
) -> dict[str, list[DetectionRecord]]:
    """Index records by image_id preserving insertion order."""
    index: dict[str, list[DetectionRecord]] = defaultdict(list)
    for r in records:
        index[r.image_id].append(r)
    return dict(index)


@functools.lru_cache(maxsize=32)
def _compute_object_points_3d(
    bd: BoardDefinition,
) -> tuple[tuple[float, float, float], ...]:
    """Reconstruct 3D calibration keypoints from a BoardDefinition.

    Uses the canonical board coordinate system (center-origin, Z=0 plane).
    Points are in millimeters, row-major from top-left, matching the
    serialization order used by ``generation/board.py``.
    """
    square_mm = bd.square_size_mm
    rows, cols = bd.rows, bd.cols

    board_w = cols * square_mm
    board_h = rows * square_mm

    if bd.type == BoardType.CHARUCO:
        start_x = -board_w / 2.0 + square_mm / 2.0
        start_y = board_h / 2.0 - square_mm / 2.0
    elif bd.type == BoardType.APRILGRID:
        start_x = -board_w / 2.0 + square_mm / 2.0
        start_y = board_h / 2.0 - square_mm / 2.0
    else:
        return ()

    points: list[tuple[float, float, float]] = []
    for row in range(rows - 1):
        for col in range(cols - 1):
            sx = start_x + col * square_mm + square_mm / 2.0
            sy = start_y - row * square_mm - square_mm / 2.0
            points.append((sx, sy, 0.0))
    return tuple(points)
