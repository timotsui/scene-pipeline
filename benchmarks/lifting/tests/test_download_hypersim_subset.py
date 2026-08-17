import unittest
import zipfile

from benchmarks.lifting.download_hypersim_subset import (
    _evenly_spaced,
    select_entries,
)


class DownloadHypersimSubsetTests(unittest.TestCase):
    def test_evenly_spaced_includes_trajectory_ends(self):
        self.assertEqual(_evenly_spaced(list(range(10)), 3), [0, 4, 9])

    def test_selects_same_frames_for_all_modalities(self):
        scene = "ai_001_001"
        names = []
        for suffix in (
            "metadata_scene.csv",
            "metadata_cameras.csv",
        ):
            names.append(f"{scene}/_detail/{suffix}")
        names.extend(
            f"{scene}/_detail/cam_00/{name}"
            for name in (
                "camera_keyframe_frame_indices.hdf5",
                "camera_keyframe_orientations.hdf5",
                "camera_keyframe_positions.hdf5",
                "metadata_camera.csv",
            )
        )
        names.extend(
            f"{scene}/_detail/mesh/metadata_semantic_instance_"
            f"bounding_box_object_aligned_2d_{kind}.hdf5"
            for kind in ("extents", "orientations", "positions")
        )
        for frame in range(5):
            names.extend(
                (
                    f"{scene}/images/scene_cam_00_final_hdf5/"
                    f"frame.{frame:04d}.color.hdf5",
                    f"{scene}/images/scene_cam_00_geometry_hdf5/"
                    f"frame.{frame:04d}.position.hdf5",
                )
            )
        entries = [zipfile.ZipInfo(name) for name in names]

        selected, frames = select_entries(
            entries, "cam_00", ("detail", "color", "position"), 3
        )

        self.assertEqual(frames, [0, 2, 4])
        frame_names = [entry.filename for entry in selected if "/frame." in entry.filename]
        self.assertEqual(len(frame_names), 6)


if __name__ == "__main__":
    unittest.main()
