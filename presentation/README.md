# Turret assembly publishing

Run commands from the project root. Blender and OpenSCAD must be on PATH. The Python build uses the OOBB v5 and OOMP environments, NumPy, trimesh, manifold3d, Shapely, Matplotlib, Pillow, ReportLab, svglib, PyMuPDF and PyYAML.

| Command | Output |
|---|---|
| `python working.py` | Rebuild the three part definitions, drawings, print files, studio views and assembly publications. |
| `python working.py --geometry-only` | Rebuild the CAD, STLs, fit samples and dimensional drawings. |
| `python working.py --assembly-only` | Render and publish the assembly books from the current part records and geometry. |
| `python working.py --filter 9_width` | Rebuild the 9 × 9 part and update its publications. |
| `python -m unittest discover -s tests` | Check the geometry, print meshes, bolt stack, nut seats and housing lands. |

Edit the station count, guide dimensions and assembly steps in [the populate recipe](../working_oomp_populate.py). The [publisher](../turret_assembly.py) places the production meshes, counts each physical item once, compares the individual printable volumes with the full STL, and generates the CSV, part READMEs, PDF and offline HTML viewer. The book, step cards, page previews, validation report and editable Blender scene live in each part’s `assembly/` folder.

The booklet and offline viewer follow the recent OOBB phone and tool holders. The step scenes use millimetre production coordinates, external-hex hardware, teal printed frames and black discs. The booklet uses landscape A4 pages in reader order. Use booklet imposition once when printing folded copies. [OOBB assembly guide](https://github.com/oomlout/oomlout_oobb_version_5/blob/main/ASSEMBLY_INSTRUCTIONS_GUIDE.md) · [Phone holder reference](https://github.com/oomlout/oomlout_oobb_part_holder_phone_version_5)

The inventory links the matching OOMP bolt, nut and bearing records. The washer is specified by its 6 mm bore, 14 mm outside diameter and 1.5 mm thickness. The project stores the original Oomlout vector logo alongside the booklet generator. [Oomlout logo source](https://github.com/oomlout/oomlout_media/blob/main/logos/logo_vector_unshaded/oomlout-LOGO-unshaded-vector.svg)
