"""Blender worker. Meshes and poses come from the production CAD in millimetres."""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def aim(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def render(**kwargs):
    output = Path(kwargs["output"])
    items = kwargs["items"]
    views = kwargs["views"]
    default_eye = kwargs.get("eye", [0.38, -0.9, 0.95])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    preferences = bpy.context.preferences.addons["cycles"].preferences
    try:
        preferences.compute_device_type = "OPTIX"
        preferences.get_devices()
        for device in preferences.devices:
            device.use = device.type == "OPTIX"
        if any(device.use for device in preferences.devices):
            scene.cycles.device = "GPU"
    except (RuntimeError, TypeError):
        pass
    scene.render.resolution_x = 880
    scene.render.resolution_y = 620
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    scene.world = bpy.data.worlds.new("Soft studio")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.8,.8,.8,1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .45
    span = kwargs["frame_width_mm"]/1000
    for name, xyz, power, radius in [
        ("Key", [-2,-3,5], 22, 4),
        ("Fill", [3,-1,3], 12, 3),
        ("Rim", [0,4,4], 18, 3),
        ("Underside", [1,-2,-4], 10, 3),
    ]:
        light = bpy.data.lights.new(name, "AREA")
        light.energy = power*.07*(span/.1)**2
        light.size = span*radius
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.location = Vector(xyz)*span
        aim(obj, [0, 0, 0])

    camera = bpy.data.objects.new("Orthographic camera", bpy.data.cameras.new("Lens"))
    scene.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.clip_start = 0.0001
    scene.camera = camera
    objects = []
    prototypes = {}
    for item in items:
        key = item["key"]
        if key in prototypes:
            obj = prototypes[key].copy()
            scene.collection.objects.link(obj)
        else:
            bpy.ops.wm.stl_import(filepath=item["source"])
            obj = bpy.context.object
            prototypes[key] = obj
            material = bpy.data.materials.new(key)
            material.use_nodes = True
            shader = material.node_tree.nodes["Principled BSDF"]
            shader.inputs["Base Color"].default_value = [*item["color"], 1]
            shader.inputs["Metallic"].default_value = item.get("metallic", 0)
            shader.inputs["Roughness"].default_value = 0.36
            obj.data.materials.append(material)
        obj.name = f"{key} {item['station']}"
        objects.append(obj)

    for view in views:
        points = []
        seen = set()
        for item, obj in zip(items, objects):
            key = item["key"]
            visible = key in view["show"]
            visible = visible and item["step"] <= view.get("through", 99)
            if "station" in view:
                visible = visible and item["station"] == view["station"]
            if view.get("single") and key in seen:
                visible = False
            obj.hide_render = not visible
            if visible:
                seen.add(key)
                matrix = Matrix(item["pose"])
                matrix.translation = (matrix.translation + Vector(item["explode"])*view.get("spread",0)) / 1000
                obj.matrix_world = matrix @ Matrix.Scale(.001,4)
                bpy.context.view_layer.update()
                if key == "frame" and abs(obj.dimensions.x*1000-kwargs["frame_width_mm"]) > .01:
                    raise ValueError("Studio frame scale differs from the production frame")
                points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
        centre = Vector([(max(p[i] for p in points) + min(p[i] for p in points)) / 2 for i in range(3)])
        eye = Vector(view.get("eye", default_eye)).normalized()
        camera.location = centre + eye * 0.6
        aim(camera, centre)
        bpy.context.view_layer.update()
        projected = [camera.matrix_world.inverted() @ p for p in points]
        left, right = min(p.x for p in projected), max(p.x for p in projected)
        bottom, top = min(p.y for p in projected), max(p.y for p in projected)
        camera.location += camera.rotation_euler.to_matrix() @ Vector([(left + right) / 2, (bottom + top) / 2, 0])
        aspect = scene.render.resolution_x / scene.render.resolution_y
        camera.data.ortho_scale = max(right - left, aspect * (top - bottom)) * 1.06
        scene.render.filepath = str(output / (view["name"] + ".png"))
        bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output.parent / "assembly.blend"),compress=True)


if __name__ == "__main__":
    job = Path(sys.argv[sys.argv.index("--") + 1])
    render(**json.loads(job.read_text(encoding="utf-8")))
