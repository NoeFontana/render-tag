"""
FiftyOne tool for visualizing render-tag datasets.
"""

import fiftyone as fo

def create_dataset(name: str) -> fo.Dataset:
    """
    Create a new FiftyOne dataset with the required schema.
    """
    dataset = fo.Dataset(name)
    
    # Register custom metadata fields on detections
    # These will be hydrated from rich_truth.json later
    dataset.add_sample_field(
        "ground_truth.detections.distance",
        fo.FloatField,
        description="Euclidean distance to camera (meters)",
    )
    dataset.add_sample_field(
        "ground_truth.detections.angle_of_incidence",
        fo.FloatField,
        description="Angle of incidence (degrees)",
    )
    dataset.add_sample_field(
        "ground_truth.detections.ppm",
        fo.FloatField,
        description="Pixels Per Module (resolution)",
    )
    dataset.add_sample_field(
        "ground_truth.detections.position",
        fo.ListField,
        description="3D position [x, y, z]",
    )
    dataset.add_sample_field(
        "ground_truth.detections.rotation_quaternion",
        fo.ListField,
        description="3D rotation [w, x, y, z]",
    )
    
    return dataset
