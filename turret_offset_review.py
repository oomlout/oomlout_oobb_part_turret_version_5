"""Review drawing for one integrated upper/lower housing at each side of the turret."""
from math import atan2, copysign, cos, degrees, hypot, radians, sin, sqrt

from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle
from matplotlib.transforms import Affine2D
from shapely.affinity import rotate
from shapely.geometry import Point, Polygon as Footprint, box
from shapely.geometry.polygon import orient

from working_svg import ACCENT, BEARING, CLAMP, DISC, FRAME, INK, MUTED, PAPER, TRACK, WASHER
from working_svg import make_axis, make_sheet


def plate_edge_x(**kwargs):
    """Outward end of a line through the rotated plate at local coordinate y."""
    theta = kwargs["theta"]
    y = kwargs["y"]
    inset = kwargs.get("inset", 0)
    bounds = []
    for direction, offset, half_size in (
        (cos(theta), -y * sin(theta), kwargs["half_width"]),
        (sin(theta), y * cos(theta), kwargs["half_height"]),
    ):
        if abs(direction) > 1e-10:
            bounds.append((copysign(half_size - inset, direction) - offset) / direction)
    return min(bounds)


def get_common_clamp_layout(**kwargs):
    guide = kwargs["guide"]
    clamp = guide["common_clamp"]
    housing = kwargs["housing"]
    face = housing["face_axle_radius_mm"]
    radius = housing["disc_radius_mm"]
    br = guide["od_mm"] / 2
    half_tread = guide["width_mm"] / 2
    half_width = (kwargs["width"] * kwargs["pitch_mm"] - kwargs["plate_edge_reduction_mm"]) / 2
    half_height = (kwargs["height"] * kwargs["pitch_mm"] - kwargs["plate_edge_reduction_mm"]) / 2
    y_edge = clamp["edge_y_mm"]
    x_edge = sqrt((radius + br)**2 - y_edge**2)
    slot_low, slot_high = clamp["slot_x_mm"]
    bolt_play = (clamp["slot_width_mm"] - guide["bore_mm"]) / 2
    if bolt_play < 0 or not slot_low-bolt_play <= x_edge - face <= slot_high+bolt_play:
        raise ValueError("The tangent edge axle falls outside the common 606 clamp slot")

    # Local profile and both mounting holes depend only on the bearing's clamp definition.
    low, high = clamp["mount_y_mm"]
    low -= clamp["end_margin_mm"]
    high += clamp["end_margin_mm"]
    outer = clamp["outer_x_mm"]
    boss = clamp["boss_x_mm"]
    lug = clamp["slot_lug_radius_mm"]
    levels = {low, high, 0, y_edge, br+0.5}
    for step in range(181):
        levels.add(y_edge + lug * cos(radians(step)))
    local_outline = [(outer,low), (outer,high)]
    for y in sorted(levels, reverse=True):
        x = boss
        if abs(y-y_edge) <= lug:
            x = min(x, slot_low - sqrt(max(0, lug**2 - (y-y_edge)**2)))
        local_outline.append((x,y))
    corner = clamp.get("corner_radius_mm", 0)
    if corner:
        profile = Footprint(local_outline)
        profile = profile.buffer(corner).buffer(-2*corner).buffer(corner)
        local_outline = list(orient(profile.simplify(.001), sign=1).exterior.coords)[:-1]
    outline = [(face+x,y) for x,y in local_outline]
    bolts = [(face+clamp["mount_x_mm"],y) for y in clamp["mount_y_mm"]]
    angles = [(angle+housing["station_rotation_deg"]) % 360
              for side in kwargs["guide_angles_by_side"].values() for angle in side]
    stations = []
    circular_pocket = "edge_pocket_clearance_mm" in clamp
    if circular_pocket:
        pocket_x = face + (slot_low + slot_high)/2
        pocket_radius = br + (slot_high-slot_low)/2 + bolt_play + clamp["edge_pocket_clearance_mm"]
        pocket_start = pocket_x - pocket_radius
        pocket_end = pocket_x + pocket_radius
        half_pocket = pocket_radius
    else:
        pocket_start = face + clamp["pocket_x_mm"][0]
        pocket_end = face + clamp["pocket_x_mm"][1]
        half_pocket = clamp["pocket_half_width_mm"]
    pocket_margin = min(half_width,half_height)
    for angle in angles:
        theta = radians(angle)
        for x,y in outline:
            if abs(x*cos(theta)-y*sin(theta)) > half_width+1e-8 or abs(x*sin(theta)+y*cos(theta)) > half_height+1e-8:
                raise ValueError(f"The common clamp exceeds the plate at {angle:g} degrees")
        if circular_pocket:
            pocket_margin = min(pocket_margin, half_width-abs(pocket_x*cos(theta)-y_edge*sin(theta))-pocket_radius,
                                half_height-abs(pocket_x*sin(theta)+y_edge*cos(theta))-pocket_radius)
        else:
            for y in (y_edge-half_pocket, y_edge+half_pocket):
                pocket_margin = min(pocket_margin, half_width-abs(pocket_end*cos(theta)-y*sin(theta)),
                                    half_height-abs(pocket_end*sin(theta)+y*cos(theta)))
        stations.append({
            "angle": angle,
            "bolt_positions": bolts,
            "outline": outline,
            "section_end": face + outer,
        })
    bolt = housing["face_bolt"]
    tip = face - half_tread - bolt["head_height_mm"]
    roller_gap = distance_to_rectangle(x=x_edge,y=y_edge,left=face-half_tread,
                                       right=face+half_tread,bottom=-br,top=br) - br
    return {
        **kwargs["pattern"],
        "half_width": half_width,
        "half_height": half_height,
        "angles": angles,
        "axle_x": x_edge,
        "axle_y": y_edge,
        "edge_angle_deg": degrees(atan2(y_edge,x_edge)),
        "roller_gap": roller_gap,
        "boss_start": face + boss,
        "boss_end": face + outer,
        "retainer_tip": tip,
        "shaft_end": face - half_tread + bolt["length_mm"],
        "running_clearance": tip - kwargs["pattern"]["bolt_sweep"],
        "stations": stations,
        "housing_length_mm": high-low,
        "bolt_spacing_mm": clamp["mount_y_mm"][1]-clamp["mount_y_mm"][0],
        "pocket_start": pocket_start,
        "pocket_half_width": half_pocket,
        "circular_pocket": circular_pocket,
        "pocket_end": pocket_end,
        "pocket_margin": pocket_margin,
    }


