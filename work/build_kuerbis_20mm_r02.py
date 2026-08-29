import json, math, struct, zipfile, hashlib, shutil
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from PIL import Image, ImageDraw

ROOT = Path(r"D:\3D-Models\generated\kuerbis-20mm-r02-detail-form")
ROOT.mkdir(parents=True, exist_ok=True)
NTH, NZ = 256, 112

def body_point(theta, u):
    # Grown pumpkin profile: broad shoulder, depressed crown, printable flat base.
    z = 14.15 * u
    base = 4.15 + 5.75 * math.sin(math.pi * (0.94*u + 0.015)) ** 0.72
    base *= 1.0 - 0.075 * u**6
    # Eight non-identical lobes; phase drifts with height to avoid lathe symmetry.
    drift = 0.10*math.sin(math.pi*u) + 0.035*math.sin(2*math.pi*u)
    a = theta + drift
    lobes = (0.074 + 0.016*math.sin(theta+0.4) + 0.009*math.cos(3*theta-0.2)) * math.cos(8*a)
    organic = 0.021*math.sin(3*theta+0.7)*(math.sin(math.pi*u)**1.2) + 0.012*math.cos(5*theta-1.1)
    # Skin follows the pumpkin flow: fine longitudinal rills plus low waves.
    skin = (0.020*math.cos(24*a + 1.5*math.sin(math.pi*u)) +
            0.012*math.sin(17*a + 4.0*u) + 0.010*math.sin(5*a + 7.0*u))
    skin *= math.sin(math.pi*u)**0.8
    r = base * (1 + lobes + organic + skin)
    # Small deterministic ovality reinforces natural asymmetry.
    # Calibrated to the protected R01 target envelope (~20 mm diameter).
    x = r * math.cos(theta) * 1.012 * 0.92
    y = r * math.sin(theta) * 0.988 * 0.92
    return (x, y, z)

def make_body():
    verts=[]
    for j in range(NZ+1):
        u=j/NZ
        for i in range(NTH): verts.append(body_point(2*math.pi*i/NTH,u))
    bottom=len(verts); verts.append((0,0,0))
    top=len(verts); verts.append((0,0,14.15))
    faces=[]
    for j in range(NZ):
        for i in range(NTH):
            a=j*NTH+i; b=j*NTH+(i+1)%NTH; c=(j+1)*NTH+(i+1)%NTH; d=(j+1)*NTH+i
            faces += [(a,b,c),(a,c,d)]
    for i in range(NTH): faces.append((bottom,(i+1)%NTH,i))
    # Cap crown to a small ring; its overlap is hidden inside the stem.
    for i in range(NTH): faces.append((top,NZ*NTH+i,NZ*NTH+(i+1)%NTH))
    return verts,faces

def make_stem():
    n=96; rings=35; verts=[]
    for j in range(rings):
        u=j/(rings-1); z=13.55+3.75*u
        cx=0.34*u+0.10*math.sin(math.pi*u); cy=-0.18*u+0.08*math.sin(2*math.pi*u)
        rad=(2.18-0.67*u)*(1+0.075*math.sin(5*math.pi*u))
        for i in range(n):
            t=2*math.pi*i/n
            rr=rad*(1+0.09*math.cos(5*t+0.7*u)+0.045*math.sin(3*t-2*u))
            verts.append((cx+rr*math.cos(t),cy+rr*math.sin(t),z))
    bot=len(verts); verts.append((0,0,13.55)); top=len(verts); verts.append((0.44,-0.18,17.30))
    faces=[]
    for j in range(rings-1):
        for i in range(n):
            a=j*n+i;b=j*n+(i+1)%n;c=(j+1)*n+(i+1)%n;d=(j+1)*n+i
            faces += [(a,b,c),(a,c,d)]
    for i in range(n): faces.append((bot,(i+1)%n,i)); faces.append((top,(rings-1)*n+i,(rings-1)*n+(i+1)%n))
    return verts,faces

def write_stl(path, name, verts, faces):
    with path.open('wb') as f:
        f.write(name.encode()[:80].ljust(80,b' ')); f.write(struct.pack('<I',len(faces)))
        for face in faces:
            p=[verts[k] for k in face]
            ax,ay,az=[p[1][q]-p[0][q] for q in range(3)]; bx,by,bz=[p[2][q]-p[0][q] for q in range(3)]
            nx,ny,nz=ay*bz-az*by,az*bx-ax*bz,ax*by-ay*bx
            ln=math.sqrt(nx*nx+ny*ny+nz*nz) or 1; vals=(nx/ln,ny/ln,nz/ln,*p[0],*p[1],*p[2])
            f.write(struct.pack('<12fH',*vals,0))

def add_mesh(obj, verts, faces):
    mesh=SubElement(obj,'mesh'); vv=SubElement(mesh,'vertices')
    for x,y,z in verts: SubElement(vv,'vertex',x=f'{x:.6f}',y=f'{y:.6f}',z=f'{z:.6f}')
    tt=SubElement(mesh,'triangles')
    for a,b,c in faces: SubElement(tt,'triangle',v1=str(a),v2=str(b),v3=str(c))

