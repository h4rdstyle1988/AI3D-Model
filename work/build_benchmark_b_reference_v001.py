#!/usr/bin/env python3
"""Build the image-reference Benchmark B sink caddy in Blender 5.2."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


CANDIDATE = "benchmark-b-reference-v002-r01"
REVISION = "B-2026-08-25.1"
OUTLET_ARC = 50.0
OUTLET_DROP = 0.0
OUTLET_RUN = math.sqrt(OUTLET_ARC**2 - OUTLET_DROP**2)

P = {
    "reference_image": "ChatGPT Image 25. Aug. 2026, 16_34_44.png",
    "reference_interpretation": "main-body dimensions exclude the drain overhang",
    "main_body_width_mm": 150.0,
    "main_body_depth_mm": 100.0,
    "overall_main_body_height_mm": 130.0,
    "base_tray_height_mm": 30.0,
    "outlet_functional_centerline_arc_mm": OUTLET_ARC,
    "outlet_horizontal_projection_mm": OUTLET_RUN,
    "outlet_vertical_drop_mm": OUTLET_DROP,
    "outlet_axis": "-Y from centre of main-body front wall",
    "outlet_outer_width_mm": 50.0,
    "outlet_inner_width_exit_mm": 44.0,
    "outlet_inner_width_end_mm": 44.0,
    "outlet_top_open": True,
    "grid_strut_width_mm": 3.2,
    "grid_thickness_mm": 3.2,
    "holder_grid_pitch_mm": 10.0,
    "front_grid_slot_pitch_mm": 12.0,
    "nominal_grid_opening_mm": 6.8,
    "fdm_profile": "0.4 mm nozzle / 0.20 mm layer / PLA or PETG",
    "final_union_method": "Blender volumetric remesh at 0.4 mm; no smoothing",
    "final_decimation_ratio": 0.08,
    "holders": {
        "dish_brush": {"bounds_xy": [-70.0, -34.0, 4.0, 47.0], "top_z": 106.0, "reference_envelope_mm": [22.0, 22.0]},
        "sponge": {"bounds_xy": [-31.0, 23.0, 1.0, 49.0], "top_z": 94.0, "reference_envelope_mm": [44.0, 30.0]},
        "detergent_bottle": {"bounds_xy": [26.0, 72.0, 0.0, 49.0], "top_z": 130.0, "reference_envelope_mm": [36.0, 38.0]},
    },
}


def box(name, x0, x1, y0, y1, z0, z1):
    bpy.ops.mesh.primitive_cube_add(location=((x0+x1)/2, (y0+y1)/2, (z0+z1)/2))
    obj = bpy.context.object; obj.name = name
    obj.dimensions = (x1-x0, y1-y0, z1-z0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def beveled_box(name, x0, x1, y0, y1, z0, z1, bevel=3.0, segments=3):
    obj = box(name, x0, x1, y0, y1, z0, z1)
    mod = obj.modifiers.new("rounded", "BEVEL")
    mod.width = bevel; mod.segments = segments; mod.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)
    return obj


def boolean(base, tool, operation, name):
    mod = base.modifiers.new(name, "BOOLEAN")
    mod.operation = operation; mod.solver = "EXACT"; mod.object = tool
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool, do_unlink=True)
    return base


def rounded_shell(name, x0, x1, y0, y1, z0, z1, wall=3.2, bevel=4.0):
    outer = beveled_box(name, x0, x1, y0, y1, z0, z1, bevel=bevel, segments=4)
    inner = beveled_box(name+"_void", x0+wall, x1-wall, y0+wall, y1-wall, z0-1.0, z1+2.0, bevel=max(1.0, bevel-wall/2), segments=4)
    return boolean(outer, inner, "DIFFERENCE", name+"_hollow")


def tapered_floor(name, x0, x1, y0, y1, bottom, top0, top1):
    vertices = [(x0,y0,bottom),(x0,y1,bottom),(x0,y1,top0),(x0,y0,top0),
                (x1,y0,bottom),(x1,y1,bottom),(x1,y1,top1),(x1,y0,top1)]
    faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)]
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vertices,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj); return obj


def tapered_floor_y(name, x0, x1, y0, y1, bottom, top0, top1):
    vertices=[(x0,y0,bottom),(x1,y0,bottom),(x1,y0,top0),(x0,y0,top0),
              (x0,y1,bottom),(x1,y1,bottom),(x1,y1,top1),(x0,y1,top1)]
    faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)]
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vertices,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj); return obj


def open_u_channel_x(name):
    x_end = 75.0 + OUTLET_RUN
    x_mid = 95.0
    fraction = (x_mid-75.0)/OUTLET_RUN
    sections = [
        (73.0, 15.0, 12.0, 4.5, 7.0, 20.0),
        (75.0, 15.0, 12.0, 4.5, 7.0, 20.0),
        (x_mid, 15.0 + fraction*(12.0-15.0), 12.0 + fraction*(9.0-12.0), 7.0-fraction*OUTLET_DROP-2.5, 7.0-fraction*OUTLET_DROP, 24.0),
        (x_end, 12.0, 9.0, 0.0, 2.5, 12.0),
    ]
    cy=-30.0; vertices=[]
    for x,outer,inner,bottom,floor,top in sections:
        vertices.extend([(x,cy-outer,bottom),(x,cy+outer,bottom),(x,cy+outer,top),(x,cy+inner,top),
                         (x,cy+inner,floor),(x,cy-inner,floor),(x,cy-inner,top),(x,cy-outer,top)])
    faces=[]; ring=8
    for section in range(len(sections)-1):
        a=section*ring; b=(section+1)*ring
        for edge in range(ring):
            nxt=(edge+1)%ring; faces.append((a+edge,b+edge,b+nxt,a+nxt))
    faces.append(tuple(reversed(range(ring)))); last=(len(sections)-1)*ring
    faces.append(tuple(last+i for i in range(ring)))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vertices,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj); return obj


def open_u_channel_y(name):
    sections=[
        (-48.0,25.0,22.0,9.0,12.0,30.0),
        (-50.0,25.0,22.0,9.0,12.0,30.0),
        (-75.0,25.0,22.0,9.0,12.0,34.0),
        (-100.0,25.0,22.0,9.0,12.0,20.0),
    ]
    vertices=[]
    for y,outer,inner,bottom,floor,top in sections:
        vertices.extend([(-outer,y,bottom),(outer,y,bottom),(outer,y,top),(inner,y,top),
                         (inner,y,floor),(-inner,y,floor),(-inner,y,top),(-outer,y,top)])
    faces=[]; ring=8
    for section in range(len(sections)-1):
        a=section*ring; b=(section+1)*ring
        for edge in range(ring):
            nxt=(edge+1)%ring; faces.append((a+edge,b+edge,b+nxt,a+nxt))
    faces.append(tuple(reversed(range(ring)))); last=(len(sections)-1)*ring
    faces.append(tuple(last+i for i in range(ring)))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vertices,[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj); return obj


def add_holder_grid(pieces, name, bounds, pitch=10.0, width=3.2):
    x0,x1,y0,y1=bounds; z0,z1=28.5,31.7; half=width/2
    pieces.extend([box(name+"_grid_frame_l",x0,x0+width,y0,y1,z0,z1),box(name+"_grid_frame_r",x1-width,x1,y0,y1,z0,z1),
                   box(name+"_grid_frame_f",x0,x1,y0,y0+width,z0,z1),box(name+"_grid_frame_b",x0,x1,y1-width,y1,z0,z1)])
    x=x0+pitch
    while x<x1-width: pieces.append(box(name+f"_grid_x_{x:.1f}",x-half,x+half,y0,y1,z0,z1)); x+=pitch
    y=y0+pitch
    while y<y1-width: pieces.append(box(name+f"_grid_y_{y:.1f}",x0,x1,y-half,y+half,z0,z1)); y+=pitch
    # Four small supports connect the grid and holder to the sloped catch floor.
    for sx in (x0+2.0,x1-2.0):
        for sy in (y0+2.0,y1-2.0): pieces.append(box(name+"_support",sx-2,sx+2,sy-2,sy+2,10.0,29.2))


def line_rectangle_segment(c, x0, x1, y0, y1):
    # y=x+c intersections with a rectangle.
    points=[]
    for x in (x0,x1):
        y=x+c
        if y0<=y<=y1: points.append((x,y))
    for y in (y0,y1):
        x=y-c
        if x0<=x<=x1: points.append((x,y))
    unique=[]
    for p in points:
        if not any(math.dist(p,q)<1e-8 for q in unique): unique.append(p)
    return unique[:2] if len(unique)>=2 else None


def diagonal_bar(name, p0, p1, width, z0, z1):
    x0,y0=p0; x1,y1=p1; length=math.hypot(x1-x0,y1-y0)+1.0
    obj=box(name,-length/2,length/2,-width/2,width/2,z0,z1)
    obj.rotation_euler[2]=math.atan2(y1-y0,x1-x0); obj.location.x=(x0+x1)/2; obj.location.y=(y0+y1)/2
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); return obj


def add_front_slotted_grid(pieces):
    x0,x1,y0,y1=-69.0,69.0,-44.0,-4.0; w=3.2; z0,z1=25.0,28.2
    pieces.extend([box("front_grid_l",x0,x0+w,y0,y1,z0,z1),box("front_grid_r",x1-w,x1,y0,y1,z0,z1),
                   box("front_grid_f",x0,x1,y0,y0+w,z0,z1),box("front_grid_b",x0,x1,y1-w,y1,z0,z1)])
    c_min=y0-x1; c_max=y1-x0
    c=c_min+8.0; index=0
    while c<c_max-8.0:
        segment=line_rectangle_segment(c,x0+w/2,x1-w/2,y0+w/2,y1-w/2)
        if segment: pieces.append(diagonal_bar(f"front_grid_diag_{index:02d}",segment[0],segment[1],w,z0,z1))
        c+=12.0; index+=1
    for sx in (x0+2.0,x1-2.0):
        for sy in (y0+2.0,y1-2.0): pieces.append(box("front_grid_support",sx-2,sx+2,sy-2,sy+2,10.0,25.6))


def union_all(pieces):
    bpy.ops.object.select_all(action="DESELECT")
    for piece in pieces: piece.select_set(True)
    bpy.context.view_layer.objects.active=pieces[0]
    bpy.ops.object.join(); base=bpy.context.object; base.name=CANDIDATE
    remesh=base.modifiers.new("deterministic_volume_union","REMESH")
    remesh.mode="VOXEL"; remesh.voxel_size=0.4; remesh.use_smooth_shade=False
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    decimate=base.modifiers.new("conservative_print_decimation","DECIMATE")
    decimate.decimate_type="COLLAPSE"; decimate.ratio=0.08
    bpy.ops.object.modifier_apply(modifier=decimate.name)
    bpy.context.view_layer.objects.active=base
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0005); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode="OBJECT")
    tri=base.modifiers.new("triangulate","TRIANGULATE"); bpy.ops.object.modifier_apply(modifier=tri.name)
    return base


def build():
    bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
    pieces=[]
    # Main 150 x 100 x 30 catch tray. Floor top slopes 17 -> 12 mm toward the centred front outlet.
    pieces.append(tapered_floor_y("catch_floor",-75,75,-50,50,0,12,17))
    pieces.extend([box("tray_left",-75,-71.8,-50,50,0,30),box("tray_right",71.8,75,-50,50,0,30),
                   box("tray_back",-75,75,46.8,50,0,30),box("tray_front_left",-75,-25,-50,-46.8,0,30),
                   box("tray_front_right",25,75,-50,-46.8,0,30)])
    add_front_slotted_grid(pieces)
    for name,data in P["holders"].items():
        x0,x1,y0,y1=data["bounds_xy"]
        shell=rounded_shell(name+"_holder",x0,x1,y0,y1,28.0,data["top_z"],wall=3.2,bevel=4.0)
        if name=="sponge":
            # Two columns x four real front ventilation/drain slots.
            centers_x=[x0+15.0,x1-15.0]
            for row,z in enumerate((42.0,53.0,64.0,75.0)):
                for col,x in enumerate(centers_x):
                    cutter=beveled_box(f"sponge_slot_{row}_{col}",x-7.0,x+7.0,y0-2.0,y0+5.0,z-2.0,z+2.0,bevel=1.5,segments=3)
                    boolean(shell,cutter,"DIFFERENCE",f"slot_{row}_{col}")
        pieces.append(shell); add_holder_grid(pieces,name,(x0+2.8,x1-2.8,y0+2.8,y1-2.8))
    pieces.append(open_u_channel_y("open_hook_drain"))
    solid=union_all(pieces)
    mat=bpy.data.materials.new("charcoal"); mat.diffuse_color=(0.055,0.065,0.075,1); solid.data.materials.append(mat)
    return solid


def look_at(camera, point):
    camera.rotation_euler=(Vector(point)-camera.location).to_track_quat('-Z','Y').to_euler()


def render_views(solid, out):
    scene=bpy.context.scene; scene.render.engine='BLENDER_WORKBENCH'; scene.render.resolution_x=1000; scene.render.resolution_y=760; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'; scene.world.color=(0.92,0.92,0.92)
    scene.display.shading.light='STUDIO'; scene.display.shading.color_type='MATERIAL'; scene.display.shading.show_shadows=True
    scene.display.shading.show_cavity=True; scene.display.shading.cavity_type='WORLD'; scene.display.shading.background_type='WORLD'
    bpy.ops.object.camera_add(); cam=bpy.context.object; scene.camera=cam; cam.data.lens=55
    views={"front":((0,-400,80),(0,-10,65),'ORTHO',220),"top":((0,-25,430),(0,-25,40),'ORTHO',220),
           "right":((380,-25,80),(0,-25,65),'ORTHO',220),"perspective":((240,-350,240),(0,-20,65),'PERSP',None)}
    for name,(location,target,kind,scale) in views.items():
        cam.data.type=kind
        if scale is not None: cam.data.ortho_scale=scale
        cam.location=location; look_at(cam,target); scene.render.filepath=str(out/f"render-{name}.png"); bpy.ops.render.render(write_still=True)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--output-dir",required=True,type=Path)
    argv=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else sys.argv[1:]; args=parser.parse_args(argv)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    solid=build(); bpy.context.view_layer.objects.active=solid; bpy.ops.object.select_all(action="DESELECT"); solid.select_set(True)
    bpy.ops.wm.stl_export(filepath=str(args.output_dir/f"{CANDIDATE}.stl"),export_selected_objects=True,ascii_format=False)
    bpy.ops.export_scene.gltf(filepath=str(args.output_dir/f"{CANDIDATE}.glb"),export_format="GLB",use_selection=True,export_apply=True)
    render_views(solid,args.output_dir)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_dir/f"{CANDIDATE}.blend"))
    (args.output_dir/"design-parameters.json").write_text(json.dumps({"candidate":CANDIDATE,"requirements_revision":REVISION,"parameters":P},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"candidate":CANDIDATE,"vertices":len(solid.data.vertices),"faces":len(solid.data.polygons),"output":str(args.output_dir)}))


if __name__=="__main__": main()
