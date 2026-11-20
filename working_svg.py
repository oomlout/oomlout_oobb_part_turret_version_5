"""Render the two review sheets from the materialized OOMP part."""
from math import cos, hypot, radians, sin, sqrt
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle
from matplotlib.transforms import Affine2D
import yaml


PAPER = "#fcfbf7"
INK = "#243841"
MUTED = "#506570"
FRAME = "#dae3e5"
DISC = "#a9d7cf"
TRACK = "#d4ebe5"
CLAMP = "#e9ae74"
BEARING = "#677b90"
WASHER = "#f6d45c"
ACCENT = "#ad4e2e"


def get_disc_pattern(**kwargs):
    diameter = kwargs["turret_diameter"]
    pitch = kwargs["pitch_mm"]
    bolt_radius = kwargs["outer_bolt_envelope_diameter_mm"] / 2
    usable_radius = diameter * pitch / 2
    hole_radius = kwargs["m6_hole_diameter_mm"] / 2
    holes = []
    for row in range(diameter):
        for column in range(diameter):
            x = (column - (diameter - 1) / 2) * pitch
            y = (row - (diameter - 1) / 2) * pitch
            if hypot(x, y) + hole_radius <= usable_radius:
                holes.append((x, y))
    outer_hole_radius = max(hypot(x, y) for x, y in holes)
    bolt_sweep = outer_hole_radius + bolt_radius
    return {
        "holes": holes,
        "outer_hole_radius": outer_hole_radius,
        "bolt_sweep": bolt_sweep,
        "usable_radius": usable_radius,
    }


def get_layout(**kwargs):
    width = kwargs["width"]
    height = kwargs["height"]
    pitch = kwargs["pitch_mm"]
    guide = kwargs["guide"]
    pattern = get_disc_pattern(**kwargs)
    usable_radius = pattern["usable_radius"]
    bolt_sweep = pattern["bolt_sweep"]
    protected_radius = max(usable_radius, bolt_sweep)
    disc_radius = protected_radius + kwargs["guide_clearance_from_sweep_mm"] - guide["clamp_inner_x_mm"]
    plate_w = width * pitch - kwargs["plate_edge_reduction_mm"]
    plate_h = height * pitch - kwargs["plate_edge_reduction_mm"]
    angles = [angle for side in kwargs["guide_angles_by_side"].values() for angle in side]
    if disc_radius + kwargs["disc_to_frame_gap_mm"] >= min(plate_w, plate_h) / 2:
        raise ValueError("The rotating disc opening exceeds the selected frame")
    edge_clearance = min(plate_w, plate_h) / 2
    for angle in angles:
        theta = radians(angle)
        for tip in (guide["clamp_inner_x_mm"], guide["clamp_outer_x_mm"]):
            for offset in (-guide["clamp_half_width_mm"], guide["clamp_half_width_mm"]):
                x = (disc_radius + tip) * cos(theta) - offset * sin(theta)
                y = (disc_radius + tip) * sin(theta) + offset * cos(theta)
                edge_clearance = min(edge_clearance, plate_w / 2 - abs(x), plate_h / 2 - abs(y))
                if abs(x) > plate_w / 2 or abs(y) > plate_h / 2:
                    raise ValueError(f"The guide at {angle} degrees extends beyond the frame")
    return {
        **pattern,
        "disc_radius": disc_radius,
        "plate_w": plate_w,
        "plate_h": plate_h,
        "angles": angles,
        "clamp_edge_clearance_mm": edge_clearance,
    }


def make_sheet(**kwargs):
    title = kwargs["title"]
    subtitle = kwargs["subtitle"]
    figure = plt.figure(figsize=(12, 6.8), facecolor=PAPER)
    figure.text(.052, .905, title, size=25, weight="bold", color=INK)
    figure.text(.054, .852, subtitle, size=11.5, color=MUTED)
    return figure


def make_axis(**kwargs):
    figure = kwargs["figure"]
    bounds = kwargs["bounds"]
    axis = figure.add_axes(bounds, aspect="equal")
    axis.set_axis_off()
    return axis


def note(**kwargs):
    figure = kwargs["figure"]
    x = kwargs["x"]
    y = kwargs["y"]
    color = kwargs.get("color", INK)
    figure.text(x, y, kwargs["title"], weight="bold", fontsize=13, color=color)
    figure.text(x, y - .032, kwargs["body"], va="top", linespacing=1.45, fontsize=10.5, color=INK)