def get_frame_opening(**kwargs):
    layout = kwargs["layout"]
    housing = kwargs["housing"]
    guide = kwargs["guide"]
    corner = guide["common_clamp"]["pocket_blend_radius_mm"]
    opening = Point(0,0).buffer(housing["opening_radius_mm"], quad_segs=96)
    radius = layout["pocket_half_width"]
    centre = (layout["pocket_end"]-radius, layout["axle_y"])
    edge_pocket = Point(centre).buffer(radius, quad_segs=48)
    face = housing["face_axle_radius_mm"]
    half = guide["width_mm"]/2
    relief = housing["face_relief_clearance_mm"]
    end = guide["od_mm"]/2+relief
    face_pocket = box(face-half,-end,face+half+relief,end)
    for angle in layout["angles"]:
        opening = opening.union(rotate(edge_pocket,angle,origin=(0,0)))
        opening = opening.union(rotate(face_pocket,angle,origin=(0,0)))
    # Blend the thin frame tips where the circular pockets meet the opening.
    return opening.buffer(corner).buffer(-corner).simplify(.0005)


def get_offset_layout(**kwargs):
    guide = kwargs["guide"]
    housing = kwargs["housing"]
    if housing.get("common_clamp"):
        return get_common_clamp_layout(**kwargs)
    face_bolt = housing.get("face_bolt")
    edge_inset = housing.get("clamp_bolt_edge_inset_mm")
    pattern = kwargs["pattern"]
    radius = housing["disc_radius_mm"]
    angle = radians(housing["edge_angle_deg"])
    bearing_radius = guide["od_mm"] / 2
    axle_radius = radius + bearing_radius
    axle_x = axle_radius * cos(angle)
    axle_y = axle_radius * sin(angle)
    half_tread = guide["width_mm"] / 2
    face_x = housing["face_axle_radius_mm"]
    boss_start = face_x + half_tread + guide["washer_thickness_mm"]
    boss_end = boss_start + housing["boss_thickness_mm"]
    shaft_start = face_x - half_tread
    if face_bolt:
        retainer_tip = shaft_start - face_bolt["head_height_mm"]
        shaft_end = shaft_start + face_bolt["length_mm"]
    else:
        retainer_tip = shaft_start - housing["retainer_projection_mm"]
        shaft_end = boss_end
    half_width = (kwargs["width"] * kwargs["pitch_mm"] - kwargs["plate_edge_reduction_mm"]) / 2
    half_height = (kwargs["height"] * kwargs["pitch_mm"] - kwargs["plate_edge_reduction_mm"]) / 2
    # Keep the original 606 notch dimensions and its bolt-row orientation.
    pocket_end = axle_x + guide["cutout_outer_x_mm"] - guide["bolt_row_x_mm"]
    washer_radius = guide["washer_od_mm"] / 2
    ear_radius = washer_radius + housing["material_beyond_washer_mm"]
    ear_min_x = axle_x - ear_radius
    outer_x = max(boss_end, axle_x + ear_radius)
    lower_bolt, upper_bolt = housing["clamp_bolt_offsets_mm"]
    low = lower_bolt - ear_radius
    high = upper_bolt + ear_radius

    if edge_inset is not None:
        # Keep the face roller supported even when both clamp bolts lie above it.
        face_half_width = bearing_radius + housing["material_beyond_washer_mm"]
        low = min(low, -face_half_width)
        high = max(high, face_half_width)

    rotation = housing.get("station_rotation_deg", 0)
    angles = [(a + rotation) % 360 for side in kwargs["guide_angles_by_side"].values() for a in side]
    stations = []
    pocket_margin = min(half_width, half_height)
    for station in angles:
        theta = radians(station)
        plate = {
            "theta": theta,
            "half_width": half_width,
            "half_height": half_height,
        }
        bolts = []
        for y in (lower_bolt, upper_bolt):
            x = axle_x if edge_inset is None else plate_edge_x(y=y, inset=edge_inset, **plate)
            bolts.append((x, y))

        # Include the exact frame corners when a housing crosses two plate edges.
        levels = [low + (high - low) * step / 120 for step in range(121)]
        for x in (-half_width, half_width):
            for y in (-half_height, half_height):
                corner_y = -x * sin(theta) + y * cos(theta)
                if low < corner_y < high:
                    levels.append(corner_y)
        levels = sorted(set(levels + [0.0])) if low < 0 < high else sorted(set(levels))
        if edge_inset is None:
            outline = [(outer_x, low), (outer_x, high)]
            section_end = boss_end
        else:
            outline = [(plate_edge_x(y=y, **plate), y) for y in levels]
            section_end = plate_edge_x(y=0, **plate)
        inner_limit = min(ear_min_x, *(x - ear_radius for x, y in bolts))
        for y in reversed(levels):
            x = max(inner_limit, sqrt(max(0, boss_start**2 - y**2)))
            # Maintain a complete washer seat on the edge axle as the rim moves in.
            if abs(y - axle_y) < ear_radius:
                x = min(x, axle_x - sqrt(ear_radius**2 - (y - axle_y)**2))
            outline.append((x, y))
        if face_bolt:
            for x, y in [*bolts, (axle_x, axle_y)]:
                distance = distance_to_rectangle(x=x, y=y, left=shaft_start, right=shaft_end,
                                                 bottom=-face_bolt["diameter_mm"]/2,
                                                 top=face_bolt["diameter_mm"]/2)
                if distance <= kwargs["m6_hole_diameter_mm"]/2:
                    raise ValueError(f"Vertical M6 hole crosses the face-roller screw at {station:g} degrees")
        stations.append({
            "angle": station,
            "bolt_positions": bolts,
            "outline": outline,
            "section_end": section_end,
        })
        for offset in (-guide["cutout_half_width_mm"], guide["cutout_half_width_mm"]):
            y = axle_y + offset
            x_world = pocket_end * cos(theta) - y * sin(theta)
            y_world = pocket_end * sin(theta) + y * cos(theta)
            pocket_margin = min(pocket_margin, half_width - abs(x_world), half_height - abs(y_world))
    return {
        **pattern,
        "half_width": half_width,
        "half_height": half_height,
        "angles": angles,
        "axle_x": axle_x,
        "axle_y": axle_y,
        "boss_start": boss_start,
        "boss_end": boss_end,
        "retainer_tip": retainer_tip,
        "shaft_end": shaft_end,
        "running_clearance": retainer_tip - pattern["bolt_sweep"],
        "stations": stations,
        "housing_length_mm": high - low,
        "bolt_spacing_mm": upper_bolt - lower_bolt,
        "pocket_end": pocket_end,
        "pocket_margin": pocket_margin,
    }


