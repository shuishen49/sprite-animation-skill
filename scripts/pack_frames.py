#!/usr/bin/env python3
"""Pack already prepared RGBA poses; never generate, interpolate or scale source poses."""
import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat


def natural_key(path):
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", path.name)]


def read_durations(value, count):
    try:
        values = [int(part.strip()) for part in value.split(",")]
    except ValueError as error:
        raise ValueError("durations must be positive integer milliseconds") from error
    if not values or any(ms <= 0 for ms in values):
        raise ValueError("durations must be positive integer milliseconds")
    if len(values) == 1:
        return values * count
    if len(values) != count:
        raise ValueError(f"expected 1 or {count} duration values, got {len(values)}")
    return values


def load_frames(directory):
    paths = sorted(directory.glob("*.png"), key=natural_key)
    if not paths:
        raise ValueError("frames directory must contain PNG files")
    images, size = [], None
    for path in paths:
        with Image.open(path) as source:
            if "A" not in source.getbands() and "transparency" not in source.info:
                raise ValueError(f"{path.name}: missing alpha channel")
            image = source.convert("RGBA")
        alpha = image.getchannel("A")
        if not alpha.getbbox():
            raise ValueError(f"{path.name}: empty frame")
        if alpha.getextrema()[0] == 255:
            raise ValueError(f"{path.name}: fully opaque image; remove its background first")
        if size is not None and image.size != size:
            raise ValueError(f"{path.name}: mixed canvas sizes; prepare equal-size source frames")
        size = image.size
        images.append(image)
    return paths, images


def load_anchors(path, paths, size):
    if path is None:
        return None
    mapping = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict):
        raise ValueError("anchors must map each source filename to [x, y]")
    anchors = []
    for frame in paths:
        point = mapping.get(frame.name)
        if not isinstance(point, list) or len(point) != 2 or any(type(v) is not int for v in point):
            raise ValueError(f"{frame.name}: provide an integer [x, y] anchor")
        if not (0 <= point[0] <= size[0] and 0 <= point[1] <= size[1]):
            raise ValueError(f"{frame.name}: anchor must be inside the source canvas")
        anchors.append(point)
    return anchors


def normalize(images, anchors, padding):
    # Without anchors retain the source coordinate system, including intentional movement.
    shifts = ([(anchors[0][0] - x, anchors[0][1] - y) for x, y in anchors]
              if anchors else [(0, 0)] * len(images))
    boxes = []
    for image, (dx, dy) in zip(images, shifts):
        left, top, right, bottom = image.getchannel("A").getbbox()
        boxes.append((left + dx, top + dy, right + dx, bottom + dy))
    left = min(box[0] for box in boxes) - padding
    top = min(box[1] for box in boxes) - padding
    right = max(box[2] for box in boxes) + padding
    bottom = max(box[3] for box in boxes) + padding
    # Keep an explicitly supplied ground/hand anchor within the output canvas as well.
    if anchors:
        left = min(left, anchors[0][0] - padding)
        top = min(top, anchors[0][1] - padding)
        right = max(right, anchors[0][0] + padding + 1)
        bottom = max(bottom, anchors[0][1] + padding + 1)
    frames, translations = [], []
    for image, (dx, dy) in zip(images, shifts):
        frame = Image.new("RGBA", (right - left, bottom - top))
        translation = (dx - left, dy - top)
        frame.paste(image, translation)  # No mask: preserve straight RGBA exactly.
        frames.append(frame)
        translations.append(translation)
    anchor = [anchors[0][0] - left, anchors[0][1] - top] if anchors else None
    return frames, translations, anchor


def frame_facts(image):
    alpha = image.getchannel("A")
    histogram = alpha.histogram()
    opaque = alpha.point(lambda value: 255 if value == 255 else 0)
    mean = ImageStat.Stat(image.convert("RGB"), opaque).mean if histogram[255] else None
    return {"bbox": list(alpha.getbbox()), "transparentPixels": histogram[0],
            "softAlphaPixels": sum(histogram[1:255]), "opaquePixels": histogram[255],
            "opaqueMeanRgb": [round(value, 3) for value in mean] if mean else None}


