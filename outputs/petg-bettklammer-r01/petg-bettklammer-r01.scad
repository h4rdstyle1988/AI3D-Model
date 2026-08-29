// PETG-Bettklammer R01 - parametrischer CAD-Stand
// Einheiten: mm. Querschnitt wird ueber die Klammerbreite extrudiert.
$fn = 96;

width = 20.0;
wall = 2.0;
clear_width = 22.4;       // 20.0 Profil + 2.0 Filz + 0.4 Montagespiel
outer_width = clear_width + 2*wall;
overall_height = 40.0;
outer_radius = outer_width/2;
inner_radius = outer_radius-wall;
bend_center_z = overall_height-outer_radius;
tooth_pitch = 1.4;
tooth_height = 0.6;
tooth_count = 18;
tooth_start_z = 1.2;

module cross_section() {
  difference() {
    union() {
      square([outer_width, bend_center_z]);
      translate([outer_width/2, bend_center_z]) circle(r=outer_radius);
    }
    union() {
      translate([wall, 0]) square([clear_width, bend_center_z+0.01]);
      translate([outer_width/2, bend_center_z]) circle(r=inner_radius);
      translate([-outer_width, -outer_radius]) square([3*outer_width, outer_radius]);
    }
  }
  // Aufschieberichtung: von unten nach oben relativ zur Innenkontur.
  // Flache Rampe beim Aufschieben, steile Zahnflanke gegen Abziehen.
  for (i=[0:tooth_count-1]) {
    z0 = tooth_start_z + i*tooth_pitch;
    polygon([[wall+clear_width,z0],
             [wall+clear_width-tooth_height,z0+tooth_pitch-0.25],
             [wall+clear_width,z0+tooth_pitch]]);
  }
}

linear_extrude(height=width, convexity=10) cross_section();
