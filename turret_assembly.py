"""Generate the per-size OOBB assembly books, viewer, inventory and catalogue."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

import numpy as np
import yaml
from PIL import Image
from trimesh.transformations import rotation_matrix, translation_matrix

from presentation import assembly_booklet, assembly_viewer
from turret_cad import export_mesh, get_parameters
from working_oomp_populate import catalogue_records


ROOT = Path(__file__).resolve().parent
PROJECT_URL = "https://github.com/oomlout/oomlout_oobb_part_turret_version_5"


def define_inventory(**kwargs):
    count = kwargs["guide_count"]
    joint = kwargs["joint_length"]
    face = kwargs["face_length"]
    # Verified local OOMP records. The Ø14 washer is a project-specified dimension.
    definitions = [
        ("frame","Plate",1,"assembled_frame();",None),
        ("rotor","Disc",1,"assembled_disc();",None),
        ("upper","Upper housing",count,"clamp_half();",None),
        ("lower","Lower housing",count,"clamp_half(lower=true);",None),
        ("bearing","606 bearing",3*count,"roller();","hardware_bearing_600_series_606_size_6_mm_id_17_mm_od_6_mm_depth"),
        ("washer","M6 washer Ø14",4*count,"interface_washer();",None),
        ("face_bolt",f"M6 × {face:g} hex bolt",2*count,"face_axle_bolt();",f"hardware_set_screw_m6_{face:g}_mm_length"),
        ("joint_bolt",f"M6 × {joint:g} hex bolt",3*count,"m6_bolt();",f"hardware_set_screw_m6_{joint:g}_mm_length"),
        ("nut","M6 nut",5*count,"m6_nut();","hardware_nut_m6"),
    ]
    parts = {}
    for key, name, quantity, entry, identity in definitions:
        part = {
            "key": key,
            "name": name,
            "quantity": quantity,
            "entry": entry,
            "id": identity or (kwargs["part_id"]+"/"+key if key!="washer" else "M6 ID6 OD14 thickness1.5 mm"),
        }
        if identity:
            from oomp import hex_to_base36
            digest = hashlib.md5(identity.encode()).hexdigest()
            code = hex_to_base36(digest[:6])
            repo = "oomp_bearing_version_5" if key=="bearing" else "oomp_hardware_bolt_version_5"
            part.update({
                "md5_6_alpha": code,
                "short_url": "https://oom.lt/a/"+code,
                "short_label": "oom.lt/a/"+code,
                "identity_source": f"https://github.com/oomlout/{repo}/tree/main/parts/{identity}",
            })
        parts[key] = part
    return parts


def assembly_instances(**kwargs):
    p = kwargs["parameters"]
    stage = kwargs["stage"]
    items = []
    def move(x=0,y=0,z=0):
        return translation_matrix([x,y,z])
    def turn(angle,axis):
        return rotation_matrix(np.radians(angle),axis)
    def place(key, step, pose, explode, station):
        colours = {
            "teal": [0,.440,.474],
            "black": [.006,.006,.006],
            "steel": [.52,.56,.60],
        }
        metal = key in ("washer","bearing","nut","face_bolt","joint_bolt")
        items.append({
            "key": key,
            "step": step,
            "station": station,
            "source": str(stage / (key+".stl")),
            "color": colours["steel" if metal else "black" if key=="rotor" else "teal"],
            "metallic": .86 if metal else 0,
            "pose": pose.tolist(),
            "explode": [float(value) for value in explode],
        })
    place("frame",5,move(),[0,0,0],-1)
    place("rotor",5,move(),[0,0,0],-1)
    half = p["bearing_width"]/2
    br = p["bearing_od"]/2
    hd = p["depth"]/2
    boss = br + p["washer_od"]/2 + 2
    surface = hd + boss
    # Vertical nut's outside face is one thread pitch above the bolt tip.
    nut_z = surface-p["joint_length"]+p["thread_beyond_nut"]
    for station,angle in enumerate(p["station_angles"]):
        orientation = turn(angle,[0,0,1])
        origin = orientation @ move(x=p["face_radius"])
        radial = orientation[:3,:3] @ np.array([1,0,0])
        for sign,key in ((1,"upper"),(-1,"lower")):
            half_pose = origin @ np.diag([1,1,sign,1])
            lift = np.array([0,0,sign*24])
            place(key,1,half_pose @ move(z=hd),lift,station)
            axle = half_pose @ move(-half,0,hd+br) @ turn(90,[0,1,0])
            place("nut",2,axle @ move(z=p["nut_start"]+half),lift+radial*9,station)
            place("bearing",3,axle,lift-radial*4,station)
            place("washer",3,axle @ move(z=2*half),lift-radial*2,station)
            place("face_bolt",3,axle @ turn(180,[1,0,0]),lift-radial*13,station)
        for x,y in [*( (p["mount_x"],y) for y in p["mount_positions"]), (p["edge_axle_x"],p["edge_y"])]:
            place("nut",4,origin @ move(x,y,nut_z),[0,0,-38],station)
            place("joint_bolt",7,origin @ move(x,y,surface),[0,0,53],station)
        edge = origin @ move(p["edge_axle_x"],p["edge_y"],-half)
        place("bearing",6,edge,[0,0,0],station)
        place("washer",6,edge @ move(z=-p["washer_depth"]),[0,0,-8],station)
        place("washer",6,edge @ move(z=half*2),[0,0,8],station)
    return items


def publish(**kwargs):
    folder = kwargs["folder"]
    record = kwargs["record"]
    p = get_parameters(geometry=record["oobb_details"])
    parts = define_inventory(guide_count=len(p["station_angles"]),joint_length=p["joint_length"],
                             face_length=p["face_bolt_length"],part_id=record["id"])
    output = folder/"assembly"
    raw = output/"render"/"raw"
    raw.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory() as temporary:
        stage = Path(temporary)
        for key, part in parts.items():
            (stage/(key+".scad")).write_text(f"use <{(folder/'true.scad').as_posix()}>;\n$fn=96;\n{part['entry']}\n")
            export_mesh(executable=kwargs["openscad"],staging=stage,name=key)
        items = assembly_instances(parameters=p,stage=stage)
        if Counter(item["key"] for item in items) != {k:v["quantity"] for k,v in parts.items()}:
            raise ValueError("Assembly poses disagree with the hardware and printed inventory")
        views = []
        for key in parts:
            views.append({
                "name": "part_"+key,
                "show": [key],
                "single": True,
                "eye": [1,-1,-1] if key=="lower" else [1,-1,1],
            })
        steps = []
        for number, spec in enumerate(record["assembly_steps"],1):
            name = f"step_{number:02d}"
            views.append({
                "name": name,
                "show": list(parts),
                "through": number,
                "spread": [1,1,.8,.65,.55,.35,.18,0][number-1],
                "eye": [1,-.8,-1] if number==4 else [1,-1,1],
            })
            if number<=4:
                views[-1]["station"] = 0
            steps.append({
                **spec,
                "key": name,
                "number": number,
                "loose_parts": dict(Counter(item["key"] for item in items if item["step"]==number)),
            })
        views.append({
            "name": "underside",
            "show": list(parts),
            "eye": [1,-1,-1.4],
        })
        for name,spread in (("exploded",1),("book_cover",0)):
            views.append({
                "name": name,
                "show": list(parts),
                "spread": spread,
            })
        job = {
            "output": str(raw),
            "frame_width_mm": p["frame_size"][0],
            "items": items,
            "views": views,
        }
        job_file = stage/"render.json"
        job_file.write_text(json.dumps(job),encoding="utf-8")
        command = [kwargs["blender"],"--background","--factory-startup","--python-exit-code","1",
                   "--python",str(ROOT/"presentation/render_steps.py"),"--",str(job_file)]
        result = subprocess.run(command,capture_output=True,text=True,errors="replace")
        if result.returncode:
            raise RuntimeError(result.stdout[-3500:]+result.stderr[-2000:])
    g = record["oobb_details"]
    title = f'{g["width"]} × {g["height"]} OOBB turret'
    data = {
        "configuration_title": title,
        "style": {
            "page_mm": [297,210],
            "columns": 2,
            "rows": 2,
            "margin_mm": 6,
            "gutter_mm": 4,
            "border": "000000",
            "border_radius_mm": 3,
            "border_width_pt": 3,
            "component_border_width_pt": 1.1,
            "thumbnail_height_mm": 8.5,
            "quantity_shift_mm": 1,
            "font_body_pt": 7,
            "font_code_pt": 6.4,
            "font_url_prefix_pt": 4.8,
            "quantity_pt": 5.8,
        },
        "book": {
            "cover_title": title,
            "cover_subtitle": f'Four 606 guides / Ø{g["turret_diameter"]*15} mm usable centre',
            "project_name": ROOT.name,
            "project_url": PROJECT_URL,
            "logo_svg": "presentation/oomlout-LOGO-unshaded-vector.svg",
            "logo_symbol_subpaths": 3,
            "details_title": "Fitting the guides",
            "details": [
                f'{p["frame_size"][0]:g} mm square frame and Ø{2*p["disc_radius"]:g} mm disc, both {p["depth"]:g} mm thick.',
                "Steps 1–4 show one guide pair. Repeat at all four stations. Quantities cover the complete turret.",
                *[f"{s['number']}. {s['action']}" for s in steps],
                "AI-generated CAD illustrations and instructions. Physical fit has yet to be tested.",
            ],
            "summary_title": "Printed parts",
            "hardware_title": "Purchased hardware",
            "summary_view": "book_cover",
            "signature_pages": 4,
            "summary_step": True,
            "viewer_start": "page-03",
            "viewer_layout": "a4-landscape-four-step",
        },
        "parts": parts,
        "steps": steps,
        "printed_keys": ["frame","rotor","upper","lower"],
        "physical_item_count": len(items),
        "print_layout_sha256": hashlib.sha256((folder/"3dpr.stl").read_bytes()).hexdigest(),
    }
    assembly_booklet.publish(output=output,data=data)
    assembly_booklet.review_outputs(output=output,data=data)
    assembly_viewer.publish(output=output,data=data)
    with (output/"parts.csv").open("w",encoding="utf-8",newline="") as stream:
        writer = csv.DictWriter(stream,["key","name","id","quantity","identity_source","short_url"],extrasaction="ignore")
        writer.writeheader()
        writer.writerows(parts.values())
    for source,target in (("book_cover","studio"),("exploded","exploded"),("underside","underside")):
        with Image.open(raw/(source+".png")) as image:
            sheet = Image.new("RGB",image.size,"#f7f6f1")
            sheet.paste(image,mask=image.getchannel("A"))
            sheet.save(folder/(target+".png"))
    write_part_readme(folder=folder,title=title,record=record,steps=steps,parts=parts)


def write_part_readme(**kwargs):
    folder = kwargs["folder"]
    record = kwargs["record"]
    g = record["oobb_details"]
    instructions = "\n\n".join(
        f"**{s['number']}. {s['title']}**\n\n{s['action']}\n\n"
        f"[![{s['title']}](assembly/cards/{s['key']}.png)](assembly/render/raw/{s['key']}.png)"
        for s in kwargs["steps"]
    )
    inventory = []
    for part in kwargs["parts"].values():
        name = part["name"]
        if "identity_source" in part:
            name = f"[{name}]({part['identity_source']})"
        if part["key"]=="washer":
            name += " × 1.5 mm, 6 mm bore"
        inventory.append(f"| {name} | {part['quantity']} |")
    text = f"""# {kwargs['title']}

