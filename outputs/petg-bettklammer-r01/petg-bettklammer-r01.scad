// PETG-Bettklammer R01 - parametrischer Konstruktionsstand
// Einheiten mm; X=Aufnahmetiefe, Y=Profilhoehe, Extrusion=Klammerbreite.
$fn = 48;
clip_width=20.0; overall_height=40.0; wall=2.0;
chrome_depth=20.0; felt=2.0; assembly_clearance=0.4;
inner_gap=chrome_depth+felt+assembly_clearance;
inner_radius=3.0; outer_radius=inner_radius+wall;
outer_depth=inner_gap+2*wall; arc_center_z=overall_height-outer_radius;
tooth_engagement=1.0; tooth_levels=[17.0,22.0,27.0,32.0];
tooth_root_radius=0.35; arc_segments=16;

function arc(cx,cy,r,a0,a1,n)=[for(i=[1:n])
    [cx+r*cos(a0+(a1-a0)*i/n),cy+r*sin(a0+(a1-a0)*i/n)]];
function tooth(zu)=[
    [wall+inner_gap,zu-2.0-tooth_root_radius],
    [wall+inner_gap-0.05,zu-2.0],
    [wall+inner_gap-tooth_engagement,zu-0.35],
    [wall+inner_gap-0.05,zu],
    [wall+inner_gap,zu+tooth_root_radius]
];

// Schnittfreies U-Profil, gegen den Uhrzeigersinn. Lange untere Zahnflanke
// ist Aufschieberampe; kurze obere Flanke sperrt gegen Abziehen nach oben.
profile=concat(
 [[0,0],[0,arc_center_z]],
 arc(outer_radius,arc_center_z,outer_radius,180,90,arc_segments),
 [[outer_depth-outer_radius,overall_height]],
 arc(outer_depth-outer_radius,arc_center_z,outer_radius,90,0,arc_segments),
 [[outer_depth,0],[wall+inner_gap,0]],
 [for(zu=tooth_levels) each tooth(zu)],
 [[wall+inner_gap,arc_center_z]],
 arc(outer_depth-outer_radius,arc_center_z,inner_radius,0,90,arc_segments),
 [[outer_radius,overall_height-wall]],
 arc(outer_radius,arc_center_z,inner_radius,90,180,arc_segments),
 [[wall,0]]
);
linear_extrude(height=clip_width,convexity=10) polygon(points=profile);
