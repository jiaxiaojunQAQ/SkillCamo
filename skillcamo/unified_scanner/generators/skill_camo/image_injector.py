# Copyright 2026
#
# Image injector for command injection.

"""
Image Injector - generates command images and injects them into skills.
Supports both simple command images and SkillCamo_cloze-style keyword images.
"""

from __future__ import annotations

import importlib
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Terminal-style color scheme (matching SkillCamo_cloze)
DEFAULT_BG_COLOR = (30, 30, 30)
DEFAULT_TEXT_COLOR = (0, 255, 100)
DEFAULT_NUMBER_COLOR = (255, 200, 50)

# Default rendering parameters
DEFAULT_FONT_SIZE = 22
DEFAULT_MAX_WIDTH = 800
DEFAULT_PADDING = 20
DEFAULT_LINE_SPACING = 10

# Supersampling: 渲染时所有像素参数（字号、padding、宽度等）乘以此倍数。
# 输出大图（不缩回原尺寸），文字像素更密、抗锯齿质量显著提升。
DEFAULT_RENDER_SCALE = 2


def _load_font(font_size: int = DEFAULT_FONT_SIZE):
    """加载等宽字体，失败则使用默认字体。"""
    from PIL import ImageFont
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            font_size,
        )
    except (OSError, IOError):
        return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    """将长文本按像素宽度自动换行。"""
    if not text:
        return [""]
    lines: list[str] = []
    # 先按换行符分割
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            test = current + char
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_width and current:
                lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)
    return lines or [""]