AI-generated CAD illustrations and instructions. Physical fit is unverified.

## Summary

![Assembled turret](studio.png)

## Details

The 6 mm frame and disc have a {g['turret_diameter']*15} mm usable centre. Exposed frame edges and housing edges have a 1.5 mm radius. Flat lands support the housings. The lower housing captures all three vertical nuts.

![Underside showing the recessed M6 nuts](underside.png)

## Parts

[Complete print layout](3dpr.stl) · [One-guide fit sample](guide_fit_sample.stl) · [Hardware and quantities](assembly/parts.csv) · [OOMP record](working.yaml)

| Item | Quantity |
|---|---:|
{chr(10).join(inventory)}

![Exploded production assembly](exploded.png)

## Assembly

[Offline illustrated viewer](assembly/assembly_instructions.html) · [Printable booklet](assembly/assembly_instructions.pdf) · [Clearance model](guide_clearance.scad)

The first four illustrations show one guide. Repeat for all four stations. The printed stack is 41 mm from face to face. Each vertical nut seats 7 mm inside the underside. A 40 mm bolt passes fully through the nut and ends 1 mm inside the surface.

{instructions}
"""
    (folder/"README.md").write_text(text,encoding="utf-8")


def main(**kwargs):
    selected = kwargs.get("filter","")
    blender = kwargs.get("blender",shutil.which("blender"))
    openscad = kwargs.get("openscad",shutil.which("openscad.com") or shutil.which("openscad"))
    if not blender or not openscad:
        raise FileNotFoundError("Assembly publishing requires Blender and OpenSCAD on PATH")
    for path in catalogue_records(filter=selected):
        print(f"Publishing assembly for {path.parent.name}",flush=True)
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        publish(folder=path.parent,record=record,blender=blender,openscad=openscad)
    write_catalogue()


def write_catalogue():
    records = sorted(catalogue_records(),key=lambda p:int(p.parent.name.split("_")[3]))
    rows = []
    for path in records:
        part = yaml.safe_load(path.read_text(encoding="utf-8"))["oobb_details"]
        link = "parts/"+path.parent.name
        rows.append(f'| [{part["width"]} × {part["height"]}]({link}/) | Ø{part["turret_diameter"]*15} mm | [STL]({link}/3dpr.stl) | [Viewer]({link}/assembly/assembly_instructions.html) · [PDF]({link}/assembly/assembly_instructions.pdf) |')
    example = records[len(records)//2].parent.relative_to(ROOT).as_posix()
    text = f"""# OOBB turrets

