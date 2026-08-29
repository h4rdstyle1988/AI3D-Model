// PETG-Bettklammer R01 - parametrischer CAD-Stand, Einheiten mm
$fn = 96;
width = 20.0;
wall = 2.0;
clear_depth = 22.4; // 20.0 Profil + 2.0 Filz + 0.4 technisches Montagespiel
overall_height = 40.0;
outer_depth = clear_depth + 2*wall;
outer_radius = outer_depth/2;
inner_radius = outer_radius-wall;
bend_center_z = overall_height-outer_radius;
tooth_pitch = 1.4;
tooth_engagement = 0.6;
tooth_count = 18;
tooth_start_z = 1.2;

module cross_section() {
  difference() {
    union() {
      square([outer_depth, bend_center_z]);
      translate([outer_depth/2, bend_center_z]) circle(r=outer_radius);
    }
    union() {
      translate([wall, 0]) square([clear_depth, bend_center_z+0.01]);
      translate([outer_depth/2, bend_center_z]) circle(r=inner_radius);
      translate([-outer_depth, -outer_radius]) square([3*outer_depth, outer_radius]);
    }
  }
  // Flache Rampe in Aufschieberichtung; kurze Flanke greift gegen Abziehen.
  for (i=[0:tooth_count-1]) {
    z0 = tooth_start_z + i*tooth_pitch;
    polygon([[wall+clear_depth,z0],
             [wall+clear_depth-tooth_engagement,z0+tooth_pitch-0.25],
             [wall+clear_depth,z0+tooth_pitch]]);
  }
}

linear_extrude(height=width, convexity=10) cross_section();