def distance_to_rectangle(**kwargs):
    x, y = kwargs["x"], kwargs["y"]
    dx = max(kwargs["left"] - x, 0, x - kwargs["right"])
    dy = max(kwargs["bottom"] - y, 0, y - kwargs["top"])
    return hypot(dx, dy)


def get_frame_holes(**kwargs):
    layout = kwargs["layout"]
    guide = kwargs["guide"]
    housing = kwargs["housing"]
    pitch = kwargs["pitch_mm"] / 2
    frame_clearance = kwargs.get("frame_hole_web_mm", 1)
    face_x = housing["face_axle_radius_mm"]
    bolt = housing["face_bolt"]
    face_right = face_x + guide["width_mm"]/2
    relief = housing["face_relief_clearance_mm"]
    mount_hole_radius = kwargs["m6_hole_diameter_mm"] / 2
    pocket_half_width = layout.get("pocket_half_width",guide["cutout_half_width_mm"])
    # Keep the full hole perimeter clear of the flush housing footprint.
    footprints = []
    for station in layout["stations"]:
        footprint = Footprint(station["outline"])
        footprints.append(footprint)
    holes = []
    for row in range(2*kwargs["height"]-1):
        for column in range(2*kwargs["width"]-1):
            x = (column - kwargs["width"] + 1) * pitch
            y = (row - kwargs["height"] + 1) * pitch
            hole_radius = 1.6 if row % 2 or column % 2 else mount_hole_radius
            if hypot(x,y) < housing["opening_radius_mm"] + hole_radius + frame_clearance:
                continue
            for station, footprint in zip(layout["stations"], footprints):
                theta = radians(station["angle"])
                u = x*cos(theta) + y*sin(theta)
                v = -x*sin(theta) + y*cos(theta)
                if footprint.distance(Point(u,v)) < hole_radius + frame_clearance:
                    break
                pocket = distance_to_rectangle(x=u,y=v,left=layout.get("pocket_start",layout["axle_x"]+guide["cutout_inner_x_mm"]-guide["bolt_row_x_mm"]),
                    right=layout["pocket_end"],bottom=layout["axle_y"]-pocket_half_width,
                    top=layout["axle_y"]+pocket_half_width)
                if layout.get("circular_pocket"):
                    pocket = hypot(u-(layout["pocket_end"]-pocket_half_width),v-layout["axle_y"])-pocket_half_width
                face_pocket = distance_to_rectangle(x=u,y=v,left=face_x-guide["width_mm"]/2,
                    right=face_right+relief,bottom=-guide["od_mm"]/2-relief,top=guide["od_mm"]/2+relief)
                if min(face_pocket,pocket) < hole_radius + frame_clearance:
                    break
                if any(hypot(u-bx,v-by) < mount_hole_radius+hole_radius+frame_clearance
                       for bx,by in station["bolt_positions"]):
                    break
                # The horizontal shank can project beyond the housing silhouette.
                shank = distance_to_rectangle(x=u,y=v,left=face_x-guide["width_mm"]/2,
                    right=layout["shaft_end"],bottom=-bolt["diameter_mm"]/2,top=bolt["diameter_mm"]/2)
                if shank <= hole_radius:
                    break
            else:
                holes.append((x,y,hole_radius))
    return holes


