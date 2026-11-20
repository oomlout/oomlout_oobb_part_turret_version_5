from math import acos, degrees, dist, hypot
import unittest

from shapely.affinity import rotate
from shapely.geometry import Point, Polygon
from turret_offset_review import get_frame_holes, get_frame_opening, get_offset_layout
from working_oomp_populate import get_frame_options, get_part
from working_svg import get_disc_pattern


class CommonClampTests(unittest.TestCase):
    def test_one_printed_profile_and_cutout_fits_every_catalogue_disc(self):
        reference = None
        for option in get_frame_options():
            with self.subTest(option=option):
                geometry = get_part(**option)["oobb_details"]
                housing = geometry["housing"]
                guide = geometry["guide"]
                face = housing["face_axle_radius_mm"]
                layout = get_offset_layout(pattern=get_disc_pattern(**geometry), **geometry)
                station = layout["stations"][0]
                profile = {
                    "outline": [(round(x-face, 8), y) for x, y in station["outline"]],
                    "bolts": [(x-face, y) for x, y in station["bolt_positions"]],
                    "common_clamp": guide["common_clamp"],
                    "face_bolt": housing["face_bolt"],
                    "boss_start": layout["boss_start"]-face,
                    "pocket": (layout["pocket_start"]-face, layout["pocket_end"]-face,
                               layout["axle_y"], layout["pocket_half_width"]),
                }
                if reference is None:
                    reference = profile
                self.assertEqual(reference, profile)
                self.assertAlmostEqual(hypot(layout["axle_x"], layout["axle_y"]),
                                       housing["disc_radius_mm"] + guide["od_mm"]/2)
                self.assertGreater(layout["roller_gap"], 2.5)
                # Keep the disc bolt holes clear even when the larger hex head overhangs the rim.
                self.assertGreater(layout["running_clearance"], 0)
                bore_sweep = layout["outer_hole_radius"] + geometry["m6_hole_diameter_mm"]/2
                self.assertGreaterEqual(layout["retainer_tip"] - bore_sweep, 2)
                self.assertGreater(layout["pocket_margin"], 0)

    def test_bearing_travel_and_flush_guide(self):
        for option in get_frame_options():
            with self.subTest(option=option):
                geometry = get_part(**option)["oobb_details"]
                guide = geometry["guide"]
                clamp = guide["common_clamp"]
                layout = get_offset_layout(pattern=get_disc_pattern(**geometry), **geometry)
                face = geometry["housing"]["face_axle_radius_mm"]
                lower, upper = clamp["slot_x_mm"]
                play = (clamp["slot_width_mm"] - guide["bore_mm"])/2
                self.assertAlmostEqual(upper-lower+2*play, 2.5)
                offset = layout["axle_x"]-face
                self.assertGreater(min(offset-lower+play, upper+play-offset), .14)
                opening = get_frame_opening(layout=layout, **geometry)
                for end in (lower-play, upper+play):
                    centre = Point(face+end,layout["axle_y"])
                    self.assertGreater(opening.boundary.distance(centre)-guide["od_mm"]/2, .49)
                footprint = Polygon(layout["stations"][0]["outline"])
                self.assertGreater(footprint.distance(Point(0,0)), geometry["housing"]["disc_radius_mm"])
                self.assertEqual((guide["width_mm"]+2*guide["washer_thickness_mm"]-geometry["depth"])/2, 1.5)
                bolt = geometry["housing"]["face_bolt"]
                nut_end = clamp["nut_pocket_start_mm"]+5
                self.assertGreaterEqual(bolt["length_mm"]-guide["width_mm"]/2, nut_end)
                self.assertGreater(clamp["outer_x_mm"],nut_end)

    def test_housing_corner_turns_and_frame_grid(self):
        for option in get_frame_options():
            with self.subTest(option=option):
                geometry = get_part(**option)["oobb_details"]
                layout = get_offset_layout(pattern=get_disc_pattern(**geometry), **geometry)
                outline = layout["stations"][0]["outline"]
                for i, point in enumerate(outline):
                    before = outline[i-1]
                    after = outline[(i+1)%len(outline)]
                    dot = sum((p-a)*(b-p) for a,p,b in zip(before,point,after))
                    cosine = dot/(dist(point,before)*dist(point,after))
                    self.assertLess(degrees(acos(max(-1,min(1,cosine)))), 6)
                holes = get_frame_holes(layout=layout, **geometry)
                self.assertTrue(holes)
                for angle in layout["angles"]:
                    footprint = rotate(Polygon(outline),angle,origin=(0,0))
                    for x,y,radius in holes:
                        self.assertGreaterEqual(footprint.distance(Point(x,y)), radius+1-1e-6)