def draw_plan(**kwargs):
    guide = kwargs["guide"]
    layout = kwargs["layout"]
    row_x = guide["bolt_row_x_mm"]
    radius = layout["disc_radius"]
    usable = layout["usable_radius"]
    sweep = layout["bolt_sweep"]
    width = layout["plate_w"]
    height = layout["plate_h"]
    hole_radius = kwargs["m6_hole_diameter_mm"] / 2
    gap = kwargs["disc_to_frame_gap_mm"]
    figure = make_sheet(
        title="Turret plate and rotating disc",
        subtitle=f'{kwargs["width"]} × {kwargs["height"]} OOBB frame     /     {kwargs["depth"]} mm plate and disc thickness     /     Top view',
    )
    axis = make_axis(figure=figure, bounds=[.036, .067, .555, .73])
    axis.set_xlim(-width / 2 - 3, width / 2 + 3)
    axis.set_ylim(-height / 2 - 3, height / 2 + 3)
    axis.add_patch(FancyBboxPatch((-width / 2, -height / 2), width, height,
                                  boxstyle="round,pad=0,rounding_size=4", fc=FRAME, ec=INK))
    # Reserve the footprint of each guide when showing the frame mounting grid.
    for row in range(kwargs["height"]):
        for column in range(kwargs["width"]):
            x = (column - (kwargs["width"] - 1) / 2) * kwargs["pitch_mm"]
            y = (row - (kwargs["height"] - 1) / 2) * kwargs["pitch_mm"]
            if hypot(x, y) < radius + gap + hole_radius + 2:
                continue
            reserved = False
            for angle in layout["angles"]:
                theta = radians(angle)
                radial = x * cos(theta) + y * sin(theta) - radius
                tangent = -x * sin(theta) + y * cos(theta)
                if (guide["clamp_inner_x_mm"] - hole_radius <= radial <= guide["clamp_outer_x_mm"] + hole_radius
                        and abs(tangent) <= guide["clamp_half_width_mm"] + hole_radius):
                    reserved = True
            if not reserved:
                axis.add_patch(Circle((x, y), hole_radius, fc=PAPER, ec=MUTED, lw=.65))

    axis.add_patch(Circle((0, 0), radius + gap, fc=PAPER, ec=INK, lw=.65))
    axis.add_patch(Circle((0, 0), radius, fc=TRACK, ec=INK))
    axis.add_patch(Circle((0, 0), usable, fc=DISC, ec="#4d837d", lw=.8))
    axis.add_patch(Circle((0, 0), sweep, fill=False, ec=ACCENT, ls="--", lw=1.35))
    for x, y in layout["holes"]:
        axis.add_patch(Circle((x, y), hole_radius, fc=PAPER, ec=INK, lw=.8))
    # One outermost hole carries an example bolt envelope.
    x, y = max(layout["holes"], key=lambda point: (hypot(*point), point[0], point[1]))
    axis.add_patch(Circle((x, y), kwargs["outer_bolt_envelope_diameter_mm"] / 2,
                          fill=False, ec=ACCENT, lw=1.3))
    for angle in layout["angles"]:
        transform = Affine2D().translate(radius, 0).rotate_deg(angle) + axis.transData
        i = guide["clamp_inner_x_mm"]
        o = guide["clamp_outer_x_mm"]
        half = guide["clamp_half_width_mm"]
        axis.add_patch(Rectangle((i, -half), o - i, 2 * half, transform=transform, fc=CLAMP, ec=INK))
        for y in guide["mount_y_mm"]:
            axis.add_patch(Circle((row_x, y), hole_radius, transform=transform, fc=PAPER, ec=INK))
        axis.add_patch(Circle((row_x, 0), guide["bore_mm"] / 2,
                              transform=transform, fc=BEARING, ec=INK))
    note(figure=figure, x=.604, y=.727, color="#386b65", title=f'Ø{2 * usable:g} mm usable circle',
         body=f'{kwargs["turret_diameter"]} OOBB units on a {kwargs["pitch_mm"]} mm pitch.\nThe pale outer ring carries the face rollers.')
    note(figure=figure, x=.604, y=.534, color=ACCENT, title=f'Ø{2 * sweep:.1f} mm bolt sweep',
         body=f'The dashed line traces an outer M6 bolt with\na Ø{kwargs["outer_bolt_envelope_diameter_mm"]:g} mm envelope over a full turn. The nearest\nclamp tip clears it by {radius + guide["clamp_inner_x_mm"] - sweep:.1f} mm.')
    note(figure=figure, x=.604, y=.314, title=f'{len(layout["angles"])} two-sided guides',
         body=f'The centre bolt carries the edge bearing. The\ntwo flanking bolts join both clamps to the plate.\nThe clamps clear the plate edge by at least {layout["clamp_edge_clearance_mm"]:.2f} mm.')
    figure.text(.604, .098, f'Frame  {width:g} × {height:g} mm     /     Disc OD  {2 * radius:.1f} mm',
                color=MUTED, fontsize=10)
    return figure


