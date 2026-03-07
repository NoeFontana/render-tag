from unittest.mock import patch


# We mock fiftyone to avoid database dependency in unit tests
@patch("fiftyone.dataset_exists", return_value=False)
@patch("fiftyone.delete_dataset")
@patch("fiftyone.Dataset")
def test_fiftyone_schema_definition(mock_dataset_cls, mock_delete, mock_exists):
    from render_tag.viz.fiftyone_tool import create_dataset

    mock_dataset = mock_dataset_cls.return_value

    # ACT
    create_dataset("test_dataset")

    # VERIFY
    # Check that custom fields are added to the detection model
    # Note: In FiftyOne, fields are added via add_sample_field or during sample creation.
    # Here we expect our create_dataset to register them.
    calls = [call[0][0] for call in mock_dataset.add_sample_field.call_args_list]

    expected_fields = ["distance", "angle_of_incidence", "ppm", "position", "rotation_quaternion"]
    for field in expected_fields:
        assert any(field in c for c in calls)
