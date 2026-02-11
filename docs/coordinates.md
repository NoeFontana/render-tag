# Coordinate Systems

Correct orientation and corner ordering are critical for fiducial marker detection. `render-tag` uses standard robotics and computer vision conventions.

## World Space
- **Z-axis**: Up
- **X-axis**: Forward
- **Y-axis**: Left
- **Origin**: Center of the ground plane.

## Camera Space (OpenCV Convention)
While Blender uses a different camera convention (Z-forward, Y-up), `render-tag` exports all metadata in the **OpenCV convention**:
- **Z-axis**: Forward (optical axis)
- **X-axis**: Right
- **Y-axis**: Down

## Tag Corners
Corners are indexed from 0 to 3 in **counter-clockwise (CCW)** order, starting from the bottom-left of the tag image.

| Index | Name | Local Coordinate |
|-------|------|------------------|
| 0 | Bottom-Left (BL) | (-s/2, -s/2) |
| 1 | Bottom-Right (BR) | (s/2, -s/2) |
| 2 | Top-Right (TR) | (s/2, s/2) |
| 3 | Top-Left (TL) | (-s/2, s/2) |

*(where s is the marker size)*

## Angle of Incidence
Defined as the angle between the camera's optical axis and the surface normal of the tag. 0° means the camera is looking directly at the tag face.
