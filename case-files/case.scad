include <openscad-library-manager/BOSL2/std.scad>
include <openscad-library-manager/BOSL2/screws.scad>

$fn=50;

key_spacing = 19.05;
corner_radius = 3;

pcb_thickness = 1.6;
rows=6;
cols=12;
mount_screw="M2";
mount_contact_diam=5.5;

pcb_size = [228.6, 123];
case_edge_thickness = 3;
standoff_height = 3; // should be taller than thickest component on the back side
case_bottom_thickness = 3;
case_height = case_bottom_thickness+standoff_height+pcb_thickness+10;
echo(str("case height = ", case_height));
case_pcb_gap = 1;
case_size = [pcb_size[0]+case_edge_thickness*2+case_pcb_gap*2, pcb_size[1]+case_edge_thickness*2+case_pcb_gap*2, case_height];
pcb_to_key_grid=3;

mount_hole_y_offset = 3.65;
mount_screw_head = "flat"; // ["flat", "socket"]
// mount_screw_head = "socket"; // ["flat", "socket"]

switch_1_offset = 33.1 + case_pcb_gap + case_edge_thickness;
echo(str("switch 1 offset from right side of case: ", switch_1_offset));
switch_1_width = 13;
switch_1_y_offset = 3;
switch_2_offset = 46.3;
switch_2_width = 6;
switch_1 = true;
switch_2 = false;
module case()
{
    diff() {
        cuboid(case_size, teardrop=true, rounding=4, except=TOP) {
            position(BOTTOM) tag_diff("remove", "rm", "kp") {
                up(case_bottom_thickness) cuboid([pcb_size[0]+case_pcb_gap*2, pcb_size[1]+case_pcb_gap*2, 20], anchor=BOTTOM, rounding=3, except=[TOP,BOTTOM]) {
                    position(BOTTOM) fwd(mount_hole_y_offset) grid_copies(n=[3, 2], spacing=[4*key_spacing, 2*key_spacing]) {
                        tag("rm") cyl(d=mount_contact_diam, standoff_height, anchor=BOTTOM);
                    }
                }
            }
            position(BOTTOM) fwd(mount_hole_y_offset) grid_copies(n=[3, 2], spacing=[4*key_spacing, 2*key_spacing]) {
                screw_hole(mount_screw, l=30, head=mount_screw_head, thread=false, anchor=TOP, orient=DOWN);
            }
            fudge=1;
            position(BACK+LEFT+TOP) tag("remove") right(key_spacing*1) back(fudge/2) cuboid([33.95, case_edge_thickness+fudge, case_height-(case_bottom_thickness+standoff_height+pcb_thickness)], anchor=TOP+BACK+LEFT, rounding=3, edges=[BOTTOM+LEFT, BOTTOM+RIGHT])
            for(pos=[[LEFT, 180], [RIGHT, -90]])
            {
                position(TOP+pos[0]) fillet(r=3, l=case_edge_thickness+fudge, spin=pos[1], orient=FRONT);
            }
            if (switch_1) {
            up(case_bottom_thickness+standoff_height+pcb_thickness+switch_1_y_offset) position(BACK+RIGHT+BOTTOM) tag("remove") left(switch_1_offset) back(fudge/2) cuboid([switch_1_width, case_edge_thickness+fudge, 7], anchor=BACK, rounding=3, except=[FRONT,BACK], teardrop=true);
            // for(pos=[[LEFT, 180], [RIGHT, -90]])
            // {
            //     position(TOP+pos[0]) fillet(r=3, l=case_edge_thickness+fudge, spin=pos[1], orient=FRONT);
            // }
            }
            if (switch_2) {
            position(BACK+RIGHT+TOP) tag("remove") left(switch_2_offset) back(fudge/2) cuboid([switch_2_width, case_edge_thickness+fudge, case_height-(case_bottom_thickness+standoff_height+pcb_thickness)], anchor=TOP+BACK, rounding=3, edges=[BOTTOM+LEFT, BOTTOM+RIGHT])
            for(pos=[[LEFT, 180], [RIGHT, -90]])
            {
                position(TOP+pos[0]) fillet(r=3, l=case_edge_thickness+fudge, spin=pos[1], orient=FRONT);
            }
            }
        }
    }
}

module key_grid()
{
    fwd(mount_hole_y_offset)
    fwd(key_spacing/2)
    diff()
    cuboid([key_spacing*12, key_spacing*5, 2], rounding=2, except=[TOP,BOTTOM,BACK]) {
        tag("remove") grid_copies(n=[12,5], spacing = [key_spacing, key_spacing]) cuboid([14, 14, 2.5]);
        for(pos=[[0, [BACK+LEFT, BACK+RIGHT]], [10, [BACK+LEFT]], [11, [BACK+RIGHT]]])
        {
            position(BACK+LEFT) right(key_spacing*pos[0]) cuboid([key_spacing, key_spacing, 2], anchor=FRONT+LEFT, rounding=2, edges=pos[1]) tag("remove") cuboid([14, 14, 2.5]);
        }
        back(key_spacing/2)
        grid_copies(n=[3,2], spacing=[4*key_spacing, 2*key_spacing]) {
            position(BOTTOM) cyl(d=5, l=pcb_to_key_grid, anchor=TOP);
            position(TOP) screw_hole(mount_screw, l=10, thread=false, anchor=TOP) position(TOP)
            nut_trap_inline(1, anchor=TOP, spin=0);
        }
    }
}

case();
// up(10)
// key_grid();
