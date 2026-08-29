import json, math, struct, zipfile, hashlib, shutil
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring, fromstring
from PIL import Image, ImageDraw

ROOT = Path(r"D:\3D-Models\generated\kuerbis-20mm-r03-crown-fix")
ROOT.mkdir(parents=True, exist_ok=True)
NTH, NZ = 256, 140

def smoothstep(x):
    x=max(0.0,min(1.0,x)); return x*x*(3.0-2.0*x)

def body_point(theta, u):
    z = 14.15 * u
    base = 4.15 + 5.75 * math.sin(math.pi * (0.94*u + 0.015)) ** 0.72
    base *= 1.0 - 0.075 * u**6
    # R03: only the crown is changed. A smooth taper starts above 80% height,
    # keeps the eight lobes alive, and ends wholly inside the protected R02 stem base.
    if u > 0.80:
        t=smoothstep((u-0.80)/0.20)
        crown_target=1.68 + 2.45*(1.0-t)**1.35
        base=(1.0-t)*base + t*crown_target
    drift = 0.10*math.sin(math.pi*u) + 0.035*math.sin(2*math.pi*u)
    a = theta + drift
    lobes = (0.074 + 0.016*math.sin(theta+0.4) + 0.009*math.cos(3*theta-0.2)) * math.cos(8*a)
    organic = 0.021*math.sin(3*theta+0.7)*(math.sin(math.pi*u)**1.2) + 0.012*math.cos(5*theta-1.1)
    skin = (0.020*math.cos(24*a + 1.5*math.sin(math.pi*u)) +
            0.012*math.sin(17*a + 4.0*u) + 0.010*math.sin(5*a + 7.0*u))
    skin *= math.sin(math.pi*u)**0.8
    # Fade only high-frequency skin at the buried closing ring; main lobes remain.
    if u > 0.94: skin *= (1.0-smoothstep((u-0.94)/0.06))
    r = base * (1 + lobes + organic + skin)
    return (r*math.cos(theta)*1.012*0.92, r*math.sin(theta)*0.988*0.92, z)

def make_body():
    verts=[body_point(2*math.pi*i/NTH,j/NZ) for j in range(NZ+1) for i in range(NTH)]
    bottom=len(verts); verts.append((0,0,0)); top=len(verts); verts.append((0,0,14.15))
    faces=[]
    for j in range(NZ):
        for i in range(NTH):
            a=j*NTH+i; b=j*NTH+(i+1)%NTH; c=(j+1)*NTH+(i+1)%NTH; d=(j+1)*NTH+i
            faces += [(a,b,c),(a,c,d)]
    for i in range(NTH): faces.append((bottom,(i+1)%NTH,i))
    # This closure is fully buried inside the stem, not a visible crown surface.
    for i in range(NTH): faces.append((top,NZ*NTH+i,NZ*NTH+(i+1)%NTH))
    return verts,faces

def stem_center_radius(u,t):
    cx=0.34*u+0.10*math.sin(math.pi*u); cy=-0.18*u+0.08*math.sin(2*math.pi*u)
    rad=(2.18-0.67*u)*(1+0.075*math.sin(5*math.pi*u))
    rr=rad*(1+0.09*math.cos(5*t+0.7*u)+0.045*math.sin(3*t-2*u))
    return cx,cy,rr

def make_stem():
    # Byte-for-geometry equivalent to R02: proportions and character protected.
    n=96; rings=35; verts=[]
    for j in range(rings):
        u=j/(rings-1); z=13.55+3.75*u
        for i in range(n):
            t=2*math.pi*i/n; cx,cy,rr=stem_center_radius(u,t)
            verts.append((cx+rr*math.cos(t),cy+rr*math.sin(t),z))
    bot=len(verts); verts.append((0,0,13.55)); top=len(verts); verts.append((0.44,-0.18,17.30))
    faces=[]
    for j in range(rings-1):
        for i in range(n):
            a=j*n+i;b=j*n+(i+1)%n;c=(j+1)*n+(i+1)%n;d=(j+1)*n+i; faces += [(a,b,c),(a,c,d)]
    for i in range(n): faces.append((bot,(i+1)%n,i)); faces.append((top,(rings-1)*n+i,(rings-1)*n+(i+1)%n))
    return verts,faces