AI-generated CAD illustrations and instructions. Errors possible.

## Summary

Three square frames on the 15 mm OOBB grid carry a rotating 6 mm disc. Four pairs of housings guide the disc on 606 bearings. The editable CAD and generated files are included for printing and modification.

[![Assembled 9 × 9 turret]({example}/studio.png)]({example}/)

## Details

The exposed plate and housing edges have a 1.5 mm radius. Flat housing lands carry the clamping load. Each face roller runs on an M6 × 20 external-hex bolt. Three M6 × 40 bolts per station engage nuts recessed into the lower housing. Washers are M6 × Ø14 × 1.5 mm at the bearing-to-print interfaces.

## Parts

| Frame | Usable centre | Full print | Assembly |
|---|---|---|---|
{chr(10).join(rows)}

## Assembly

Start with the [one-guide fit sample]({example}/guide_fit_sample.stl) to check nut capture, washer seats and roller adjustment. The illustrated books show the full hardware inventory and sequence. Physical fit has yet to be tested.

Run `python working.py` to populate the records and rebuild the drawings, print models, renders and assembly books. Run `python working.py --assembly-only` to republish from the current CAD. Run `python -m unittest discover -s tests` for the fit and mesh checks.
"""
    (ROOT/"README.md").write_text(text,encoding="utf-8")


if __name__ == "__main__":
    main()