class KeywordImageRenderer:
    """Renders keywords into terminal-style images (SkillCamo_cloze style)

    Generates images with:
    - Dark background (30, 30, 30)
    - Green terminal text (0, 255, 100)
    - Yellow numbered labels (255, 200, 50)
    """

    def __init__(
        self,
        bg_color: Tuple[int, int, int] = DEFAULT_BG_COLOR,
        text_color: Tuple[int, int, int] = DEFAULT_TEXT_COLOR,
        number_color: Tuple[int, int, int] = DEFAULT_NUMBER_COLOR,
    ):
        self.bg_color = bg_color
        self.text_color = text_color
        self.number_color = number_color

    def render_keyword_image(
        self,
        keyword: str,
        index: int,
        output_path: Path,
    ) -> Path:
        """Render a single keyword with its index number

        Args:
            keyword: The keyword text to render
            index: The keyword index number (1, 2, 3...)
            output_path: Where to save the PNG

        Returns:
            Path to the generated image
        """
        try:
            from PIL import Image, ImageDraw

            scale = DEFAULT_RENDER_SCALE
            font_size = 24 * scale
            padding = DEFAULT_PADDING * scale
            line_spacing = DEFAULT_LINE_SPACING * scale
            font = _load_font(font_size)

            # Measure text
            index_text = f"[{index}] "
            full_text = index_text + keyword
            img_temp = Image.new('RGB', (1, 1))
            draw_temp = ImageDraw.Draw(img_temp)
            text_bbox = draw_temp.textbbox((0, 0), full_text, font=font)

            width = max(300 * scale, text_bbox[2] - text_bbox[0] + padding * 2)
            height = font_size + padding * 2 + line_spacing

            image = Image.new('RGB', (width, height), self.bg_color)
            draw = ImageDraw.Draw(image)

            # Draw index number in yellow
            draw.text((padding, padding), index_text, fill=self.number_color, font=font)

            # Measure index width to position keyword
            idx_bbox = draw.textbbox((0, 0), index_text, font=font)
            kw_x = padding + (idx_bbox[2] - idx_bbox[0])
            draw.text((kw_x, padding), keyword, fill=self.text_color, font=font)

            image.save(output_path, 'PNG')
            logger.info(f"Rendered keyword image ({width}x{height}): {output_path}")
            return output_path

        except ImportError as exc:
            raise RuntimeError(
                "Pillow is not installed. Cannot generate keyword images."
            ) from exc

    def render_keyword_grid(
        self,
        keywords: List[str],
        output_dir: Path,
        base_name: str = "keyword",
    ) -> List[Path]:
        """Render multiple keywords as individual images

        Args:
            keywords: List of keyword strings
            output_dir: Directory to save images
            base_name: Base filename without extension

        Returns:
            List of paths to generated images
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        for i, keyword in enumerate(keywords, start=1):
            output_path = output_dir / f"{base_name}_{i}.png"
            self.render_keyword_image(keyword, i, output_path)
            paths.append(output_path)

        return paths

    def render_combined_keywords_image(
        self,
        image_keyword_map: Dict[int, str],
        output_path: Path,
    ) -> Path:
        """Render all keywords in a single combined image

        Args:
            image_keyword_map: Dict mapping index to keyword {1: "curl", 2: ".env"}
            output_path: Where to save the combined PNG

        Returns:
            Path to the generated image
        """
        try:
            from PIL import Image, ImageDraw

            scale = DEFAULT_RENDER_SCALE
            font_size = 22 * scale
            padding = DEFAULT_PADDING * scale
            line_spacing = DEFAULT_LINE_SPACING * scale
            font = _load_font(font_size)
            line_height = font_size + line_spacing

            # Measure all lines to determine width
            img_temp = Image.new('RGB', (1, 1))
            draw_temp = ImageDraw.Draw(img_temp)
            max_line_width = 0
            for i, keyword in sorted(image_keyword_map.items()):
                line_text = f"[{i}] {keyword}"
                bbox = draw_temp.textbbox((0, 0), line_text, font=font)
                max_line_width = max(max_line_width, bbox[2] - bbox[0])

            width = max(max_line_width + padding * 2, 400 * scale)
            height = len(image_keyword_map) * line_height + padding * 2

            image = Image.new('RGB', (width, height), self.bg_color)
            draw = ImageDraw.Draw(image)

            y = padding
            for i, keyword in sorted(image_keyword_map.items()):
                # Draw index number in yellow
                index_text = f"[{i}]"
                draw.text((padding, y), index_text, fill=self.number_color, font=font)

                # Measure index width to position keyword
                idx_bbox = draw.textbbox((0, 0), index_text + " ", font=font)
                kw_x = padding + (idx_bbox[2] - idx_bbox[0])

                # Draw keyword in green
                draw.text((kw_x, y), keyword, fill=self.text_color, font=font)

                y += line_height

            image.save(output_path, 'PNG')
            logger.info(f"Rendered combined keywords image ({width}x{height}): {output_path}")
            return output_path

        except ImportError as exc:
            raise RuntimeError(
                "Pillow is not installed. Cannot generate keyword images."
            ) from exc


def _apply_degradation(image_path: Path, degradation: dict) -> None:
    """可选后处理:降低图片 OCR 可读性(高斯噪点 + JPEG 往返),行为零副作用当 degradation 为空时。

    Args:
        image_path: 要就地修改的 PNG 路径
        degradation: 包含可选键 gaussian_noise_sigma(float) 和 jpeg_quality(int 1-95) 的字典
    """
    sigma = degradation.get("gaussian_noise_sigma", 0)
    quality = degradation.get("jpeg_quality", 0)
    if not sigma and not quality:
        return
    try:
        import io
        import numpy as np
        from PIL import Image
        img = Image.open(image_path)
        if sigma:
            arr = np.array(img, dtype=np.float32)
            arr += np.random.normal(0, sigma, arr.shape)
            arr = np.clip(arr, 0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
        if quality:
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=quality)
            buf.seek(0)
            img = Image.open(buf).copy()
        img.save(image_path, "PNG")
    except ImportError:
        logger.warning("numpy not available; skipping degradation")
    except Exception as e:
        logger.warning(f"degradation failed ({e}); keeping original image")


class ImageInjector:
    """Injects command images into skill files"""

    def __init__(
        self,
        base_skill_path: Path,
        config: Any,
        keyword_renderer: Optional[KeywordImageRenderer] = None,
        degradation: Optional[Dict] = None,
    ):
        """
        初始化注入器

        Args:
            base_skill_path: 基础技能路径
            config: 配置对象 (InjectionConfig)，需实现 get_iteration_dir() 方法
            keyword_renderer: Optional renderer for keyword images
        """
        self.base_skill_path = Path(base_skill_path)
        self.config = config
        self.skill_md = self.base_skill_path / "SKILL.md"
        self.keyword_renderer = keyword_renderer or KeywordImageRenderer()
        self.degradation: Dict = degradation or {}

    def inject_with_injection(
        self,
        command_text: str,
        iteration: int,
        rewritten_skill_md: str,
    ) -> Path:
        """
        Generate skill with injected command image (legacy interface)

        Args:
            command_text: The command to render into the image
            iteration: Current iteration number
            rewritten_skill_md: Full rewritten SKILL.md content

        Returns:
            Path to the generated skill directory
        """
        # Create output directory using config's unified method
        iter_dir = self.config.get_iteration_dir(iteration)
        skill_output = iter_dir / "skill"
        skill_output.mkdir(parents=True, exist_ok=True)

        # Copy base skill
        if skill_output.exists():
            shutil.rmtree(skill_output)
        shutil.copytree(self.base_skill_path, skill_output)

        # Generate command image
        image_path = self._generate_command_image(
            command_text,
            skill_output,
        )

        self._write_rewritten_skill_md(skill_output / "SKILL.md", rewritten_skill_md)

        return skill_output

    def inject_with_cloze(
        self,
        cloze_result: Any,
        iteration: int,
        rewritten_skill_md: str,
        image_filename: str = "keywords.png",
    ) -> Path:
        """Generate skill with cloze-style injected keyword image

        Args:
            cloze_result: ClozeResult with masked command and keywords
            iteration: Current iteration number
            rewritten_skill_md: Full rewritten SKILL.md content
            image_filename: Filename for the keyword image

        Returns:
            Path to the generated skill directory
        """
        # Create output directory using config's unified method
        iter_dir = self.config.get_iteration_dir(iteration)
        skill_output = iter_dir / "skill"
        skill_output.mkdir(parents=True, exist_ok=True)

        # Copy base skill
        if skill_output.exists():
            shutil.rmtree(skill_output)
        shutil.copytree(self.base_skill_path, skill_output)

        # Generate keyword image using the renderer
        resources_dir = skill_output / "resources"
        resources_dir.mkdir(exist_ok=True)

        keyword_image_path = resources_dir / image_filename
        self.keyword_renderer.render_combined_keywords_image(
            cloze_result.image_keyword_map,
            keyword_image_path,
        )

        self._write_rewritten_skill_md(skill_output / "SKILL.md", rewritten_skill_md)

        return skill_output

    def inject_with_split(
        self,
        split_result: Any,
        iteration: int,
        rewritten_skill_md: str,
        image_filename: str = "split.png",
    ) -> Path:
        """Generate skill with split-style injected command image

        Args:
            split_result: SplitResult with markdown_command and image_content
            iteration: Current iteration number
            rewritten_skill_md: Full rewritten SKILL.md content
            image_filename: Filename for the split command image

        Returns:
            Path to the generated skill directory
        """
        # Import here to avoid circular dependency
        from .models import SplitResult

        # Create output directory using config's unified method
        iter_dir = self.config.get_iteration_dir(iteration)
        skill_output = iter_dir / "skill"
        skill_output.mkdir(parents=True, exist_ok=True)

        # Copy base skill
        if skill_output.exists():
            shutil.rmtree(skill_output)
        shutil.copytree(self.base_skill_path, skill_output)

        # Generate split command image
        resources_dir = skill_output / "resources"
        resources_dir.mkdir(exist_ok=True)

        image_path = resources_dir / image_filename
        self._generate_split_content_image(
            split_result.image_content,
            image_path,
        )

        self._write_rewritten_skill_md(skill_output / "SKILL.md", rewritten_skill_md)

        return skill_output

    def inject_with_replace(
        self,
        command_text: str,
        iteration: int,
        rewritten_skill_md: str,
        target_image_relpath: str,
    ) -> Path:
        """SkillCamo-Replace: overwrite an EXISTING referenced image in place.

        Renders the command to a PNG via the standard renderer, then wraps that
        PNG as a base64-embedded ``<image>`` inside a minimal SVG written to the
        existing ``target_image_relpath`` (overwriting the benign asset). No new
        file is added; the SKILL.md keeps its original image anchor. The command
        text is hidden from text scanners (base64) but visible to a multimodal
        agent that renders the SVG.
        """
        iter_dir = self.config.get_iteration_dir(iteration)
        skill_output = iter_dir / "skill"
        skill_output.mkdir(parents=True, exist_ok=True)
        if skill_output.exists():
            shutil.rmtree(skill_output)
        shutil.copytree(self.base_skill_path, skill_output)

        # Render command PNG to a temp path, then embed into the target SVG
        tmp_png = skill_output / "resources" / ".replace_cmd.png"
        tmp_png.parent.mkdir(parents=True, exist_ok=True)
        self._generate_command_image_to_path(command_text, tmp_png)

        target_svg = (skill_output / target_image_relpath).resolve()
        if not target_svg.exists():
            logger.warning(f"inject_with_replace: target image missing, creating: {target_svg}")
        target_svg.parent.mkdir(parents=True, exist_ok=True)
        self._png_to_svg_with_embed(tmp_png, target_svg)
        tmp_png.unlink(missing_ok=True)

        self._write_rewritten_skill_md(skill_output / "SKILL.md", rewritten_skill_md)
        return skill_output

    @staticmethod
    def _png_to_svg_with_embed(png_path: Path, svg_out_path: Path) -> None:
        """Wrap a PNG as a base64-embedded <image> inside a minimal SVG."""
        import base64
        from PIL import Image

        with Image.open(png_path) as im:
            w, h = im.size
        b64 = base64.b64encode(Path(png_path).read_bytes()).decode("ascii")
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<image xlink:href="data:image/png;base64,{b64}" '
            f'width="{w}" height="{h}"/></svg>'
        )
        Path(svg_out_path).write_text(svg, encoding="utf-8")

    def inject_with_drop(
        self,
        command: str,
        iteration: int,
        image_filename: str = "command.png",
    ) -> Path:
        """Generate skill with full command image injection (no LLM rewriting)

        Like bash_script_drop: copies base skill and drops a rendered command
        image into resources/ WITHOUT modifying SKILL.md.

        Args:
            command: The full command to render as image
            iteration: Current iteration number
            image_filename: Filename for the command image

        Returns:
            Path to the generated skill directory
        """
        # Create output directory using config's unified method
        iter_dir = self.config.get_iteration_dir(iteration)
        skill_output = iter_dir / "skill"
        skill_output.mkdir(parents=True, exist_ok=True)

        # Copy base skill (preserving original SKILL.md)
        if skill_output.exists():
            shutil.rmtree(skill_output)
        shutil.copytree(self.base_skill_path, skill_output)

        # Generate command image
        resources_dir = skill_output / "resources"
        resources_dir.mkdir(exist_ok=True)

        image_path = resources_dir / image_filename
        self._generate_command_image_to_path(command, image_path)
        logger.info(f"Dropped command image: {image_path}")

        return skill_output

    def _generate_split_content_image(self, content: str, output_path: Path) -> Path:
        """Generate terminal-style image with split command content

        Uses auto-wrapping and adaptive sizing with the keyword renderer's color scheme.
        """
        try:
            from PIL import Image, ImageDraw

            scale = DEFAULT_RENDER_SCALE
            font_size = DEFAULT_FONT_SIZE * scale
            padding = DEFAULT_PADDING * scale
            line_spacing = DEFAULT_LINE_SPACING * scale
            max_width = DEFAULT_MAX_WIDTH * scale
            font = _load_font(font_size)
            max_text_width = max_width - padding * 2

            # Auto-wrap text
            img_temp = Image.new('RGB', (1, 1))
            draw_temp = ImageDraw.Draw(img_temp)
            lines = _wrap_text(draw_temp, content, font, max_text_width)

            # Calculate dimensions from wrapped lines
            line_height = font_size + line_spacing
            max_line_width = 0
            for line in lines:
                bbox = draw_temp.textbbox((0, 0), line, font=font)
                max_line_width = max(max_line_width, bbox[2] - bbox[0])

            width = max(max_line_width + padding * 2, 500 * scale)
            height = line_height * len(lines) + padding * 2

            image = Image.new('RGB', (width, height), self.keyword_renderer.bg_color)
            draw = ImageDraw.Draw(image)

            y = padding
            for line in lines:
                draw.text((padding, y), line, fill=self.keyword_renderer.text_color, font=font)
                y += line_height

            image.save(output_path, 'PNG')
            logger.info(f"Generated split content image ({width}x{height}, {len(lines)} lines): {output_path}")
            return output_path

        except ImportError as exc:
            raise RuntimeError(
                "Pillow is not installed. Cannot generate split content image."
            ) from exc

    def _generate_command_image(self, command: str, skill_dir: Path) -> Path:
        """Generate PNG image with command text"""
        resources_dir = skill_dir / "resources"
        resources_dir.mkdir(exist_ok=True)

        image_path = resources_dir / "command.png"
        self._generate_fallback_image(command, image_path)
        return image_path

    def _generate_command_image_to_path(self, command: str, output_path: Path) -> Path:
        """Generate PNG image with command text to specified output path

        Uses terminal-style rendering with auto-wrapping and adaptive sizing.

        Args:
            command: The command text to render
            output_path: Full path for the output image

        Returns:
            Path to the generated image
        """
        try:
            from PIL import Image, ImageDraw

            scale = DEFAULT_RENDER_SCALE
            font_size = DEFAULT_FONT_SIZE * scale
            padding = DEFAULT_PADDING * scale
            line_spacing = DEFAULT_LINE_SPACING * scale
            max_width = DEFAULT_MAX_WIDTH * scale
            font = _load_font(font_size)
            max_text_width = max_width - padding * 2

            # Auto-wrap text
            img_temp = Image.new('RGB', (1, 1))
            draw_temp = ImageDraw.Draw(img_temp)
            lines = _wrap_text(draw_temp, command, font, max_text_width)

            # Calculate dimensions from wrapped lines
            line_height = font_size + line_spacing
            max_line_width = 0
            for line in lines:
                bbox = draw_temp.textbbox((0, 0), line, font=font)
                max_line_width = max(max_line_width, bbox[2] - bbox[0])

            width = max(max_line_width + padding * 2, 500 * scale)
            height = line_height * len(lines) + padding * 2

            image = Image.new('RGB', (width, height), self.keyword_renderer.bg_color)
            draw = ImageDraw.Draw(image)

            y = padding
            for line in lines:
                draw.text((padding, y), line, fill=self.keyword_renderer.text_color, font=font)
                y += line_height

            image.save(output_path, 'PNG')
            if self.degradation:
                _apply_degradation(output_path, self.degradation)
            logger.info(f"Generated command image ({width}x{height}, {len(lines)} lines): {output_path}")
            return output_path

        except ImportError as exc:
            raise RuntimeError(
                "Pillow is not installed. Cannot generate command image."
            ) from exc

    def _generate_fallback_image(self, command: str, output_path: Path) -> None:
        """Generate image using PIL with auto-wrapping and adaptive sizing."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            scale = DEFAULT_RENDER_SCALE
            font_size = 36 * scale
            padding = DEFAULT_PADDING * scale
            line_spacing = DEFAULT_LINE_SPACING * scale
            max_width = DEFAULT_MAX_WIDTH * scale
            font = _load_font(font_size)
            max_text_width = max_width - padding * 2

            # Auto-wrap text
            img_temp = Image.new('RGB', (1, 1))
            draw_temp = ImageDraw.Draw(img_temp)
            lines = _wrap_text(draw_temp, command, font, max_text_width)

            # Calculate dimensions from wrapped lines
            heights = []
            max_line_width = 0
            for line in lines:
                bbox = draw_temp.textbbox((0, 0), line, font=font)
                line_w = bbox[2] - bbox[0]
                max_line_width = max(max_line_width, line_w)
                heights.append(bbox[3] - bbox[1])

            width = max(max_line_width + padding * 2, 500 * scale)
            height = sum(heights) + (len(lines) - 1) * line_spacing + padding * 2

            image = Image.new('RGB', (width, height), (0, 0, 0))
            draw = ImageDraw.Draw(image)

            y = padding
            for i, line in enumerate(lines):
                draw.text((padding, y), line, fill=(255, 255, 255), font=font)
                y += heights[i] + line_spacing

            image.save(output_path, 'PNG')
            if self.degradation:
                _apply_degradation(output_path, self.degradation)
            logger.info(f"Generated fallback image ({width}x{height}, {len(lines)} lines): {output_path}")

        except ImportError as exc:
            raise RuntimeError(
                "Failed to generate command image: Pillow is not installed and placeholder output is disabled"
            ) from exc

    def _write_rewritten_skill_md(self, skill_md_path: Path, rewritten_skill_md: str) -> None:
        """Write the full rewritten SKILL.md produced by the LLM."""
        skill_md_path.write_text(rewritten_skill_md.rstrip() + "\n", encoding="utf-8")
        logger.info(f"Wrote rewritten SKILL.md: {skill_md_path}")


def create_image_injector(
    base_skill_path: Path,
    config: Any,
    bg_color: Tuple[int, int, int] = DEFAULT_BG_COLOR,
    text_color: Tuple[int, int, int] = DEFAULT_TEXT_COLOR,
    number_color: Tuple[int, int, int] = DEFAULT_NUMBER_COLOR,
) -> ImageInjector:
    """Create ImageInjector with terminal-style keyword renderer

    Args:
        base_skill_path: Base skill directory
        config: Configuration object
        bg_color: Background color tuple
        text_color: Text color tuple
        number_color: Number/index color tuple

    Returns:
        Configured ImageInjector with KeywordImageRenderer
    """
    renderer = KeywordImageRenderer(
        bg_color=bg_color,
        text_color=text_color,
        number_color=number_color,
    )
    return ImageInjector(
        base_skill_path=base_skill_path,
        config=config,
        keyword_renderer=renderer,
    )
