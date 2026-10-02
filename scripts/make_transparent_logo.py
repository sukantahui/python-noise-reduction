"""Script to remove white background from CNAT logo and export transparent PNG and ICO."""
import numpy as np
from PIL import Image
from pathlib import Path


def create_transparent_cnat_logo(
    input_path: Path = Path("assets/logo.png"),
    output_png_paths: list[Path] = None,
    output_ico_paths: list[Path] = None
) -> None:
    """Removes the white background portion from the CNAT logo and creates smooth anti-aliased transparent PNG and ICO."""
    if output_png_paths is None:
        output_png_paths = [Path("assets/logo.png"), Path("src/gui/assets/logo.png")]
    if output_ico_paths is None:
        output_ico_paths = [Path("assets/logo.ico"), Path("src/gui/assets/logo.ico")]

    img = Image.open(input_path).convert("RGBA")
    data = np.array(img, dtype=np.float32)

    rgb = data[:, :, :3]
    # Compute Euclidean distance from pure white (255, 255, 255)
    dist_from_white = np.linalg.norm(255.0 - rgb, axis=-1)

    low_thresh = 10.0
    high_thresh = 40.0

    alpha = np.clip((dist_from_white - low_thresh) / (high_thresh - low_thresh), 0.0, 1.0) * 255.0
    alpha_norm = alpha / 255.0
    alpha_mask = alpha_norm > 0.01

    clean_rgb = rgb.copy()
    for c in range(3):
        channel = clean_rgb[:, :, c]
        # Defringe / un-premultiply white from anti-aliased border pixels
        defringed = (channel - (1.0 - alpha_norm) * 255.0) / np.maximum(alpha_norm, 0.05)
        clean_rgb[:, :, c] = np.where(alpha_mask, np.clip(defringed, 0.0, 255.0), 0.0)

    result_data = np.zeros_like(data, dtype=np.uint8)
    result_data[:, :, :3] = np.uint8(clean_rgb)
    result_data[:, :, 3] = np.uint8(np.round(alpha))

    result_img = Image.fromarray(result_data, "RGBA")

    for png_path in output_png_paths:
        png_path.parent.mkdir(parents=True, exist_ok=True)
        result_img.save(png_path, "PNG", optimize=True)
        print(f"Saved transparent PNG to: {png_path}")

    for ico_path in output_ico_paths:
        ico_path.parent.mkdir(parents=True, exist_ok=True)
        result_img.save(
            ico_path,
            format="ICO",
            sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        )
        print(f"Saved multi-resolution ICO to: {ico_path}")


if __name__ == "__main__":
    create_transparent_cnat_logo()
