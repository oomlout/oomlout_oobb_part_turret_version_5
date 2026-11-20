"""Build self-contained assembly and print SCAD files from the materialized OOMP part."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import shutil
import subprocess

from turret_offset_review import get_frame_holes, get_frame_opening, get_offset_layout
from working_svg import get_disc_pattern


def render_oobb_module(**kwargs):
    import oobb
    import opsc

    name = kwargs.pop("module_name")
    mode = kwargs.get("mode", "true")
    kwargs.setdefault("mode", mode)
    kwargs.setdefault("type", "positive")
    if kwargs["shape"] == "oobb_bolt":
        # The v5 bolt wrapper delegates to the legacy OOBB hex-bolt primitive.
        # Its polygon carries both shaft depth and head height. OPSC extrudes by depth.
        from old.oobb_get_items_base_old import get_oobb_bolt
        components = []
        pending = list(get_oobb_bolt(**kwargs))
        while pending:
            item = pending.pop()
            if isinstance(item,list):
                pending.extend(item)
            else:
                if item["shape"] == "polyg":
                    item["depth"] = item["h"]
                components.append(item)
    else:
        components = oobb.oobb_easy(**kwargs)
    body = opsc.scad_render(opsc.opsc_get_object(components, mode=mode))
    return f"module {name}() {{\n{body}}}\n"


def get_oobb_modules(**kwargs):
    geometry = kwargs["geometry"]
    guide = geometry["guide"]
    recipes = [
        {
            "module_name": "rounded_plate_blank",
            "shape": "oobb_rounded_rectangle_rounded",
            "mode": "3dpr",
            "radius": 5,
            "radius_rounded": geometry["plate_edge_radius_mm"],
            "size": [
                geometry["width"]*geometry["pitch_mm"]-geometry["plate_edge_reduction_mm"],
                geometry["height"]*geometry["pitch_mm"]-geometry["plate_edge_reduction_mm"],
                geometry["depth"],
            ],
        },
        {
            "module_name": "lower_nut_profile",
            "shape": "oobb_nut",
            "radius_name": "m6",
            "mode": "3dpr",
            "zz": "bottom",
            "depth": 1,
        },
        {
            "module_name": "plate_blank",
            "shape": "oobb_plate",
            "mode": "3dpr",
            "width": geometry["width"],
            "height": geometry["height"],
            "depth": geometry["depth"],
            "holes": False,
        },
        {
            "module_name": "unit_bore",
            "shape": "oobb_hole",
            "radius": 1,
            "depth": 1,
        },
        {
            "module_name": "m6_bolt",
            "shape": "oobb_bolt",
            "radius_name": "m6",
            "depth": guide["clamp_bolt_length_mm"],
            "include_nut": False,
        },
        {
            "module_name": "face_axle_bolt",
            "shape": "oobb_bolt",
            "radius_name": "m6",
            "depth": geometry["housing"]["face_bolt"]["length_mm"],
            "include_nut": False,
        },
        {
            "module_name": "edge_nut_pocket",
            "shape": "oobb_nut",
            "radius_name": "m6",
            "mode": "3dpr",
            "zz": "bottom",
            "depth": guide["common_clamp"]["outer_x_mm"]-guide["common_clamp"]["nut_pocket_start_mm"]+0.02,
        },
        {
            "module_name": "m6_nut_blank",
            "shape": "oobb_nut",
            "radius_name": "m6",
            "zz": "bottom",
        },
        {
            "module_name": "interface_washer",
            "shape": "tube",
            "r": guide["washer_id_mm"] / 2,
            "wall_thickness": (guide["washer_od_mm"] - guide["washer_id_mm"]) / 2,
            "depth": guide["washer_thickness_mm"],
        },
        {
            "module_name": "roller",
            "shape": "tube",
            "r": guide["bore_mm"] / 2,
            "wall_thickness": (guide["od_mm"] - guide["bore_mm"]) / 2,
            "depth": guide["width_mm"],
        },
    ]
    return "\n".join(render_oobb_module(**recipe) for recipe in recipes)


def get_parameters(**kwargs):
    geometry = kwargs["geometry"]
    guide = geometry["guide"]
    clamp = guide["common_clamp"]
    housing = geometry["housing"]
    bolt = housing["face_bolt"]
    layout = get_offset_layout(pattern=get_disc_pattern(**geometry), **geometry)
    frame_holes = get_frame_holes(layout=layout, **geometry)
    opening = get_frame_opening(layout=layout, **geometry)
    face = housing["face_axle_radius_mm"]
    pocket_r = layout["pocket_half_width"]
    if not layout.get("circular_pocket"):
        raise ValueError("Production turrets require the cylindrical 606 pocket")
    if geometry["depth"] > guide["width_mm"] + 2 * guide["washer_thickness_mm"]:
        raise ValueError("Plate depth exceeds the edge bearing and washer stack")
    outline = []
    lower_outline = []
    lug_scale = clamp["lower_nut_lug_radius_mm"]/clamp["slot_lug_radius_mm"]
    boss = clamp["boss_x_mm"]
    inside = clamp["slot_x_mm"][0]-clamp["slot_lug_radius_mm"]
    reinforced_inside = clamp["slot_x_mm"][0]-clamp["lower_nut_lug_radius_mm"]
    for x, y in layout["stations"][0]["outline"]:
        x -= face
        outline.append([round(x, 6), round(y, 6)])
        # Reinforce the captive-nut end of the lower lug. The blended rail uses
        # the same vertex ordering as its mating footprint for a continuous loft.
        dy = y-clamp["edge_y_mm"]
        # Anchor the rail beyond the lobe so the face-roller washer still seats flat.
        reach = clamp["edge_y_mm"]-guide["od_mm"]/2-.5
        if x <= boss+.00001 and abs(dy)<reach:
            x = boss+(x-boss)*(boss-reinforced_inside)/(boss-inside)
            blend = min(abs(dy),reach-abs(dy))
            y += (1 if dy>=0 else -1)*blend*(lug_scale-1)
        lower_outline.append([round(x,6),round(y,6)])
    return {
        "frame_size": [2*layout["half_width"], 2*layout["half_height"]],
        "depth": geometry["depth"],
        "station_angles": layout["angles"],
        "frame_holes": frame_holes,
        "disc_holes": layout["holes"],
        "disc_radius": housing["disc_radius_mm"],
        "opening_radius": housing["opening_radius_mm"],
        "frame_opening": [[round(x,6),round(y,6)] for x,y in list(opening.exterior.coords)[:-1]],
        "mount_hole_d": geometry["m6_hole_diameter_mm"],
        "face_radius": face,
        "bearing_od": guide["od_mm"],
        "bearing_width": guide["width_mm"],
        "bearing_bore": guide["bore_mm"],
        "washer_od": guide["washer_od_mm"],
        "washer_depth": guide["washer_thickness_mm"],
        "face_relief": housing["face_relief_clearance_mm"],
        "face_bolt_length": bolt["length_mm"],
        "face_head_d": bolt["head_diameter_mm"],
        "face_head_height": bolt["head_height_mm"],
        "clamp_outline": outline,
        "lower_outline": lower_outline,
        "clamp_y_min": min(y for x,y in outline),
        "clamp_length": layout["housing_length_mm"],
        "housing_radius": clamp["outer_edge_radius_mm"],
        "plate_radius": geometry["plate_edge_radius_mm"],
        "lower_lug_radius": clamp["lower_nut_lug_radius_mm"],
        "joint_length": guide["clamp_bolt_length_mm"],
        "nut_height": guide["nut_thickness_mm"],
        "thread_beyond_nut": guide["thread_beyond_nut_mm"],
        "bolt_sweep_radius": layout["bolt_sweep"],
        "clamp_outer_x": clamp["outer_x_mm"],
        "boss_x": clamp["boss_x_mm"],
        "mount_x": clamp["mount_x_mm"],
        "mount_positions": clamp["mount_y_mm"],
        "washer_pocket_clearance": clamp["washer_pocket_clearance_mm"],
        "edge_y": clamp["edge_y_mm"],
        "edge_axle_x": round(layout["axle_x"]-face, 6),
        "slot_ends": clamp["slot_x_mm"],
        "slot_width": clamp["slot_width_mm"],
        "pocket_x": round(layout["pocket_end"]-pocket_r-face, 6),
        "pocket_radius": pocket_r,
        "horizontal_bore": clamp["horizontal_bolt_bore_mm"],
        "nut_start": clamp["nut_pocket_start_mm"],
    }


def export_mesh(**kwargs):
    executable = kwargs["executable"]
    staging = kwargs["staging"]
    name = kwargs["name"]
    command = [executable, "--backend=Manifold", "--export-format", "binstl",
               "-o", f"{name}.stl", f"{name}.scad"]
    process = subprocess.run(command, cwd=staging, capture_output=True, text=True)
    mesh = staging / f"{name}.stl"
    if process.returncode or "ERROR:" in process.stderr or not mesh.exists() or mesh.stat().st_size <= 84:
        raise RuntimeError(f"OpenSCAD export failed for {name}\n{process.stderr}")
    if name not in ("3dpr", "guide_fit_sample"):
        return
    # STL stores separate float32 triangles. Reconstruct the solid after that
    # quantization to discard zero-thickness seams at tangent fillets.
    import manifold3d
    import trimesh
    imported = trimesh.load_mesh(mesh)
    triangles = manifold3d.Mesh(imported.vertices.astype("float32"), imported.faces.astype("uint32"))
    triangles.merge()
    solid = manifold3d.Manifold(triangles)
    if solid.status() != manifold3d.Error.NoError:
        raise ValueError(f"{name} has an invalid mesh after STL export: {solid.status()}")
    result = solid.to_mesh()
    cleaned = trimesh.Trimesh(result.vert_properties[:,:3], result.tri_verts)
    if not cleaned.is_volume or abs(cleaned.volume-imported.volume) > .01:
        raise ValueError(f"{name} lost solid volume in STL export")
    cleaned.export(mesh)


def build_turret(**kwargs):
    generate_stl = kwargs.get("generate_stl", True)
    render_preview = kwargs.get("render_preview", generate_stl)
    part = kwargs["part"]
    root = Path(__file__).resolve().parent
    folder = root / "parts" / part["id"]
    parameters = get_parameters(geometry=part["oobb_details"])
    recipe = (root / "turret.scad").read_text(encoding="utf-8")
    native_modules = get_oobb_modules(geometry=part["oobb_details"])
    definitions = []
    for key, value in parameters.items():
        definitions.append(f"{key} = {json.dumps(value, allow_nan=False)};")
    header = "\n".join(definitions)
    executable = shutil.which("openscad.com") or shutil.which("openscad")
    if generate_stl and not executable:
        raise FileNotFoundError("OpenSCAD must be on PATH to export the turret STL")
    print(f"Building {part['id']}", flush=True)
    with TemporaryDirectory(dir=folder) as temporary:
        staging = Path(temporary)
        models = {
            "3dpr": "print_layout();",
            "true": "assembly();",
            "guide_fit_sample": "fit_sample();",
            "guide_clearance": "slide = 0; // [-1:0.05:1]\nclearance_review(slide);",
        }
        for name, entry in models.items():
            if name.startswith("guide_"):
                contents = f"use <true.scad>;\n$fn = 96;\n{entry}\n"
            else:
                contents = f"// {part['id']}\n{header}\n\n{native_modules}\n{recipe}\n\n{entry}\n"
            (staging / f"{name}.scad").write_text(contents, encoding="utf-8")
        if generate_stl:
            for name in ("3dpr", "guide_fit_sample"):
                export_mesh(executable=executable, staging=staging, name=name)
        if render_preview:
            command = [executable, "--preview", "--viewall", "--autocenter", "--projection=o",
                       "--camera=0,0,0,50,0,30,500", "--imgsize=1000,720",
                       "-o", "true.png", "true.scad"]
            subprocess.run(command, cwd=staging, capture_output=True, text=True, check=True)
        for output in sorted(staging.iterdir()):
            destination = folder / output.name
            try:
                output.replace(destination)
            except PermissionError:
                # Some Windows mesh viewers permit writing while holding a delete lock.
                payload = output.read_bytes()
                with destination.open("r+b") as target:
                    previous = target.read()
                    try:
                        target.seek(0)
                        target.write(payload)
                        target.truncate()
                    except OSError:
                        target.seek(0)
                        target.write(previous)
                        target.truncate()
                        raise
