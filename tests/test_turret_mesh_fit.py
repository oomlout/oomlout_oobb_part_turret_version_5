"""Check the exported print bodies and nominal assembly using the current OpenSCAD models."""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

import trimesh
import yaml

from working_oomp_populate import catalogue_records
from turret_cad import export_mesh, get_parameters
from working_svg import get_disc_pattern


class TurretMeshFitTests(unittest.TestCase):
    def test_rotor_has_m3_through_holes_and_a_solid_running_track(self):
        counts = {
            3: 16,
            5: 48,
            7: 108,
        }
        for record in catalogue_records():
            with self.subTest(part=record.parent.name):
                g = yaml.safe_load(record.read_text(encoding="utf-8"))["oobb_details"]
                pattern = get_disc_pattern(**g)
                holes = pattern["m3_holes"]
                self.assertEqual(len(holes),counts[g["turret_diameter"]])
                self.assertFalse(set(holes).intersection(pattern["holes"]))
                diameter = 2*g["housing"]["disc_radius_mm"]
                solids = trimesh.load_mesh(record.with_name("3dpr.stl")).split()
                disc = next(s for s in solids if abs(s.extents[0]-diameter)<.001)
                self.assertEqual(disc.euler_number, 2-2*(len(holes)+len(pattern["holes"])))
                self.assertFalse(disc.contains([(x,y,3) for x,y in holes]).any())
                radius = g["disc_m3_hole_diameter_mm"]/2
                self.assertEqual(disc.contains([(7.5+radius-.05,0,3),(7.5+radius+.05,0,3)]).tolist(),[False,True])
                self.assertTrue(all((x*x+y*y)**.5+radius <= pattern["usable_radius"] for x,y in holes))

    def test_frame_roundover_leaves_flat_housing_lands(self):
        for record in catalogue_records():
            with self.subTest(part=record.parent.name):
                geometry = yaml.safe_load(record.read_text(encoding="utf-8"))["oobb_details"]
                width = geometry["width"]*geometry["pitch_mm"]-geometry["plate_edge_reduction_mm"]
                solids = trimesh.load_mesh(record.with_name("3dpr.stl")).split()
                frame = next(s for s in solids if abs(s.extents[0]-width)<.001 and abs(s.extents[2]-6)<.001)
                x = width/2-.3
                # At 0.3 mm inboard the R1.5 arc meets the section at z=0.6 and 5.4.
                probes = [(x,-30,z) for z in (.5,.7,5.3,5.5)]
                probes += [(x,4,.05),(x,4,5.95)]
                self.assertEqual(frame.contains(probes).tolist(),[False,True,True,False,True,True])

    def test_recessed_nut_shoulders_and_exposed_housing_radius(self):
        executable = shutil.which("openscad.com") or shutil.which("openscad")
        record = next(catalogue_records())
        g = yaml.safe_load(record.read_text(encoding="utf-8"))["oobb_details"]
        p = get_parameters(geometry=g)
        height = p["bearing_od"]/2+p["washer_od"]/2+2
        stack = 2*height+p["depth"]
        recess = stack+p["nut_height"]+p["thread_beyond_nut"]-p["joint_length"]
        self.assertEqual((stack,recess,p["joint_length"]), (41,7,40))
        self.assertEqual(stack-p["joint_length"], 1)
        with TemporaryDirectory() as temp:
            stage = Path(temp)
            for name in ("upper","lower"):
                entry = "clamp_half(lower=true);" if name=="lower" else "clamp_half();"
                source = f"use <{record.with_name('true.scad').as_posix()}>;\n$fn=96;\n{entry}"
                (stage/(name+".scad")).write_text(source)
                export_mesh(executable=executable,staging=stage,name=name)
                half = trimesh.load_mesh(stage/(name+".stl"))
                shoulder = height-recess
                positions = [(p["mount_x"],y) for y in p["mount_positions"]]
                positions += [(x,p["edge_y"]) for x in p["slot_ends"]]
                for x,y in positions:
                    probes = [(x,y+4.1,shoulder-.1),(x,y+4.1,shoulder+.1)]
                    self.assertEqual(half.contains(probes).tolist(),[True,name=="upper"])
                x = p["clamp_outer_x"]-.3
                probes = [(x,-7,height-.7),(x,-7,height-.5),(x,-7,.04)]
                self.assertEqual(half.contains(probes).tolist(),[True,False,True])

    def test_print_and_sample_bodies(self):
        for record in catalogue_records():
            for model, count in (("3dpr",10),("guide_fit_sample",4),("guide_pair",2)):
                with self.subTest(part=record.parent.name, model=model):
                    mesh = trimesh.load_mesh(record.with_name(f"{model}.stl"))
                    bodies = mesh.split(only_watertight=False)
                    self.assertEqual(len(bodies),count)
                    for body in bodies:
                        self.assertTrue(body.is_volume)
                        self.assertAlmostEqual(body.bounds[0,2],0,places=5)

    def test_edge_race_clears_both_printed_housings_through_full_travel(self):
        for record in catalogue_records():
            geometry = yaml.safe_load(record.read_text(encoding="utf-8"))["oobb_details"]
            guide = geometry["guide"]
            clamp = guide["common_clamp"]
            params = get_parameters(geometry=geometry)
            play = (clamp["slot_width_mm"]-guide["bore_mm"])/2
            radius = guide["od_mm"]/2 + play + clamp["edge_pocket_clearance_mm"]
            seat = (guide["width_mm"] - geometry["depth"])/2 + guide["washer_thickness_mm"]
            # The convex hull represents every shaft position, including sideways play.
            # Allow 0.005 mm for the polygonal representation of circular surfaces.
            ends = []
            for x in clamp["slot_x_mm"]:
                cylinder = trimesh.creation.cylinder(radius=radius-.005,height=seat-.005,sections=192)
                cylinder.apply_translation([x,clamp["edge_y_mm"],(seat-.005)/2])
                ends.append(cylinder)
            sweep = trimesh.util.concatenate(ends).convex_hull
            pair = trimesh.load_mesh(record.with_name("guide_pair.stl")).split()
            self.assertEqual(len(pair),2)
            for index, half in enumerate(sorted(pair,key=lambda mesh:mesh.centroid[0])):
                with self.subTest(part=record.parent.name,half=("upper","lower")[index]):
                    sign = 1 if index==0 else -1
                    mating_x = half.bounds[index,0]
                    # Undo the layout's outboard-face-down printing orientation.
                    half.apply_transform([
                        [0,0,-1,params["clamp_outer_x"]],
                        [0,1,0,params["clamp_y_min"]],
                        [sign,0,0,-sign*mating_x],
                        [0,0,0,1],
                    ])
                    overlap = trimesh.boolean.intersection([half,sweep],engine="manifold")
                    self.assertLess(abs(overlap.volume),.0001)
                    # The washer must still bear on a solid floor at both stops.
                    low,high = clamp["slot_x_mm"]
                    for stop in (low-play,high+play):
                        probes = [(stop,clamp["edge_y_mm"]+4,seat+d) for d in (-.02,.02)]
                        self.assertEqual(half.contains(probes).tolist(),[False,True])

    def test_nominal_assembly_intersections(self):
        executable = shutil.which("openscad.com") or shutil.which("openscad")
        self.assertIsNotNone(executable)
        pairs = [
            ("assembled_frame()", "assembled_disc()"),
            ("assembled_frame()", "assembled_clamps()"),
            ("assembled_frame()", "assembled_hardware(true,false)"),
            ("assembled_disc()", "assembled_clamps()"),
            ("assembled_disc()", "assembled_hardware()"),
            ("assembled_clamps()", "assembled_hardware()"),
        ]
        with TemporaryDirectory() as temp:
            stage = Path(temp)
            for record in catalogue_records():
                with self.subTest(part=record.parent.name):
                    assembly = record.with_name("true.scad").as_posix()
                    # A separate 1 mm³ cube lets OpenSCAD export an empty collision result.
                    script = [f"use <{assembly}>;", "$fn=96;", "translate([250,0,0]) cube(1);"]
                    for first, second in pairs:
                        script.append(f"intersection() {{ {first}; {second}; }}")
                    (stage/"test.scad").write_text("\n".join(script), encoding="utf-8")
                    command = [executable,"--backend=Manifold","--export-format","binstl",
                               "-o","test.stl","test.scad"]
                    result = subprocess.run(command,cwd=stage,capture_output=True,text=True)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertNotIn("ERROR:",result.stderr)
                    self.assertNotIn("WARNING:",result.stderr)
                    self.assertAlmostEqual(trimesh.load_mesh(stage/"test.stl").volume, 1, places=3)
