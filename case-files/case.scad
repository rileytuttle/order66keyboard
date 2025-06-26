include <BOSL2/std.scad>
include <BOSL2/screws.scad>

$fn=50;

key_spacing = 19.05;
corner_radius = 3;

pcb_thickness = 1.6;
rows=6;
cols=12;
mount_screw="M2.5";
mount_contact_diam=5.5;

pcb_size = [228.6, 123];
case_edge_thickness = 4;
case_size = [pcb_size[0]+case_edge_thickness*2, pcb_size[1]+case_edge_thickness*2, 18];

mount_hole_y_offset = 3.65;

module case()
{
    diff() {
        cuboid(case_size, teardrop=true, rounding=4, except=TOP) {
            case_pcb_gap = 0.5;
            up(0.1) position(TOP) tag("remove") cuboid([pcb_size[0]+case_pcb_gap, pcb_size[1]+case_pcb_gap, 10], anchor=TOP, rounding=3, except=[TOP,BOTTOM]);
            // standoffs not sure how tall for right now
            tag("keep") position(TOP) down(10) fwd(mount_hole_y_offset) grid_copies(n=[3, 2], spacing=[4*key_spacing, 2*key_spacing]) {
                cyl(d=mount_contact_diam, 8, anchor=BOTTOM);
            }
            // tag("remove") position(TOP) down(10) grid_copies(n=[3, 2], spacing=[4*key_spacing, 2*key_spacing]) {
            //     #screw_hole(mount_screw, l=10, thread=false, anchor=BOTTOM);
            // }
        }
    }
}

case();
