"""
Script autonome appelé via subprocess pour isoler les crashes natifs de vtracer (SIGSEGV).
Usage : python _vtracer_helper.py <png_path> <svg_output_path> <n_colors>
"""
import sys


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: _vtracer_helper.py <png_path> <svg_output_path> <n_colors>", file=sys.stderr)
        sys.exit(2)

    png_path, svg_output_path, n_colors_str = sys.argv[1], sys.argv[2], sys.argv[3]
    n_colors = int(n_colors_str)

    import vtracer

    svg_content = vtracer.convert_image_to_svg_py(
        png_path,
        colormode='color',
        hierarchical='stacked',
        filter_speckle=4,
        color_precision=min(n_colors, 8),
        layer_difference=16,
        corner_threshold=60,
        length_threshold=4.0,
        max_iterations=10,
        splice_threshold=45,
        path_precision=8,
    )

    with open(svg_output_path, 'w', encoding='utf-8') as f:
        f.write(svg_content)


if __name__ == '__main__':
    main()
