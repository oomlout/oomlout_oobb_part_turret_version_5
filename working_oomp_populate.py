"""Editable review part and common 606 guide. Dimensions are millimetres unless noted."""
from contextlib import chdir
from pathlib import Path

from oomp_populate_helper import build_oomp_id, write_extras


def get_606_guide(**kwargs):
    # Plan coordinates use the disc rim as zero, positive outward.
    bearing_od_mm = 17
    bolt_spacing_mm = 18
    return {
        # Local origin is the face-roller centre. X points outward, Y along the side.
        "common_clamp": {
            "outer_x_mm": 19.5,
            "boss_x_mm": 4.5,
            "mount_x_mm": 12,
            "mount_y_mm": [-15, 37.5],
            "end_margin_mm": 8,
            "edge_y_mm": 19.5,
            "slot_x_mm": [3.67, 5.67],
            "slot_width_mm": 6.5,
            "slot_lug_radius_mm": 5.5,
            "corner_radius_mm": 1.5,
            "pocket_blend_radius_mm": 1,
            "outer_edge_radius_mm": 1.5,
            "lower_nut_lug_radius_mm": 8,
            "edge_pocket_clearance_mm": 0.5,
            "washer_pocket_clearance_mm": 0.25,
            "horizontal_bolt_bore_mm": 6.4,
            "nut_pocket_start_mm": 12,
        },
        "bore_mm": 6,
        "od_mm": bearing_od_mm,
        "width_mm": 6,
        "clamp_bolt_length_mm": 40,
        "nut_thickness_mm": 5,
        "thread_beyond_nut_mm": 1,
        "washer_id_mm": 6,
        "washer_od_mm": 14,
        "washer_thickness_mm": 1.5,
        "clamp_inner_x_mm": -16,
        "clamp_outer_x_mm": 21,
        "clamp_half_width_mm": bolt_spacing_mm + 8,
        "face_axle_x_mm": -8,
        "cutout_inner_x_mm": -6,
        "cutout_outer_x_mm": 19,
        "cutout_half_width_mm": 10,
        "bolt_row_x_mm": bearing_od_mm / 2,
        "mount_y_mm": [-bolt_spacing_mm, bolt_spacing_mm],
    }


def get_frame_options(**kwargs):
    return [
        {
            "width": 11,
            "height": 11,
            "turret_diameter": 7,
        },
        {
            "width": 9,
            "height": 9,
            "turret_diameter": 5,
        },
        {
            "width": 7,
            "height": 7,
            "turret_diameter": 3,
        },
    ]


def get_assembly_steps(**kwargs):
    return [
        {
            "title": "Identify the housings",
            "action": "Set out the four guide pairs. Each lower housing has three hex recesses on its outside face.",
        },
        {
            "title": "Load the face-axle nuts",
            "action": "Press one M6 nut into the side opening of every upper and lower housing.",
        },
        {
            "title": "Fit the face rollers",
            "action": "Pass an M6 × 20 hex bolt through each 606 bearing and one washer. Screw it into the side nut. Keep the washer against the printed housing.",
        },
        {
            "title": "Load the lower housings",
            "action": "Press three M6 nuts into the underside of each lower housing. The centre nut can slide along its pocket for edge adjustment.",
        },
        {
            "title": "Seat the frame and disc",
            "action": "Set the frame on the four lower housings with their mounting holes aligned. Centre the disc in the opening with its underside on the face rollers.",
        },
        {
            "title": "Stack the edge rollers",
            "action": "At each station, sandwich one 606 edge bearing between two washers. Centre the washers over the axle slot and lower the upper housing onto the flat frame land.",
        },
        {
            "title": "Join the guides",
            "action": "Install three M6 × 40 hex bolts from above at each station. The two outer bolts join the housings to the frame. Leave the edge-axle bolt loose for adjustment.",
        },
        {
            "title": "Set the running fit",
            "action": "Bring each edge roller into light contact. Tighten the edge axles and turn the disc through a full revolution. Check that the rollers turn freely and the housings sit flat.",
        },
    ]


