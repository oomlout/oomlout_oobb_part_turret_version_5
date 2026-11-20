// All parts use millimetres. Local clamp X points outward and Y follows the plate side.
$fn = 96;
eps = 0.02;
print_gap = 4;
br = bearing_od / 2;
washer_recess = (bearing_width + 2 * washer_depth - depth) / 2;
boss_height = br + washer_od / 2 + 2;
half_tread = bearing_width / 2;
nut_recess = depth + 2*boss_height + nut_height + thread_beyond_nut - joint_length;
assert(nut_recess >= nut_height && nut_recess < boss_height-washer_recess,
       "Select a vertical bolt that engages a fully recessed nut with a solid shoulder.");

module through_hole(x, y, radius, height) {
    translate([x, y, -eps]) scale([radius,radius,height+2*eps]) unit_bore();
}

module at_station(a) {
    rotate([0,0,a]) translate([face_radius,0,0]) children();
}

module housing_lands() {
    for (a=station_angles) at_station(a)
        translate([0,0,-eps]) linear_extrude(height=depth+2*eps) polygon(clamp_outline);
}

module opening_roundover() {
    r = plate_radius;
    // Both exposed lips of the circular aperture. The bearing tread stays square on the disc.
    profile = concat([[opening_radius-eps,-eps],[opening_radius+r,-eps]],
        [for (a=[0:7.5:90]) [opening_radius+r-r*sin(a),r-r*cos(a)]],
        [[opening_radius-eps,r]]);
    for (flip=[0,1]) translate([0,0,flip*depth]) scale([1,1,1-2*flip])
        rotate_extrude($fn=384) polygon(profile);
}

module frame() {
    difference() {
        union() {
            rounded_plate_blank();
            intersection() { plate_blank(); housing_lands(); }
        }
        difference() { opening_roundover(); housing_lands(); }
        translate([0,0,-eps]) linear_extrude(height=depth+2*eps) polygon(frame_opening);
        for (p=frame_holes) through_hole(p[0], p[1], p[2], depth);
        for (a=station_angles) at_station(a) {
            for (y=mount_positions) through_hole(mount_x, y, mount_hole_d/2, depth);
        }
    }
}

module disc() {
    difference() {
        cylinder(r=disc_radius,h=depth,$fn=240);
        for (p=disc_holes) through_hole(p[0],p[1],mount_hole_d/2,depth);
        for (p=disc_m3_holes)
            translate([p.x,p.y,-eps]) scale([1,1,depth+2*eps]) disc_m3_bore();
    }
}

// Upper half starts at the top surface of the frame. Mirror in Z for its lower mate.
function inward_normal(a,b) = let(v=b-a) [-v[1],v[0]] / norm(v);
function inset_vertex(loop,i,d) = let(n=len(loop), p=loop[i],
    a=inward_normal(loop[(i+n-1)%n],p), b=inward_normal(p,loop[(i+1)%n]))
    p + d*(a+b)/(1+a*b);

module clamp_body(is_lower=false) {
    n = len(clamp_outline);
    profile = is_lower ? lower_outline : clamp_outline;
    base = [for (p=clamp_outline) [p.x,p.y,0]];
    transitions = is_lower ? 8 : 0;
    // Ease the lower nut boss out of the rail, clear of the disc's working edge.
    flare = is_lower ? [for (j=[0:transitions],i=[0:n-1])
              let(t=j/transitions,k=(1-cos(180*t))/2,p=clamp_outline[i]*(1-k)+profile[i]*k)
              [p.x,p.y,3+6*t]] : [];
    divisions = 12;
    rings = [for (j=[0:divisions],i=[0:n-1])
             let(a=90*j/divisions,p=inset_vertex(profile,i,housing_radius*(1-cos(a))))
             [p.x,p.y,boss_height-housing_radius+housing_radius*sin(a)]];
    layers = 1+len(flare)/n+divisions;
    sides = [for (j=[0:layers-1],i=[0:n-1]) let(k=(i+1)%n)
             each [[j*n+i,(j+1)*n+i,(j+1)*n+k],[j*n+i,(j+1)*n+k,j*n+k]]];
    polyhedron(points=concat(base,flare,rings),faces=concat(
        [[for(i=[0:n-1]) i]], sides, [[for(i=[n-1:-1:0]) layers*n+i]]),convexity=8);
}

module captive_nut_cut(x,y) {
    translate([x,y,boss_height-nut_recess]) scale([1,1,nut_recess+eps]) lower_nut_profile();
}

module clamp_half(lower=false) {
    difference() {
        clamp_body(is_lower=lower);
        if (lower) {
            for (y=mount_positions) captive_nut_cut(mount_x,y);
            play = (slot_width-bearing_bore)/2;
            hull() for(x=[slot_ends[0]-play,slot_ends[1]+play]) captive_nut_cut(x,edge_y);
        }
        // Recess only the moving washer envelope into the plate-facing surface.
        if (washer_recess>0) hull() for (x=slot_ends)
            translate([x,edge_y,-eps])
                cylinder(r=washer_od/2+(slot_width-bearing_bore)/2+washer_pocket_clearance,h=washer_recess+eps);
        for (y=mount_positions) through_hole(mount_x,y,mount_hole_d/2,boss_height);
        hull() for (x=slot_ends) through_hole(x,edge_y,slot_width/2,boss_height);
        translate([boss_x-1,0,br]) rotate([0,90,0])
            scale([horizontal_bore/2,horizontal_bore/2,clamp_outer_x-boss_x+2]) unit_bore();
        translate([nut_start,0,br]) rotate([0,90,0]) edge_nut_pocket();
    }
}

