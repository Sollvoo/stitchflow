"""
Script autonome appelé via subprocess pour isoler les crashes natifs de vtracer (SIGSEGV).
Usage : python _vtracer_helper.py <png_path> <svg_output_path> <n_colors> [fine_details]
fine_details : "1" pour activer les paramètres précision max (texte fin, détails nets).
"""
import sys


def main() -> None:
    if len(sys.argv) < 4 or len(sys.argv) > 5:
        print("Usage: _vtracer_helper.py <png_path> <svg_output_path> <n_colors> [fine_details]", file=sys.stderr)
        sys.exit(2)

    png_path, svg_output_path, n_colors_str = sys.argv[1], sys.argv[2], sys.argv[3]
    n_colors = int(n_colors_str)
    fine_details = len(sys.argv) == 5 and sys.argv[4] == "1"

    import vtracer

    if fine_details:
        filter_speckle = 1
        color_precision = 8
        path_precision = 6
        corner_threshold = 80
    else:
        filter_speckle = 2 if n_colors > 3 else 4
        color_precision = min(n_colors, 8)
        path_precision = 8
        corner_threshold = 60

    vtracer.convert_image_to_svg_py(
        png_path,
        svg_output_path,
        colormode='color',
        # cutout : formes disjointes (trous découpés) — l'ordre de broderie ne peut
        # plus recouvrir le design, contrairement à stacked (fond brodé par-dessus)
        hierarchical='cutout',
        filter_speckle=filter_speckle,
        color_precision=color_precision,
        layer_difference=16,
        corner_threshold=corner_threshold,
        length_threshold=4.0,
        max_iterations=10,
        splice_threshold=45,
        path_precision=path_precision,
    )


if __name__ == '__main__':
    main()
