import importlib.util
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from PIL import Image, ImageDraw

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "pack_frames.py"
spec = importlib.util.spec_from_file_location("pack_frames", MODULE)
packer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packer)


class PackFramesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def frame(self, name, x=6, color=(103, 75, 52, 255), size=(32, 32)):
        image = Image.new("RGBA", size)
        ImageDraw.Draw(image).rectangle((x, 5, x + 7, 21), fill=color)
        image.putpixel((x - 1, 10), (103, 75, 52, 80))
        image.save(self.source / name)
        return image

    def args(self, **overrides):
        values = dict(frames=self.source, out=self.root / "output", durations="85",
                      loop=False, exclude_last=False, anchors=None, padding=2, preview_scale=2)
        values.update(overrides)
        return Namespace(**values)

    def image_info(self, path):
        with Image.open(path) as image:
            return dict(image.info)

    def image_bytes(self, path):
        with Image.open(path) as image:
            return image.tobytes()

    def test_preserves_rgba_and_shared_coordinates_while_natural_sorting(self):
        second = self.frame("frame-10.png", x=13)
        first = self.frame("frame-2.png", x=6)
        out = packer.pack(self.args())
        manifest = json.loads((out / "animation.json").read_text())
        self.assertEqual([f["source"] for f in manifest["frames"]], ["frame-2.png", "frame-10.png"])
        self.assertEqual(manifest["frames"][0]["translation"], manifest["frames"][1]["translation"])
        for source, entry in zip([first, second], manifest["frames"]):
            result = Image.open(out / entry["file"]).convert("RGBA")
            dx, dy = entry["translation"]
            for y in range(source.height):
                for x in range(source.width):
                    if source.getpixel((x, y))[3]:
                        self.assertEqual(source.getpixel((x, y)), result.getpixel((x + dx, y + dy)))
        facts = json.loads((out / "report.json").read_text())
        self.assertEqual(facts["facts"][0]["softAlphaPixels"], 1)
        self.assertEqual(facts["facts"][0]["opaqueMeanRgb"], [103, 75, 52])
        self.assertEqual(manifest["preview"]["gifDurationsMs"], [90, 90])
        self.assertNotIn("loop", self.image_info(out / "preview.gif"))
        self.assertEqual(self.image_info(out / "preview.webp")["loop"], 1)

    def test_manual_anchors_translate_without_scaling_and_remain_in_canvas(self):
        self.frame("frame-0.png", x=6)
        self.frame("frame-1.png", x=10)
        anchors = self.root / "anchors.json"
        anchors.write_text(json.dumps({"frame-0.png": [9, 25], "frame-1.png": [13, 25]}))
        out = packer.pack(self.args(anchors=anchors, loop=True))
        manifest = json.loads((out / "animation.json").read_text())
        self.assertEqual(manifest["frames"][1]["translation"][0], manifest["frames"][0]["translation"][0] - 4)
        a = self.image_bytes(out / "frames/frame-000.png")
        b = self.image_bytes(out / "frames/frame-001.png")
        self.assertEqual(a, b)
        self.assertEqual(manifest["anchor"], [6, 22])
        self.assertEqual(self.image_info(out / "preview.gif")["loop"], 0)

    def test_explicit_exclusion_keeps_original_duration_mapping(self):
        for i in range(3):
            self.frame(f"frame-{i}.png", x=6 + i)
        out = packer.pack(self.args(durations="120,40,80", exclude_last=True))
        manifest = json.loads((out / "animation.json").read_text())
        self.assertEqual(manifest["excludedSources"], ["frame-2.png"])
        self.assertEqual([f["durationMs"] for f in manifest["frames"]], [120, 40])

    def test_animation_decoders_preserve_visible_pixels_soft_alpha_and_elapsed_time(self):
        sources = [self.frame("frame-0.png"),
                   self.frame("frame-1.png", x=11, color=(42, 97, 121, 255))]
        out = packer.pack(self.args(durations="85,115", loop=True))
        manifest = json.loads((out / "animation.json").read_text())
        expected = []
        for source, entry in zip(sources, manifest["frames"]):
            normalized = Image.new("RGBA", tuple(manifest["size"]))
            normalized.paste(source, tuple(entry["translation"]))
            scale = manifest["preview"]["scale"]
            expected.append(normalized.resize((normalized.width * scale, normalized.height * scale),
                                              Image.Resampling.NEAREST))
        for extension in ["webp", "gif"]:
            with self.subTest(extension=extension), Image.open(out / f"preview.{extension}") as animation:
                self.assertEqual(animation.n_frames, 2, "distinct poses must remain distinct")
                elapsed = 0
                for index in range(animation.n_frames):
                    animation.seek(index)
                    animation.load()
                    elapsed += animation.info["duration"]
                    if extension == "webp":
                        decoded = animation.convert("RGBA")
                        self.assertEqual(decoded.getchannel("A").tobytes(), expected[index].getchannel("A").tobytes())
                        self.assertGreater(decoded.getchannel("A").histogram()[80], 0, "soft alpha survives encoding")
                        for y in range(decoded.height):
                            for x in range(decoded.width):
                                pixel = expected[index].getpixel((x, y))
                                if pixel[3] > 0:
                                    self.assertEqual(decoded.getpixel((x, y)), pixel)
                    else:
                        background = Image.new("RGBA", expected[index].size, (237, 231, 212, 255))
                        flattened = Image.alpha_composite(background, expected[index]).convert("RGB")
                        # This fixture has fewer than 256 colors, so no palette approximation is necessary.
                        self.assertEqual(animation.convert("RGB").tobytes(), flattened.tobytes())
                durations = (manifest["preview"]["gifDurationsMs"] if extension == "gif"
                             else [entry["durationMs"] for entry in manifest["frames"]])
                self.assertEqual(elapsed, sum(durations))

    def test_invalid_inputs_do_not_create_output(self):
        for mode in ["rgb", "opaque", "empty", "mixed", "durations"]:
            with self.subTest(mode=mode):
                for file in self.source.iterdir():
                    file.unlink()
                self.frame("frame-0.png")
                if mode == "rgb":
                    Image.new("RGB", (32, 32), "white").save(self.source / "frame-1.png")
                elif mode == "opaque":
                    Image.new("RGBA", (32, 32), "white").save(self.source / "frame-1.png")
                elif mode == "empty":
                    Image.new("RGBA", (32, 32)).save(self.source / "frame-1.png")
                elif mode == "mixed":
                    self.frame("frame-1.png", size=(40, 40))
                with self.assertRaises(ValueError):
                    packer.pack(self.args(durations="40,60" if mode == "durations" else "80"))
                self.assertFalse((self.root / "output").exists())

    def test_refuses_nonempty_destination_and_keeps_existing_files(self):
        self.frame("frame-0.png")
        out = self.root / "output"
        out.mkdir()
        (out / "keep.txt").write_text("keep")
        with self.assertRaises(ValueError):
            packer.pack(self.args())
        self.assertEqual((out / "keep.txt").read_text(), "keep")


if __name__ == "__main__":
    unittest.main()