def get_part(**kwargs):
    width = kwargs.get("width", 9)
    height = kwargs.get("height", width)
    depth = kwargs.get("depth", 6)
    turret_diameter = kwargs.get("turret_diameter", width - 4 if width in (7, 9, 11) else 5)
    for frame in get_frame_options(**kwargs):
        if (frame["width"], frame["height"], frame["turret_diameter"]) == (width, height, turret_diameter):
            kwargs = {
                **frame,
                **kwargs,
            }
            break
    bearing = kwargs.get("bearing", "606")
    offset_housing = kwargs.get("offset_housing", True)
    face_axle_radius_mm = kwargs.get("face_axle_radius_mm", turret_diameter * 15 / 2 + 10)
    face_contact_mm = kwargs.get("face_contact_mm", 3)
    station_rotation_deg = kwargs.get("station_rotation_deg", 0)
    face_bolt_length_mm = kwargs.get("face_bolt_length_mm", 20)
    guide = get_606_guide(**kwargs)
    if not 0 < face_contact_mm <= guide["width_mm"]:
        raise ValueError("Face contact must fit within the width of the 606 tread")
    disc_radius_mm = kwargs.get("disc_radius_mm", face_axle_radius_mm - guide["width_mm"] / 2 + face_contact_mm)
    required_face_radius = disc_radius_mm + guide["width_mm"] / 2 - face_contact_mm
    if "face_axle_radius_mm" in kwargs and abs(required_face_radius - face_axle_radius_mm) > 0.00001:
        raise ValueError("The selected disc, axle and tread overlap dimensions disagree")
    face_axle_radius_mm = required_face_radius
    disc_to_frame_gap_mm = kwargs.get("disc_to_frame_gap_mm", 1)
    guide_angles_by_side = kwargs.get("guide_angles_by_side", {
        "east": [0],
        "north": [90],
        "west": [180],
        "south": [270],
    })
    guide_count = sum(len(angles) for angles in guide_angles_by_side.values())
    number_of_guides = kwargs.get("number_of_guides", guide_count)
    if number_of_guides != guide_count or guide_count < 1:
        raise ValueError("number_of_guides must match the populated side positions")
    if bearing != "606":
        raise ValueError("Only the 606 guide has a review profile")

    geometry = {
        "oobb_type": "turret",
        "run_scad": True,
        "run_solidcraft": False,
        "width": width,
        "height": height,
        "depth": depth,
        "turret_diameter": turret_diameter,
        "bearing": bearing,
        "number_of_guides": number_of_guides,
        "guide_angles_by_side": guide_angles_by_side,
        "guide": guide,
        "pitch_mm": 15,
        "plate_edge_reduction_mm": 1,
        "plate_edge_radius_mm": 1.5,
        "m6_hole_diameter_mm": 6.5,
        "outer_bolt_envelope_diameter_mm": 11.54,
        "guide_clearance_from_sweep_mm": 2,
        "disc_to_frame_gap_mm": disc_to_frame_gap_mm,
    }
    drawing = "turret_review"
    if offset_housing:
        drawing = "offset_housing_review"
        geometry["housing"] = {
            "common_clamp": True,
            "disc_radius_mm": disc_radius_mm,
            "opening_radius_mm": disc_radius_mm + disc_to_frame_gap_mm,
            "station_rotation_deg": station_rotation_deg,
            "face_axle_radius_mm": face_axle_radius_mm,
            "face_contact_mm": face_contact_mm,
            "face_relief_clearance_mm": 0.5,
            "boss_thickness_mm": 12,
            "face_bolt": {
                "style": "external_hex",
                "diameter_mm": 6,
                "length_mm": face_bolt_length_mm,
                "head_diameter_mm": 11.54,
                "head_height_mm": 4,
            },
            "material_beyond_washer_mm": 1,
        }
    return {
        "taxonomy_1": "oobb",
        "taxonomy_2": "part",
        "taxonomy_3": "turret",
        "taxonomy_4": f"{width}_width",
        "taxonomy_5": f"{height}_height",
        "taxonomy_6": f"{depth}_depth",
        "taxonomy_7": f"{turret_diameter}_turret_diameter",
        "taxonomy_8": f"{bearing}_bearing",
        "taxonomy_9": f"{number_of_guides}_number_of_guides",
        "oobb_type": "turret",
        "oobb_details": geometry,
        "svg_details": {
            "svg_name": drawing,
        },
        "assembly_steps": get_assembly_steps(**kwargs),
        "plate_3dpr_contents": {
            "outer_plate": 1,
            "disc": 1,
            "top_clamp": number_of_guides,
            "bottom_clamp": number_of_guides,
        },
    }


def get_active_parts(**kwargs):
    frame_options = get_frame_options(**kwargs)
    if "width" in kwargs or "height" in kwargs:
        frame_options = [{}]
    elif "turret_diameter" in kwargs:
        frame_options = [frame for frame in frame_options if frame["turret_diameter"] == kwargs["turret_diameter"]]
    parts = []
    for frame in frame_options:
        options = frame.copy()
        options.update(kwargs)
        part = get_part(**options)
        parts.append(part)
    return parts


def catalogue_records(**kwargs):
    stage = kwargs.get("stage", "parts")
    selected = kwargs.get("filter", "")
    root = Path(__file__).resolve().parent
    for part in get_active_parts(**kwargs):
        part_id = build_oomp_id(part)
        path = root / stage / part_id / "working.yaml"
        if selected in part_id and path.is_file():
            yield path


def main(**kwargs):
    selected = kwargs.get("filter", "")
    project_directory = Path(__file__).resolve().parent
    parts = [part for part in get_active_parts(**kwargs) if selected in build_oomp_id(part)]
    if parts:
        with chdir(project_directory):
            write_extras(parts)


if __name__ == "__main__":
    main()