def draw_section(**kwargs):
    guide = kwargs["guide"]
    row_x = guide["bolt_row_x_mm"]
    face_x = guide["face_axle_x_mm"]
    outer = guide["clamp_outer_x_mm"]
    inner = guide["clamp_inner_x_mm"]
    half_depth = kwargs["depth"] / 2
    br = guide["od_mm"] / 2
    bw = guide["width_mm"]
    wt = guide["washer_thickness_mm"]
    wr = guide["washer_od_mm"] / 2
    bore = guide["bore_mm"]
    slot = guide["cutout_outer_x_mm"]
    seat = bw / 2 + wt
    layout = kwargs["layout"]
    theta = radians(layout["angles"][0])
    # First intersection of this guide's centreline with the rectangular frame.
    frame_edge = 1 / max(2 * abs(cos(theta)) / layout["plate_w"],
                         2 * abs(sin(theta)) / layout["plate_h"]) - layout["disc_radius"]
    figure = make_sheet(title="One 606 guide, in section",
                        subtitle="Radial section through the roller axles     /     Disc centre to the left, stationary frame to the right")
    axis = make_axis(figure=figure, bounds=[.035, .33, .58, .44])
    axis.set_xlim(-32, 41)
    axis.set_ylim(-29, 29)

    def block(**kwargs):
        x = kwargs["x"]
        z = kwargs["z"]
        width = kwargs["width"]
        height = kwargs["height"]
        axis.add_patch(Rectangle((x, z), width, height, fc=kwargs["color"], ec=INK, lw=.8))

    block(x=-32, z=-half_depth, width=32, height=2 * half_depth, color=DISC)
    block(x=slot, z=-half_depth, width=frame_edge-slot, height=2 * half_depth, color=FRAME)
    block(x=row_x-br, z=-bw / 2, width=2 * br, height=bw, color=BEARING)
    for sign in (1, -1):
        face_z = half_depth + br
        # The fork straddles the face roller. Its bridge passes above the OD.
        fork_left = face_x - bw / 2 - wt
        fork_right = face_x + bw / 2 + wt
        cap_z = face_z + br + 1
        outline = [(inner, face_z-4), (fork_left, face_z-4), (fork_left, cap_z),
                   (fork_right, cap_z), (fork_right, face_z-4), (0, face_z-4),
                   (0, seat), (slot, seat), (slot, half_depth), (outer, half_depth),
                   (outer, face_z+2), (1, face_z+2), (1, cap_z+3), (inner, cap_z+3)]
        axis.add_patch(Polygon([(x, sign*z) for x,z in outline], fc=CLAMP, ec=INK, lw=1))
        block(x=face_x-bw/2, z=sign*face_z-br, width=bw, height=2*br, color=BEARING)
        for x in (fork_left, face_x+bw/2):
            block(x=x, z=sign*face_z-wr, width=wt, height=2*wr, color=WASHER)
        block(x=row_x-wr, z=min(sign*bw/2, sign*seat), width=2*wr, height=wt, color=WASHER)
        axis.plot([inner, 1], [sign*face_z]*2, color=INK, lw=1, ls="-.")
    block(x=row_x-bore/2, z=-half_depth-7, width=bore, height=2*half_depth+14, color="#c9d0d8")
    axis.plot([row_x, row_x], [-half_depth-10, half_depth+10], color=INK, lw=.9, ls="-.")
    axis.text(-31, 0, "DISC", va="center", fontsize=8, weight="bold", color=INK)
    axis.annotate("FRAME", xy=((slot + min(frame_edge, 41)) / 2, 0), xytext=(39, -11),
                  ha="right", va="center", fontsize=8, weight="bold", color=INK,
                  arrowprops={
                      "arrowstyle": "-",
                      "color": MUTED,
                  })
    figure.text(.059, .285, "Radial axle  ·  one per face roller", fontsize=12, weight="bold", color=INK)
    figure.text(.059, .228, "The upper and lower rollers run on the disc faces. Yellow marks\na washer at every printed fork-to-bearing interface.", fontsize=10.5, color=INK)
    figure.text(.059, .147, "Vertical axle  ·  one per guide", fontsize=12, weight="bold", color=INK)
    figure.text(.059, .090, "The flat centre roller follows the rim. Its washer–606–washer stack\nis 1.5 + 6 + 1.5 = 9 mm between the clamp seats.", fontsize=10.5, color=INK)

    footprint = make_axis(figure=figure, bounds=[.653,.43,.28,.31])
    half = guide["clamp_half_width_mm"]
    notch = guide["cutout_half_width_mm"]
    left = guide["cutout_inner_x_mm"]
    footprint.set_xlim(left-7,outer+6)
    footprint.set_ylim(-half-5,half+5)
    # Show the actual circular opening and the same local notch at every station.
    frame_to_local = (Affine2D().rotate(-theta).translate(-layout["disc_radius"], 0)
                      + footprint.transData)
    footprint.add_patch(Rectangle((-layout["plate_w"]/2, -layout["plate_h"]/2),
                                  layout["plate_w"], layout["plate_h"],
                                  transform=frame_to_local, fc=FRAME, ec=INK, lw=.8))
    r = kwargs["layout"]["disc_radius"]
    footprint.add_patch(Circle((-r,0),r+kwargs["disc_to_frame_gap_mm"],fc=PAPER,ec=INK,lw=.8))
    footprint.add_patch(Rectangle((left,-notch),slot-left,2*notch,fc=PAPER,ec="none"))
    mouth = sqrt((r + kwargs["disc_to_frame_gap_mm"]) ** 2 - notch ** 2) - r
    footprint.plot([mouth,slot,slot,mouth],[-notch,-notch,notch,notch],color=INK,lw=1)
    footprint.add_patch(Circle((row_x,0),br,fc="none",ec=BEARING,ls="--"))
    footprint.add_patch(Circle((row_x,0),bore/2,fc="none",ec=BEARING,ls="--"))
    for y in guide["mount_y_mm"]:
        footprint.add_patch(Circle((row_x,y),kwargs["m6_hole_diameter_mm"]/2,fc=PAPER,ec=INK))
    footprint.plot([row_x, row_x], [-half, half], color=MUTED, lw=.8, ls="-.")
    figure.text(.65, .765, "Frame cutout from above", fontsize=13, weight="bold", color=INK)
    lower_y, upper_y = guide["mount_y_mm"]
    note(figure=figure, x=.65, y=.355, title="Three bolts on one tangent",
         body=f"The outer bolts are {upper_y-lower_y:g} mm centre to centre.\nThey pass through solid frame on either\nside of the notch. The bolt between them\ncarries the edge bearing.")
    figure.text(.65,.093,"606   Ø6 bore × Ø17 × 6 mm\nWasher   M6 × Ø14 × 1.5 mm",fontsize=10.5,linespacing=1.5,color=MUTED)
    return figure


