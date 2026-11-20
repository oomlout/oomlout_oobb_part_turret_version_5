# OOBB turret project

- Define each turret in `working_oomp_populate.py`, materialize its OOMP record with `working_oomp.py`, then build its review drawings with `working_svg.py`. Run all three in sequence with `python working.py`.
- Use verbose multiline dictionaries. Pass editable options through named routines with `**kwargs`. Put defaults at the top of the routine that owns them.
- Keep the taxonomy in the order `oobb, part, turret, width, height, depth, turret_diameter, bearing, number_of_guides`. Width, height and usable turret diameter are in OOBB units. Depth is in millimetres and is shared by the plate and disc.
- Define the guide and frame cutout once per bearing type. Set each turret's guide positions by side. Include one upper and one lower clamp per guide in every future plate 3dpr layout.
- Use an M6 washer with 14 mm outside diameter and 1.5 mm thickness at every printed-part-to-bearing interface.
- The current build produces concept sheets for discussion. Review the bearing arrangement and clearances with the user before starting printable geometry.