def draw_offset_review(**kwargs):
    supplied_plan = kwargs.get("plan_axis")
    guide = kwargs["guide"]
    housing = kwargs["housing"]
    layout = kwargs["layout"]
    radius = housing["disc_radius_mm"]
    opening = housing["opening_radius_mm"]
    angle = layout["edge_angle_deg"] if housing.get("common_clamp") else housing["edge_angle_deg"]
    edge_x = layout["axle_x"]
    edge_y = layout["axle_y"]
    face = housing["face_axle_radius_mm"]
    br = guide["od_mm"] / 2
    tread = guide["width_mm"]
    wr = guide["washer_od_mm"] / 2
    wt = guide["washer_thickness_mm"]
    hole = kwargs["m6_hole_diameter_mm"] / 2
    bore = guide["bore_mm"] / 2
    pocket = layout["pocket_end"]
    notch = layout.get("pocket_half_width",guide["cutout_half_width_mm"])
    width = layout["half_width"]
    height = layout["half_height"]
    face_left = face - tread / 2
    face_right = face + tread / 2
    boss = layout["boss_start"]
    end = layout["stations"][0]["section_end"]
    shaft_end = layout["shaft_end"]
    face_bolt = housing.get("face_bolt")
    head_radius = face_bolt["head_diameter_mm"]/2 if face_bolt else bore+1
    relief = housing.get("face_relief_clearance_mm", 0)
    tip = layout["retainer_tip"]
    if supplied_plan is None:
        figure = make_sheet(
            title=f'Turret housings with {housing["face_contact_mm"]:g} mm of tread on the disc' if face_bolt else f"One housing per side, edge roller at {angle:g}°",
            subtitle=(f'{kwargs["width"]} × {kwargs["height"]} OOBB plate     /     Ø{2*layout["usable_radius"]:g} mm usable circle'
                      f'     /     Ø{2*radius:g} mm disc     /     Edge roller {angle:.1f}° from each housing axis'),
        )
        plan = make_axis(figure=figure, bounds=[.03,.16,.47,.62])
    else:
        plan = supplied_plan
        figure = plan.figure
    plan.set_xlim(-width-3,width+3)
    plan.set_ylim(-height-3,height+3)
    plan.add_patch(Rectangle((-width,-height),2*width,2*height,fc=FRAME,ec=INK))
    if layout.get("circular_pocket"):
        plan.add_patch(Polygon(get_frame_opening(**kwargs).exterior.coords,fc=PAPER,ec=MUTED))
    else:
        plan.add_patch(Circle((0,0),opening,fc=PAPER,ec=MUTED))
    if face_bolt:
        for x,y,grid_radius in get_frame_holes(**kwargs):
            plan.add_patch(Circle((x,y),grid_radius,fc=PAPER,ec=MUTED,lw=.65))
    plan.add_patch(Circle((0,0),radius,fc=TRACK,ec=INK))
    plan.add_patch(Circle((0,0),layout["usable_radius"],fc=DISC,ec=MUTED,lw=.8))
    plan.add_patch(Circle((0,0),layout["bolt_sweep"],fill=False,ec=ACCENT,ls="--"))
    for x,y in layout["holes"]:
        plan.add_patch(Circle((x,y),hole,fc=PAPER,ec=INK,lw=.65))
    for station in layout["stations"]:
        tr = Affine2D().rotate_deg(station["angle"]) + plan.transData
        if not layout.get("circular_pocket"):
            cutout = [(pocket,edge_y-notch), (pocket,edge_y+notch)]
            pocket_start = layout.get("pocket_start",edge_x + guide["cutout_inner_x_mm"] - guide["bolt_row_x_mm"])
            for step in range(41):
                y = edge_y + notch - 2*notch*step/40
                x = max(pocket_start, sqrt(max(0, opening**2-y**2)))
                cutout.append((x,y))
            plan.add_patch(Polygon(cutout,transform=tr,fc=PAPER,ec=MUTED,lw=.65))
        if face_bolt and not layout.get("circular_pocket"):
            half_relief = br+relief
            cut = [(face_right+relief,-half_relief),(face_right+relief,half_relief)]
            for step in range(41):
                y = half_relief - 2*half_relief*step/40
                cut.append((sqrt(opening**2-y**2),y))
            plan.add_patch(Polygon(cut,transform=tr,fc=PAPER,ec=MUTED,lw=.65))
        plan.add_patch(Polygon(station["outline"],transform=tr,fc=CLAMP,ec=INK,alpha=.55,lw=.9))
        bolts = station["bolt_positions"]
        plan.plot(*zip(*bolts), transform=tr,
                  color=MUTED,lw=.7,ls="-.")
        for centre in bolts:
            plan.add_patch(Circle(centre,hole,transform=tr,fc=PAPER,ec=INK,lw=.65))
        # Edge bearing shown through the upper clamp to locate the contact.
        plan.add_patch(Circle((edge_x,edge_y),br,transform=tr,fc=BEARING,ec=INK))
        plan.add_patch(Circle((edge_x,edge_y),bore,transform=tr,fc=PAPER,ec=INK,lw=.65))
        plan.add_patch(Rectangle((face_left,-br),tread,2*br,transform=tr,fc=BEARING,ec=INK,lw=.8))
        plan.add_patch(Rectangle((face_right,-wr),wt,2*wr,transform=tr,fc=WASHER,ec=INK,lw=.65))
        if face_bolt:
            plan.add_patch(Rectangle((face_left,-bore),shaft_end-face_left,2*bore,transform=tr,
                                     fc="#c8d0d4",ec=INK,lw=.9))
            plan.add_patch(Rectangle((tip,-head_radius),face_left-tip,2*head_radius,transform=tr,
                                     fc="#c8d0d4",ec=INK,lw=.9))
        else:
            plan.plot([tip,min(layout["boss_end"],station["section_end"])],[0,0],transform=tr,color=INK,lw=.75,ls="-.")
    if supplied_plan is not None:
        return figure
    figure.text(.05,.117,f'{layout["housing_length_mm"]:g} mm housing   ·   Clamp bolts {layout["bolt_spacing_mm"]:g} mm centre to centre',
                color=INK,size=11,weight="bold")
    inset = housing.get("clamp_bolt_edge_inset_mm")
    if inset is not None:
        lower, upper = housing["clamp_bolt_offsets_mm"]
        caption = (f'Bolt centres sit {inset:g} mm in from the finished edge,\n'
                   f'{lower:+g} and {upper:+g} mm across the housing from the face roller.')
    elif housing.get("common_clamp"):
        caption = (f'Edge axle offset along the clamp is {edge_y:g} mm.\n'
                   f'Edge-to-face roller clearance in plan is {layout["roller_gap"]:.2f} mm.')
    else:
        caption = f'Ø{2*opening:g} mm opening gives {opening-radius:g} mm radial clearance around the disc.'
    figure.text(.05,.080,caption,color=MUTED,size=9.5,va="top")

    figure.text(.54,.766,"Section through the two face rollers",weight="bold",size=14,color=INK)
    section = make_axis(figure=figure,bounds=[.535,.305,.415,.41])
    section_edge = plate_edge_x(theta=radians(layout["stations"][0]["angle"]),
                                half_width=width, half_height=height, y=0)
    section.set_xlim(layout["bolt_sweep"]-11,section_edge+2)
    hd = kwargs["depth"]/2
    roller_z = hd + br
    section.set_ylim(-roller_z-br-2,roller_z+br+2)
    start = section.get_xlim()[0]
    def block(**values):
        section.add_patch(Rectangle((values["x"],values["z"]),values["w"],values["h"],
                                    ec=INK,fc=values["color"],lw=.85))
    block(x=start,z=-hd,w=radius-start,h=2*hd,color=DISC)
    frame_start = max(opening,face_right+relief) if face_bolt else opening
    block(x=frame_start,z=-hd,w=section_edge-frame_start,h=2*hd,color=FRAME)
    for sign in (1,-1):
        boss_height = br + wr + 2
        seat_z = hd
        block(x=boss,z=min(sign*seat_z,sign*(hd+boss_height)),w=end-boss,h=hd+boss_height-seat_z,color=CLAMP)
        if housing.get("common_clamp"):
            nut_x = face+guide["common_clamp"]["nut_pocket_start_mm"]
            block(x=nut_x,z=sign*roller_z-5.92,w=end-nut_x,h=11.84,color=PAPER)
            block(x=nut_x,z=sign*roller_z-5.77,w=5,h=11.54,color=BEARING)
        block(x=face_left,z=sign*roller_z-br,w=tread,h=2*br,color=BEARING)
        block(x=face_right,z=sign*roller_z-wr,w=wt,h=2*wr,color=WASHER)
        # The shaft and retaining end are envelopes for fastener selection.
        block(x=tip,z=sign*roller_z-bore,w=shaft_end-tip,h=2*bore,color="#c8d0d4")
        block(x=tip,z=sign*roller_z-head_radius,w=face_left-tip,h=2*head_radius,color="#c8d0d4")
    section.axvline(layout["bolt_sweep"],color=ACCENT,ls="--",lw=1)
    section.text(start+1,0,"DISC",size=8,color=INK,va="center")
    if face_bolt:
        section.plot([face_left,radius],[hd,hd],color=ACCENT,lw=2.4,solid_capstyle="butt")
        section.plot([face_left,radius],[-hd,-hd],color=ACCENT,lw=2.4,solid_capstyle="butt")
    section.text(layout["bolt_sweep"]-.6,roller_z+2,"Bolt\nsweep",ha="right",va="center",size=8,color=ACCENT)
    if face_bolt:
        figure.text(.54,.239,f'M6 × {face_bolt["length_mm"]:g} face-roller bolt',size=13,weight="bold",color=INK)
        figure.text(.54,.195,"The M6 hex nut loads from the outside edge of each housing.\nBoth housing halves seat directly on the frame.",size=10.5,color=INK,va="top")
        figure.text(.54,.099,f'10 mm AF hex head   ·   {layout["running_clearance"]:.2f} mm to the rotating hex-head envelope',size=9.5,color=MUTED,va="top")
    else:
        figure.text(.54,.239,f'{end-boss:g} mm outboard support',size=13,weight="bold",color=INK)
    return figure