def write_outputs(out, paths, frames, durations, translations, anchor, loop, scale, excluded):
    width, height = frames[0].size
    (out / "frames").mkdir()
    sheet = Image.new("RGBA", (width * len(frames), height))
    entries = []
    for index, (source, frame, ms, translation) in enumerate(zip(paths, frames, durations, translations)):
        filename = f"frames/frame-{index:03d}.png"
        frame.save(out / filename)
        sheet.paste(frame, (index * width, 0))
        entries.append({"index": index, "source": source.name, "file": filename,
                        "rect": [index * width, 0, width, height], "durationMs": ms,
                        "translation": list(translation), "anchor": anchor})
    sheet.save(out / "sheet.png")
    scaled = [frame.resize((width * scale, height * scale), Image.Resampling.NEAREST) for frame in frames]
    backgrounds = []
    for frame in scaled:
        background = Image.new("RGBA", frame.size, (237, 231, 212, 255))
        backgrounds.append(Image.alpha_composite(background, frame).convert("RGB"))
    # GIF cannot retain soft alpha; use an opaque inspection background and 10ms timing.
    gif_durations = [max(10, ((ms + 5) // 10) * 10) for ms in durations]
    gif_options = {"loop": 0} if loop else {}
    backgrounds[0].save(out / "preview.gif", save_all=True, append_images=backgrounds[1:],
                        duration=gif_durations, disposal=2, optimize=False, **gif_options)
    scaled[0].save(out / "preview.webp", save_all=True, append_images=scaled[1:],
                   duration=durations, loop=0 if loop else 1, lossless=True, exact=True)
    columns = min(4, len(frames))
    cell_width, cell_height = width * scale + 16, height * scale + 38
    rows = (len(frames) + columns - 1) // columns
    contact = Image.new("RGB", (columns * cell_width, rows * cell_height), (237, 231, 212))
    draw = ImageDraw.Draw(contact)
    for index, (preview, ms) in enumerate(zip(backgrounds, durations)):
        x, y = index % columns * cell_width, index // columns * cell_height
        contact.paste(preview, (x + 8, y + 8))
        draw.text((x + 8, y + height * scale + 15), f"{index:03d} / {ms}ms", fill=(34, 41, 43))
    contact.save(out / "contact.png")
    manifest = {"schemaVersion": 1, "size": [width, height], "loop": loop,
                "anchor": anchor, "anchorMeaning": "user-supplied" if anchor else "unspecified",
                "sheet": "sheet.png", "frames": entries, "excludedSources": excluded,
                "preview": {"scale": scale, "gifDurationsMs": gif_durations,
                            "gifAlpha": "opaque-background", "webpAlpha": "RGBA"}}
    facts = [frame_facts(frame) for frame in frames]
    report = {"frameCount": len(frames), "size": [width, height], "totalDurationMs": sum(durations),
              "loop": loop, "facts": facts,
              "review": "Geometry and color facts only; manual motion, identity and loop review required.",
              "notes": ["No source pose scaling, interpolation or redraw was performed.",
                        "Preview encoders may merge identical adjacent frames while retaining elapsed time."]}
    (out / "animation.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pack(args):
    directory, out = args.frames.resolve(), args.out.resolve()
    if not directory.is_dir():
        raise ValueError("frames must be an existing directory")
    if out == directory or directory in out.parents:
        raise ValueError("output must be outside the source frames directory")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError("output must be new or an empty directory")
    if args.padding < 0 or args.preview_scale < 1:
        raise ValueError("padding must be nonnegative and preview-scale must be positive")
    paths, images = load_frames(directory)
    durations = read_durations(args.durations, len(paths))
    anchors = load_anchors(args.anchors, paths, images[0].size)
    excluded = []
    if args.exclude_last:
        if len(paths) < 2:
            raise ValueError("exclude-last requires at least two source frames")
        excluded = [paths[-1].name]
        paths, images, durations = paths[:-1], images[:-1], durations[:-1]
        if anchors:
            anchors = anchors[:-1]
    frames, translations, anchor = normalize(images, anchors, args.padding)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".sprite-pack-", dir=out.parent))
    try:
        write_outputs(temporary, paths, frames, durations, translations, anchor,
                      args.loop, args.preview_scale, excluded)
        if out.exists():
            out.rmdir()  # Fails safely if another process populated it meanwhile.
        temporary.rename(out)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, required=True, help="flat directory of same-size RGBA PNG frames")
    parser.add_argument("--out", type=Path, required=True, help="new or empty output directory")
    parser.add_argument("--durations", default="80", help="one duration or one comma-separated ms value per source frame")
    parser.add_argument("--loop", action="store_true", help="loop indefinitely; default is play once")
    parser.add_argument("--exclude-last", action="store_true", help="explicitly remove last frame and its duration")
    parser.add_argument("--anchors", type=Path, help='JSON mapping source filenames to integer [x, y] anchors')
    parser.add_argument("--padding", type=int, default=8)
    parser.add_argument("--preview-scale", type=int, default=2, help="integer preview scale; source PNGs stay unscaled")
    args = parser.parse_args()
    try:
        out = pack(args)
    except (ValueError, OSError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"Packed frames: {out}")


if __name__ == "__main__":
    main()
