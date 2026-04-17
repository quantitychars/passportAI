"""
src/processing/photo.py — Product Photo Standardization

Processes raw product photos into standardized 800x800 PNG files:
  1. Remove background using rembg (U2Net model)
  2. Place subject on white background
  3. Resize/pad to exactly 800x800 pixels
  4. Save as PNG (lossless)

The output photo is used in the DPP package and displayed in the Gradio UI.

Dependencies:
    pip install rembg pillow

Note: rembg downloads the U2Net model (~170MB) on first run.
      The model is cached at ~/.u2net/

Usage:
    from src.processing.photo import standardize_photo
    output_path = standardize_photo("raw_product.jpg", output_path="output/uuid/photo.png")
"""

from pathlib import Path


TARGET_SIZE = (800, 800)
BACKGROUND_COLOR = (255, 255, 255, 255)  # White, fully opaque


def standardize_photo(
    input_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """Remove background and standardize a product photo to 800x800 PNG.

    Pipeline:
        1. Load image with Pillow (convert to RGBA for transparency support)
        2. Run rembg background removal (U2Net model)
        3. Create 800x800 white canvas
        4. Resize subject (maintaining aspect ratio) with padding
        5. Composite subject onto white background
        6. Save as PNG

    Args:
        input_path: Path to input image (JPEG, PNG, WebP, etc.)
        output_path: Path for the output PNG. If None, saves to same directory
                     as input with '_standardized.png' suffix.

    Returns:
        Path to the standardized 800x800 PNG file.

    Raises:
        FileNotFoundError: If input_path does not exist.
        ImportError: If rembg or Pillow is not installed.

    Example:
        >>> from src.processing.photo import standardize_photo
        >>> out = standardize_photo("product.jpg", "output/uuid/photo.png")
        >>> print(out)  # Path('output/uuid/photo.png')
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    if output_path is None:
        output_path = input_path.parent / f"{input_path.stem}_standardized.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # TODO: implement background removal and standardization
    # try:
    #     from rembg import remove
    #     from PIL import Image, ImageOps
    # except ImportError as e:
    #     raise ImportError(f"Missing dependency: {e}. Run: pip install rembg pillow") from e
    #
    # # Step 1: Load image
    # img = Image.open(input_path).convert("RGBA")
    #
    # # Step 2: Remove background
    # img_no_bg = remove(img)  # Returns RGBA with transparent background
    #
    # # Step 3: Create white canvas
    # canvas = Image.new("RGBA", TARGET_SIZE, BACKGROUND_COLOR)
    #
    # # Step 4: Resize subject to fit within 800x800 (with padding)
    # subject_bbox = img_no_bg.getbbox()
    # if subject_bbox:
    #     cropped = img_no_bg.crop(subject_bbox)
    #     cropped.thumbnail((TARGET_SIZE[0] - 40, TARGET_SIZE[1] - 40), Image.LANCZOS)
    #     # Center on canvas
    #     x = (TARGET_SIZE[0] - cropped.width) // 2
    #     y = (TARGET_SIZE[1] - cropped.height) // 2
    #     canvas.paste(cropped, (x, y), cropped)
    #
    # # Step 5: Convert to RGB (remove alpha) and save
    # final = canvas.convert("RGB")
    # final.save(str(output_path), "PNG", optimize=True)
    #
    # return output_path
    raise NotImplementedError("standardize_photo() not yet implemented")


def get_image_dimensions(image_path: str | Path) -> tuple[int, int]:
    """Get image dimensions without loading the full file.

    Args:
        image_path: Path to the image file.

    Returns:
        Tuple of (width, height) in pixels.

    Raises:
        FileNotFoundError: If image does not exist.
    """
    # TODO: implement using Pillow
    # from PIL import Image
    # with Image.open(image_path) as img:
    #     return img.size
    raise NotImplementedError("get_image_dimensions() not yet implemented")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python photo.py <input_image>")
        sys.exit(1)

    input_file = sys.argv[1]
    print(f"Standardizing: {input_file}")
    # TODO: uncomment after implementation
    # out = standardize_photo(input_file)
    # print(f"Output: {out}")
    print("standardize_photo() not yet implemented")