def draw_clamp_comparison(**kwargs):
    variants = kwargs["variants"]
    figure = make_sheet(
        title="One compact 606 clamp on two plate sizes",
        subtitle="Four side stations per plate   /   Plans at the same scale   /   3 mm tread contact on both disc faces",
    )
    limit = max(layout["half_width"] for geometry,layout in variants) + 3
    for (geometry,layout),left in zip(variants,(.024,.345)):
        axis = make_axis(figure=figure,bounds=[left,.18,.312,.54])
        draw_offset_review(plan_axis=axis,layout=layout,**geometry)
        axis.set_xlim(-limit,limit)
        axis.set_ylim(-limit,limit)
        centre = left + .156
        figure.text(centre,.755,f'{geometry["width"]} × {geometry["height"]}   /   Ø{geometry["turret_diameter"]} OOBB',
                    ha="center",fontsize=15,weight="bold",color=INK)
        figure.text(centre,.135,f'{layout["roller_gap"]:.2f} mm between rollers in plan',ha="center",fontsize=10,color=INK)
        figure.text(centre,.091,f'Ø{2*geometry["housing"]["disc_radius_mm"]:g} mm disc',ha="center",fontsize=10,color=MUTED)

    geometry, layout = variants[0]
    clamp = geometry["guide"]["common_clamp"]
    face = geometry["housing"]["face_axle_radius_mm"]
    figure.text(.685,.755,"Shared clamp half",fontsize=15,weight="bold",color=INK)
    detail = make_axis(figure=figure,bounds=[.68,.21,.295,.51])
    detail.set_xlim(-7,62)
    detail.set_ylim(-27,49)
    vertices = [(x-face,y) for x,y in layout["stations"][0]["outline"]]
    detail.add_patch(Polygon(vertices,fc=CLAMP,ec=INK))
    for y in clamp["mount_y_mm"]:
        detail.add_patch(Circle((clamp["mount_x_mm"],y),geometry["m6_hole_diameter_mm"]/2,fc=PAPER,ec=INK))
    low, high = clamp["slot_x_mm"]
    r = clamp["slot_width_mm"]/2
    y = clamp["edge_y_mm"]
    detail.add_patch(FancyBboxPatch((low-r,y-r),high-low+2*r,2*r,
                                    boxstyle=f"round,pad=0,rounding_size={r}",fc=PAPER,ec=INK))
    detail.plot([high+r,25],[y,y],color=MUTED,lw=.8)
    detail.text(26,y,"Edge-axle slot",va="center",size=9.5,color=INK)
    detail.plot([4.5,17],[-3,-3],ls="--",lw=.8,color=INK)
    detail.plot([4.5,17],[3,3],ls="--",lw=.8,color=INK)
    detail.plot([17,25],[0,0],color=MUTED,lw=.8)
    detail.text(26,0,"Face axle",va="center",size=9.5,color=INK)
    figure.text(.685,.135,f'{layout["housing_length_mm"]:g} mm long   ·   {layout["bolt_spacing_mm"]:g} mm fixing centres',size=10,color=INK)
    travel = high-low+clamp["slot_width_mm"]-geometry["guide"]["bore_mm"]
    figure.text(.685,.091,f'{travel:g} mm of travel with a 6 mm axle',size=10,color=MUTED)
    return figure