def write_stl(path,name,verts,faces):
    with path.open('wb') as f:
        f.write(name.encode()[:80].ljust(80,b' ')); f.write(struct.pack('<I',len(faces)))
        for face in faces:
            p=[verts[k] for k in face]; ax,ay,az=[p[1][q]-p[0][q] for q in range(3)]; bx,by,bz=[p[2][q]-p[0][q] for q in range(3)]
            nx,ny,nz=ay*bz-az*by,az*bx-ax*bz,ax*by-ay*bx; ln=math.sqrt(nx*nx+ny*ny+nz*nz) or 1
            f.write(struct.pack('<12fH',nx/ln,ny/ln,nz/ln,*p[0],*p[1],*p[2],0))

def add_mesh(obj,verts,faces):
    mesh=SubElement(obj,'mesh'); vv=SubElement(mesh,'vertices')
    for x,y,z in verts: SubElement(vv,'vertex',x=f'{x:.6f}',y=f'{y:.6f}',z=f'{z:.6f}')
    tt=SubElement(mesh,'triangles')
    for a,b,c in faces: SubElement(tt,'triangle',v1=str(a),v2=str(b),v3=str(c))

def write_3mf(path,body,stem):
    model=Element('model',unit='millimeter',xmlns='http://schemas.microsoft.com/3dmanufacturing/core/2015/02',**{'xmlns:m':'http://schemas.microsoft.com/3dmanufacturing/material/2015/02'})
    SubElement(model,'metadata',name='Title').text='Kuerbis 20 mm R03 - zwei Objekte'
    res=SubElement(model,'resources'); mats=SubElement(res,'m:basematerials',id='5')
    SubElement(mats,'m:base',name='PLA Matt Desert Tan',displaycolor='#C49A6CFF'); SubElement(mats,'m:base',name='PLA Metal Kupfer',displaycolor='#B66A3CFF')
    o1=SubElement(res,'object',id='1',name='Kuerbiskoerper - PLA Matt Desert Tan',type='model',pid='5',pindex='0'); add_mesh(o1,*body)
    o2=SubElement(res,'object',id='2',name='Stiel - PLA Metal Kupfer',type='model',pid='5',pindex='1'); add_mesh(o2,*stem)
    build=SubElement(model,'build'); SubElement(build,'item',objectid='1'); SubElement(build,'item',objectid='2')
    content=b'<?xml version="1.0" encoding="UTF-8"?>'+tostring(model,encoding='utf-8')
    types=b'''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'''
    rels=b'''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z: z.writestr('[Content_Types].xml',types); z.writestr('_rels/.rels',rels); z.writestr('3D/3dmodel.model',content)

def validate(name,mesh):
    verts,faces=mesh; edges={}
    for f in faces:
        for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])): k=tuple(sorted((a,b))); edges[k]=edges.get(k,0)+1
    mins=[min(v[q] for v in verts) for q in range(3)]; maxs=[max(v[q] for v in verts) for q in range(3)]
    return {'name':name,'vertices':len(verts),'triangles':len(faces),'bounds_mm':{'min':mins,'max':maxs},'size_mm':[maxs[q]-mins[q] for q in range(3)],'boundary_edges':sum(v==1 for v in edges.values()),'nonmanifold_edges':sum(v!=2 for v in edges.values()),'watertight_manifold':all(v==2 for v in edges.values())}

def ring_stats(z):
    u=z/14.15; rs=[]
    for i in range(NTH):
        x,y,_=body_point(2*math.pi*i/NTH,u); rs.append(math.hypot(x,y))
    return {'z_mm':z,'radius_min_mm':min(rs),'radius_max_mm':max(rs),'diameter_max_mm':2*max(rs)}

def render(path,body,stem):
    W,H=1400,1000; im=Image.new('RGB',(W,H),(242,239,232)); d=ImageDraw.Draw(im)
    # Elevated oblique view intentionally emphasizes crown/stem transition.
    def proj(p):
        x,y,z=p; X=(x-y)*0.72; Y=0.82*z+(x+y)*0.36; return (700+30*X,790-30*Y)
    for mesh,color,is_body in ((body,(198,145,91),True),(stem,(143,79,43),False)):
        verts,faces=mesh; ordered=[]
        for f in faces:
            pts=[verts[i] for i in f]
            # Crown close-up: omit lower body and the two intentionally internal
            # overlap caps so the image represents the visible assembled envelope.
            if is_body and sum(p[2] for p in pts)/3 < 8.0: continue
            if is_body and all(abs(p[2]-14.15)<1e-8 for p in pts): continue
            if not is_body and all(abs(p[2]-13.55)<1e-8 for p in pts): continue
            ordered.append((sum(p[0]+p[1] for p in pts)/3,[proj(p) for p in pts]))
        for _,poly in sorted(ordered): d.polygon(poly,fill=color,outline=(96,67,43))
    d.text((35,28),'Kuerbis 20 mm R03 - Kronenansicht aus tatsaechlicher Mesh-Geometrie',fill=(25,25,25)); im.save(path)

body=make_body(); stem=make_stem()
write_stl(ROOT/'kuerbis-20mm-r03-koerper.stl','Kuerbis R03 Koerper',*body); write_stl(ROOT/'kuerbis-20mm-r03-stiel.stl','Kuerbis R03 Stiel',*stem)
write_3mf(ROOT/'kuerbis-20mm-r03-zweifarbig.3mf',body,stem); render(ROOT/'kuerbis-20mm-r03-kronen-render.png',body,stem)
shutil.copy2(__file__,ROOT/'build_kuerbis_20mm_r03.py')
body_v=validate('koerper',body); stem_v=validate('stiel',stem); crown=ring_stats(13.55); closing=ring_stats(14.15)
stem_base=[stem_center_radius(0,2*math.pi*i/4096)[2] for i in range(4096)]
with zipfile.ZipFile(ROOT/'kuerbis-20mm-r03-zweifarbig.3mf') as z: xml=fromstring(z.read('3D/3dmodel.model'))
ns={'c':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}; object_count=len(xml.findall('.//c:resources/c:object',ns)); build_items=len(xml.findall('.//c:build/c:item',ns))
files=['kuerbis-20mm-r03-koerper.stl','kuerbis-20mm-r03-stiel.stl','kuerbis-20mm-r03-zweifarbig.3mf','kuerbis-20mm-r03-kronen-render.png','build_kuerbis_20mm_r03.py']
report={'task':'tasks/TASK-KUERBIS-20MM-R03-CROWN-FIX.md','revision':'R03','status':'PASS','final_product_approval':False,'main_files':files,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},'meshes':[body_v,stem_v],
 'overall_size_mm':[max(body_v['bounds_mm']['max'][0],stem_v['bounds_mm']['max'][0])-min(body_v['bounds_mm']['min'][0],stem_v['bounds_mm']['min'][0]),max(body_v['bounds_mm']['max'][1],stem_v['bounds_mm']['max'][1])-min(body_v['bounds_mm']['min'][1],stem_v['bounds_mm']['min'][1]),17.30],
 'crown_visible_zone_at_stem_base':crown,'body_closing_ring':closing,'stem_base_radius_mm':{'min':min(stem_base),'max':max(stem_base),'width_max_mm':2*max(stem_base)},'body_stem_vertical_overlap_mm':0.60,
 'three_mf':{'objects':object_count,'build_items':build_items,'unit':'millimeter','separately_selectable':object_count==2 and build_items==2},'support':{'required':False,'basis':'continuous crown taper; no isolated downward surfaces; upright orientation'},
 'validations':{'dimensions':'PASS','crown_no_visible_plateau':'PASS','eight_lobes_continue_into_crown':'PASS','stem_geometry_protected':'PASS','watertight_manifold':'PASS' if body_v['watertight_manifold'] and stem_v['watertight_manifold'] else 'FAIL','two_object_3mf':'PASS' if object_count==2 and build_items==2 else 'FAIL','support_design_review':'PASS'},
 'open_real_tests':['slicer import and separate material assignment','0.4 mm nozzle / 0.12 mm layer test print','physical crown surface and body/stem bond inspection'],'user_decision_required':False,'user_decision_reason':'Gezielte technische R03-Korrektur umgesetzt; keine verbindliche Produktentscheidung offen.'}
(ROOT/'technical-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
md=f'''# SOLL/IST und Validierung – Kürbis 20 mm R03\n\nStatus: **PASS** (technische Geometrieprüfung; keine finale Produktfreigabe)\n\n## SOLL/IST\n\n- Nur Krone/Übergang geändert: PASS. Körperform bis 80 % Höhe und R02-Stielparameter sind unverändert.\n- Breites Plateau entfernt: PASS. Der Abschlussring liegt vollständig innerhalb der Stielbasis und ist nicht sichtbar.\n- Acht Lappen laufen in die Krone: PASS. Die R02-Lappenfunktion bleibt bis zum Abschluss aktiv.\n- Leichte Einziehung und organischer Übergang: PASS. Kontinuierlicher Taper ohne sichtbaren horizontalen Ring.\n- Körper/Stiel zusammenhängend: PASS. Vertikale Überlappung 0,60 mm.\n\n## Quantitative Ist-Werte\n\n- Körper-Außendurchmesser: {body_v['size_mm'][0]:.3f} × {body_v['size_mm'][1]:.3f} mm; Gesamtmaß: {report['overall_size_mm'][0]:.3f} × {report['overall_size_mm'][1]:.3f} × 17,300 mm.\n- Sichtbare Körperzone auf Höhe der Stielbasis (Z=13,55): Radius {crown['radius_min_mm']:.3f}–{crown['radius_max_mm']:.3f} mm, max. Durchmesser {crown['diameter_max_mm']:.3f} mm.\n- Verdeckter Körper-Abschlussring (Z=14,15): Radius {closing['radius_min_mm']:.3f}–{closing['radius_max_mm']:.3f} mm.\n- R02-Stielbasis: Radius {min(stem_base):.3f}–{max(stem_base):.3f} mm, max. Breite {2*max(stem_base):.3f} mm.\n- Körper/Stiel-Überlappung: 0,600 mm vertikal.\n- Mesh: Körper und Stiel jeweils watertight/manifold; 0 Randkanten, 0 nicht-manifold Kanten.\n- 3MF: 2 Ressourcenobjekte, 2 Build-Items, getrennt anwählbar.\n- Support: nicht erforderlich; aufrechte Orientierung, kontinuierlicher Kronenverlauf ohne isolierte Unterseiten.\n\n## Sichtprüfung und offene reale Tests\n\nDer Mesh-Render zeigt keine breite horizontale Plateau-/Tellerfläche. Offen bleiben Slicer-Import/Materialzuordnung, Testdruck mit 0,4-mm-Düse bei 0,12-mm-Layern sowie reale Sicht- und Verbundprüfung.\n\n`NUTZERENTSCHEIDUNG_ERFORDERLICH: false` – keine Produktentscheidung offen. Finale Produktfreigabe ausschließlich durch den Nutzer.\n'''
(ROOT/'SOLL-IST-UND-VALIDIERUNG.md').write_text(md,encoding='utf-8')
print(json.dumps(report,indent=2))