def save_drawing(**kwargs):
    path = kwargs["path"]
    figure = kwargs["figure"]
    svg_metadata = {
        "Date": None,
    }
    figure.savefig(path.with_suffix(".svg"), metadata=svg_metadata, facecolor=PAPER)
    figure.savefig(path.with_suffix(".png"), dpi=155, facecolor=PAPER)
    plt.close(figure)


def main(**kwargs):
    from working_oomp_populate import catalogue_records
    project = Path(__file__).resolve().parent
    matplotlib.rcParams["svg.hashsalt"] = "oobb-turret"
    comparison = []
    for path in catalogue_records(**kwargs):
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        geometry = record["oobb_details"]
        recipe = record["svg_details"]["svg_name"]
        if recipe == "offset_housing_review":
            from turret_offset_review import get_offset_layout, draw_offset_review
            layout = get_offset_layout(pattern=get_disc_pattern(**geometry), **geometry)
            drawings = [("offset_housing", draw_offset_review)]
            size = (geometry["width"], geometry["height"], geometry["turret_diameter"])
            if geometry["housing"].get("common_clamp") and size in ((9,9,5),(11,11,7)) and geometry["depth"] == 6:
                comparison.append((geometry,layout))
        elif recipe == "turret_review":
            layout = get_layout(**geometry)
            drawings = [("turret_plan", draw_plan), ("guide_section", draw_section)]
        else:
            continue
        for name, draw in drawings:
            figure = draw(layout=layout, **geometry)
            save_drawing(path=path.parent / name, figure=figure)
    if len(comparison) == 2:
        from turret_offset_review import draw_clamp_comparison
        comparison.sort(key=lambda item: item[0]["width"])
        save_drawing(path=project / "parts" / "compact_606_clamp", figure=draw_clamp_comparison(variants=comparison))


if __name__ == "__main__":
    main()