module m6_nut() {
    difference() {
        m6_nut_blank();
        through_hole(0,0,bearing_bore/2,5);
    }
}

module edge_hardware(bearings=true,fasteners=true) {
    translate([edge_axle_x,edge_y,-half_tread]) {
        if (bearings) color("SlateGray") roller();
        if (fasteners) for (z=[-washer_depth,bearing_width])
            color("Goldenrod") translate([0,0,z]) interface_washer();
    }
}

module face_hardware(bearings=true,fasteners=true) {
    translate([-half_tread,0,depth/2+br]) rotate([0,90,0]) {
        if (bearings) color("SlateGray") roller();
        if (fasteners) {
            color("Goldenrod") translate([0,0,bearing_width]) interface_washer();
            color("Silver") rotate([180,0,0]) face_axle_bolt();
            color("Silver") translate([0,0,nut_start+half_tread])
            m6_nut();
        }
    }
}

module vertical_fastener(x,y) {
    surface = depth/2 + boss_height;
    translate([x,y,0]) {
        color("Silver") translate([0,0,surface]) m6_bolt();
        color("Silver") translate([0,0,-surface+nut_recess-nut_height]) m6_nut();
    }
}

module assembled_clamps() {
    for (a=station_angles) at_station(a) {
        color("SandyBrown") translate([0,0,depth/2]) clamp_half();
        color("SandyBrown") mirror([0,0,1]) translate([0,0,depth/2]) clamp_half(lower=true);
    }
}

module assembled_hardware(bearings=true,fasteners=true) {
    for (a=station_angles) at_station(a) {
        edge_hardware(bearings,fasteners);
        face_hardware(bearings,fasteners);
        mirror([0,0,1]) face_hardware(bearings,fasteners);
        if (fasteners) {
            for (y=mount_positions) vertical_fastener(mount_x,y);
            vertical_fastener(edge_axle_x,edge_y);
        }
    }
}

module assembled_frame() { translate([0,0,-depth/2]) frame(); }
module assembled_disc() { translate([0,0,-depth/2]) disc(); }

module assembly() {
    color("LightGray") assembled_frame();
    color("LightSeaGreen") assembled_disc();
    assembled_clamps();
    assembled_hardware();
}

// The flat outboard wall sits on the bed. This prints the radial axle bore vertically.
module upper_on_bed() {
    translate([0,-clamp_y_min,clamp_outer_x]) rotate([0,90,0]) clamp_half();
}

module lower_on_bed() {
    translate([boss_height,-clamp_y_min,clamp_outer_x]) mirror([1,0,0]) rotate([0,90,0]) clamp_half(lower=true);
}

module print_layout() {
    frame();
    disc();
    // One pair per station, in two banks outside the frame.
    for (i=[0:len(station_angles)-1]) {
        column = i % 2;
        row = floor(i/2);
        translate([frame_size[0]/2+print_gap+row*(boss_height+print_gap),
                   frame_size[1]/2-clamp_length-column*(clamp_length+print_gap),0])
            upper_on_bed();
        translate([-frame_size[0]/2+clamp_length+column*(clamp_length+print_gap),
                   frame_size[1]/2+print_gap+row*(boss_height+print_gap),0])
            rotate([0,0,90]) lower_on_bed();
    }
}

// Cut a single production station and a mating arc for a low-material fit trial.
module sample_window() {
    translate([face_radius-16.5,clamp_y_min-2,-depth])
        cube([clamp_outer_x+19.5,clamp_length+4,3*depth]);
}

module fit_sample() {
    intersection() {
        sample_window();
        rotate([0,0,-station_angles[0]]) frame();
    }
    translate([-print_gap,0,0]) intersection() {
        sample_window();
        disc();
    }
    translate([face_radius+clamp_outer_x+print_gap,clamp_y_min,0]) upper_on_bed();
    translate([face_radius+clamp_outer_x+boss_height+2*print_gap,clamp_y_min,0]) lower_on_bed();
}

// Hide the upper clamp so the edge bearing and its two washer seats are visible.
// Use the slider to inspect the complete range of a nominal 6 mm axle.
module clearance_review(slide=0) {
    play = (slot_width-bearing_bore)/2;
    x = slide < 0 ? edge_axle_x+(-slide)*(slot_ends[0]-play-edge_axle_x)
                  : edge_axle_x+slide*(slot_ends[1]+play-edge_axle_x);
    intersection() {
        translate([0,0,-depth/2]) sample_window();
        rotate([0,0,-station_angles[0]]) translate([0,0,-depth/2]) frame();
    }
    color("LightSeaGreen") intersection() {
        sample_window();
        translate([0,0,-depth/2]) disc();
    }
    translate([face_radius,0,0]) {
        color("SandyBrown") mirror([0,0,1]) translate([0,0,depth/2]) clamp_half(lower=true);
        translate([x-edge_axle_x,0,0]) edge_hardware();
        face_hardware();
        mirror([0,0,1]) face_hardware();
        // Red marks actual interference with the disc for the selected setting.
        color("red") translate([0,0,eps]) intersection() {
            translate([x,edge_y,-half_tread]) roller();
            translate([-face_radius,0,-depth/2]) disc();
        }
    }
}
