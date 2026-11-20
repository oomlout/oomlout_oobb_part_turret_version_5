"""Run python render_turrets.py after python working.py to refresh the studio PNGs."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


def render_studio(**kwargs):
    import oobb
    from PIL import Image
    from turret_cad import export_mesh
    from working_oomp_populate import catalogue_records

    selected = kwargs.get("filter", "")
    samples = kwargs.get("samples", 32)
    resolution = kwargs.get("resolution", 1200)
    blender = kwargs.get("blender", shutil.which("blender"))
    openscad = kwargs.get("openscad", shutil.which("openscad.com") or shutil.which("openscad"))
    studio = Path(oobb.__file__).parent / "presentation" / "scripts" / "render_catalogue.py"
    groups = {
        "frame": "assembled_frame();",
        "rotor": "assembled_disc();",
        "guides": "assembled_clamps();",
        "bearings": "assembled_hardware(true,false);",
        "fasteners": "assembled_hardware(false,true);",
    }
    if not blender or not openscad or not studio.is_file():
        raise RuntimeError("Studio rendering needs Blender, OpenSCAD and the OOBB v5 presentation scripts")
    with TemporaryDirectory() as temporary:
        jobs = []
        for record in catalogue_records(filter=selected):
            folder = record.parent
            staging = Path(temporary) / folder.name
            staging.mkdir()
            for group, entry in groups.items():
                recipe = f"use <{(folder/'true.scad').as_posix()}>;\n$fn = 96;\n{entry}\n"
                (staging / f"{group}.scad").write_text(recipe, encoding="utf-8")
                export_mesh(executable=openscad, staging=staging, name=group)
            jobs.append({
                "directory": str(staging),
                "destination": str(folder / "studio.png"),
                "groups": list(groups),
                "studio": str(studio),
                "samples": samples,
                "resolution": resolution,
            })
        if not jobs:
            raise ValueError(f"No active turret matched {selected!r}")
        manifest = Path(temporary) / "jobs.json"
        manifest.write_text(json.dumps(jobs), encoding="utf-8")
        command = [blender, "--background", "--factory-startup", "--python-exit-code", "1",
                   "--python", str(Path(__file__).resolve()), "--", str(manifest)]
        subprocess.run(command, check=True)
        for job in jobs:
            with Image.open(Path(job["directory"]) / "assembly.png") as image:
                background = Image.new("RGB", image.size, "#F7F6F1")
                background.paste(image, mask=image.getchannel("A"))
                background.save(job["destination"])


def render_assembly(**kwargs):
    import bpy
    from mathutils import Vector
    import runpy

    directory = Path(kwargs["directory"])
    studio = runpy.run_path(kwargs["studio"])
    colours = {
        "frame": (0,177,183),
        "guides": (0,177,183),
        "rotor": (18,18,18),
        "bearings": (144,151,157),
        "fasteners": (196,199,201),
    }
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = kwargs["samples"]
    scene.cycles.use_denoising = True
    prefs = bpy.context.preferences.addons["cycles"].preferences
    if any(option[0] == "OPTIX" for option in prefs.get_device_types(bpy.context)):
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        for device in prefs.devices:
            device.use = device.type == "OPTIX"
        if any(d.use for d in prefs.devices):
            scene.cycles.device = "GPU"
    scene.render.resolution_x = kwargs["resolution"]
    scene.render.resolution_y = round(kwargs["resolution"]*.82)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "AgX"
    scene.world = bpy.data.worlds.new("OOBB studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.8,.8,.8,1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .45
    points = []
    for group in kwargs["groups"]:
        bpy.ops.wm.stl_import(filepath=str(directory / f"{group}.stl"))
        part = bpy.context.object
        part.scale = (.001,)*3
        bpy.context.view_layer.update()
        metal = group in ("fasteners","bearings")
        material = studio["material"](group, colours[group], .29 if metal else .4)
        material.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = float(metal)
        part.data.materials.append(material)
        points.extend(part.matrix_world @ v.co for v in part.data.vertices)
    span = max(p.x for p in points)-min(p.x for p in points)
    for name,position,energy,radius in (
        ("Key",(-2,-3,5),22,4), ("Fill",(3,-1,3),12,3), ("Rim",(0,4,4),18,3)
    ):
        data = bpy.data.lights.new(name,"AREA")
        data.energy = energy*.07*(span/.1)**2
        data.shape = "DISK"
        data.size = span*radius
        light = bpy.data.objects.new(name,data)
        scene.collection.objects.link(light)
        light.location = Vector(position)*span
        studio["aim"](light,(0,0,0))
    data = bpy.data.cameras.new("Three-quarter assembly")
    data.type = "ORTHO"
    data.clip_start = .0001
    camera = bpy.data.objects.new("Camera",data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = Vector((1.15,-1.45,1.65))*span
    studio["aim"](camera,(0,0,0))
    bpy.context.view_layer.update()
    inverse = camera.matrix_world.inverted()
    projected = [inverse @ p for p in points]
    width = max(p.x for p in projected)-min(p.x for p in projected)
    height = max(p.y for p in projected)-min(p.y for p in projected)
    data.ortho_scale = max(width,height/.82)*1.15
    scene.render.filepath = str(directory / "assembly.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    if "--" in sys.argv:
        manifest = Path(sys.argv[sys.argv.index("--")+1])
        for job in json.loads(manifest.read_text(encoding="utf-8")):
            render_assembly(**job)
    else:
        render_studio()