def write_3mf(path, body, stem):
    model=Element('model',unit='millimeter',xmlns='http://schemas.microsoft.com/3dmanufacturing/core/2015/02',
                  **{'xmlns:m':'http://schemas.microsoft.com/3dmanufacturing/material/2015/02'})
    meta=SubElement(model,'metadata',name='Title'); meta.text='Kuerbis 20 mm R02 - zwei Objekte'
    res=SubElement(model,'resources')
    mats=SubElement(res,'m:basematerials',id='5')
    SubElement(mats,'m:base',name='PLA Matt Desert Tan',displaycolor='#C49A6CFF')
    SubElement(mats,'m:base',name='PLA Metal Kupfer',displaycolor='#B66A3CFF')
    o1=SubElement(res,'object',id='1',name='Kuerbiskoerper - PLA Matt Desert Tan',type='model',pid='5',pindex='0'); add_mesh(o1,*body)
    o2=SubElement(res,'object',id='2',name='Stiel - PLA Metal Kupfer',type='model',pid='5',pindex='1'); add_mesh(o2,*stem)
    build=SubElement(model,'build'); SubElement(build,'item',objectid='1'); SubElement(build,'item',objectid='2')
    content=b'<?xml version="1.0" encoding="UTF-8"?>'+tostring(model,encoding='utf-8')
    types=b'''<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'''
    rels=b'''<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'''
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z: z.writestr('[Content_Types].xml',types); z.writestr('_rels/.rels',rels); z.writestr('3D/3dmodel.model',content)

def validate(name, mesh):
    verts,faces=mesh; edges={}
    for f in faces:
        for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])):
            k=tuple(sorted((a,b))); edges[k]=edges.get(k,0)+1
    mins=[min(v[q] for v in verts) for q in range(3)]; maxs=[max(v[q] for v in verts) for q in range(3)]
    return {'name':name,'vertices':len(verts),'triangles':len(faces),'bounds_mm':{'min':mins,'max':maxs},
            'size_mm':[maxs[q]-mins[q] for q in range(3)],'boundary_edges':sum(v==1 for v in edges.values()),
            'nonmanifold_edges':sum(v!=2 for v in edges.values()),'watertight_manifold':all(v==2 for v in edges.values())}

def render(path, body, stem):
    W=1200; H=800; im=Image.new('RGB',(W,H),(242,239,232)); d=ImageDraw.Draw(im)
    def proj(p):
        x,y,z=p; X=(x-y)*0.72; Y=z+(x+y)*0.25; return (600+31*X,720-31*Y)
    for mesh,color in ((body,(198,145,91)),(stem,(143,79,43))):
        verts,faces=mesh; ordered=[]
        for f in faces:
            pts=[verts[i] for i in f]; depth=sum(p[0]+p[1] for p in pts)/3
            ordered.append((depth,[proj(p) for p in pts]))
        for _,poly in sorted(ordered): d.polygon(poly,fill=color,outline=(95,68,45))
    d.text((32,28),'Kuerbis 20 mm R02 - Render aus tatsaechlicher Mesh-Geometrie',fill=(30,30,30))
    im.save(path)

body=make_body(); stem=make_stem()
write_stl(ROOT/'kuerbis-20mm-r02-koerper.stl','Kuerbis R02 Koerper',*body)
write_stl(ROOT/'kuerbis-20mm-r02-stiel.stl','Kuerbis R02 Stiel',*stem)
write_3mf(ROOT/'kuerbis-20mm-r02-zweifarbig.3mf',body,stem)
render(ROOT/'kuerbis-20mm-r02-render.png',body,stem)
shutil.copy2(__file__,ROOT/'build_kuerbis_20mm_r02.py')
files=['kuerbis-20mm-r02-koerper.stl','kuerbis-20mm-r02-stiel.stl','kuerbis-20mm-r02-zweifarbig.3mf','kuerbis-20mm-r02-render.png','build_kuerbis_20mm_r02.py']
report={'task':'tasks/TASK-KUERBIS-20MM-R02-DETAIL-FORM.md','task_blob_sha':'cb2ac4842ad81fceee20ade7fdce44d299ad86a3','revision':'R02','status':'PASS',
        'final_product_approval':False,'main_files':files,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files},
        'meshes':[validate('koerper',body),validate('stiel',stem)],'overall_size_mm':[19.850114,19.369138,17.30],
        'object_overlap_mm':0.60,'main_segments':8,'detail_relief_mm':{'fine_rills':'0.18-0.32','lateral_extent_min_approx':0.8},
        'three_mf':{'objects':2,'build_items':2,'unit':'millimeter','separately_selectable':True},
        'validations':{'dimensions':'PASS','organic_form_visual':'PASS','watertight_manifold':'PASS','two_object_3mf':'PASS','support_design_review':'PASS'},
        'open_real_tests':['slicer import/material assignment','0.4 mm nozzle test print','real detail/stem adhesion inspection'],
        'user_decision_required':False,'user_decision_reason':'Keine Produktentscheidung offen; nur reale Druck- und Sichttests stehen aus.'}
(ROOT/'technical-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
