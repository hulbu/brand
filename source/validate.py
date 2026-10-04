#!/usr/bin/env python3
"""Validate shipped assets against the brief and preserved studio geometry."""
from pathlib import Path
from html.parser import HTMLParser
from PIL import Image, ImageChops
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
import build

ROOT=build.ROOT
CFG=build.CFG
manifest=json.loads((ROOT/'source/asset-manifest.json').read_text())
assets=manifest['assets']
checks=[]

def check(ok,message):
    if not ok: raise AssertionError(message)
    checks.append(message)

def near(a,b): return abs(a-b)<1e-8

check(CFG['geometry']=={'radius':150,'centers':[435,540,645],'y':540,'gaps':{'standard':22,'32':32,'16':44}},'Founder geometry is unchanged')
expected=[]
for v in ('','-coral','-ink','-white'):
    for cut in ('','-16','-32'):
        stem='hulbu-mark'+v+cut
        expected.append('logo/'+stem+'.svg')
        for w in (512,1024,2048): expected.append(f'logo/png/{stem}-{w}.png')
for n in ('favicon.svg','favicon-auto.svg','favicon.ico','favicon-16.png','favicon-32.png','favicon-48.png','apple-touch-icon.png','android-chrome-192.png','android-chrome-512.png','maskable-512.png','site.webmanifest','head.html'):
    expected.append('favicon/'+n)
for variant in build.PROFILES:
    for platform,size in CFG['profiles'].items(): expected.append(f'social/profile/{variant}/{platform}-{size}.png')
for spec in build.COVERS:
    for suffix in ('-background', '' if spec['id'].startswith('og-') else '-with-logo'):
        expected.append(f'social/covers/{spec["id"]}{suffix}.png')
expected += ['colors/tokens.json','colors/tokens.css','colors/tokens.ts','colors/swatches.png','README.md','LICENSE','preview.html','PLATFORM-NOTES.md']
for p in expected: check((ROOT/p).is_file(),f'Required file: {p}')
check(len({a['path'] for a in assets})==len(assets),'No duplicate inventory entries')

for a in assets:
    p=ROOT/a['path']; check(p.exists(),f'Inventory exists: {a["path"]}')
    if p.suffix=='.svg':
        e=ET.fromstring(p.read_text()); tags={n.tag.split('}')[-1] for n in e.iter()}
        check(tags<=({'svg','path','title','style'} if p.name=='favicon-auto.svg' else {'svg','path','title'}),f'Path-only SVG: {p.name}')
        check(all(re.fullmatch(r'-?\d+',v) for v in e.attrib['viewBox'].split()),f'Integer viewBox: {p.name}')
        check(bool(e.find('{*}title').text),f'Titled SVG: {p.name}')
        paths=e.findall('{*}path')
        check(len(paths)==3,f'Three exact components: {p.name}')
        check(all('stroke' not in n.attrib and 'transform' not in n.attrib for n in paths),f'No stroke or transform: {p.name}')
    if p.suffix=='.png':
        im=Image.open(p); im.load()
        check(im.size==(a['width'],a['height']),f'PNG size: {p.name}')
        check(im.info.get('srgb')==0,f'sRGB metadata: {p.name}')
        if a['kind']=='logo':
            alpha=im.convert('RGBA').getchannel('A')
            check(alpha.getextrema()==(0,255),f'Transparent logo: {p.name}')
            # At centre y, the first negative gap ends at the next disk left edge.
            gap=a['gap']; px=round((105-gap/2)/510*im.width)
            check(alpha.getpixel((px,im.height//2))==0,f'Real gap negative space: {p.name}')
            check(im.size[1]==round(im.size[0]*300/510),f'Correct logo aspect ratio: {p.name}')
        if a['kind']=='profile':
            bg=build.COL[build.PROFILES[a['variant']][1]]
            check(im.convert('RGBA').getchannel('A').getextrema()==(255,255),f'Opaque profile: {p.name}')
            rgbim=im.convert('RGB'); bgim=Image.new('RGB',im.size,bg)
            box=ImageChops.difference(rgbim,bgim).getbbox()
            check(box is not None,f'Profile has mark: {p.name}')
            n=im.width
            check(all(math.hypot(x-n/2,y-n/2)<n*.42 for x in (box[0],box[2]) for y in (box[1],box[3])),f'Circular crop margin: {p.name}')
            # All non-background pixels must live in the expected mark rectangle.
            check(box[0]>=n*.16-1 and box[2]<=n*.84+1 and box[1]>=n*.30-1 and box[3]<=n*.70+1,f'No external frame: {p.name}')

# Independently interpret the original mask construction as point membership.
# Ignore only pixels within 1.5 raster pixels of ANY boundary (anti-alias band).
geometry_stats=[]
for ref,gap in [('src.svg',22),('src-32.svg',32),('src-16.svg',44)]:
    root=ET.parse(ROOT/'source/favicon-from-studio'/ref).getroot()
    circles=root.findall('{*}circle'); masks={e.attrib['id']:e for e in root.findall('.//{*}mask')}
    view=tuple(map(float,root.attrib['viewBox'].split()))
    size=520; scale=view[2]/size
    actual=build.raster(build.svg(build.mark_paths(gap),view,'Comparison'),size,size)
    shapes=[]
    for index,el in enumerate(circles):
        mask=masks[el.attrib['mask'][5:-1]]
        cutters=[tuple(float(c.attrib[k]) for k in ('cx','cy','r')) for c in mask.findall('{*}circle')]
        shapes.append((tuple(float(el.attrib[k]) for k in ('cx','cy','r')),cutters,build.rgb(build.COL[('yellow','teal','primary')[index]])))
    count=0; errors=0
    for y in range(size):
        yy=view[1]+(y+.5)*scale
        for x in range(size):
            xx=view[0]+(x+.5)*scale; expected_pixel=(0,0,0,0); edge=False
            for (cx,cy,r),cutters,color in shapes:
                dist=math.hypot(xx-cx,yy-cy); edge|=abs(dist-r)<1.5*scale
                inside=dist<r
                for bx,by,br in cutters:
                    dd=math.hypot(xx-bx,yy-by); edge|=abs(dd-br)<1.5*scale
                    inside &= dd>=br
                if inside: expected_pixel=(*color,255)
            if not edge:
                count+=1; ap=actual.getpixel((x,y))
                if (expected_pixel[3]==0 and ap[3]!=0) or (expected_pixel[3] and ap!=expected_pixel): errors+=1
    check(errors==0,f'Studio geometry {ref}: {count} interior pixels, zero mismatches')
    geometry_stats.append({'reference':ref,'pixels_checked':count,'mismatches':errors})

ico=(ROOT/'favicon/favicon.ico').read_bytes()
check(struct.unpack_from('<HHH',ico)==(0,1,3),'ICO header has three images')
for i,size in enumerate((16,32,48)):
    w,h,_,_,planes,bpp,length,offset=struct.unpack_from('<BBBBHHII',ico,6+i*16)
    check((w,h,planes,bpp)==(size,size,1,32),f'ICO dimensions {size}')
    check(ico[offset:offset+length]==(ROOT/f'favicon/favicon-{size}.png').read_bytes(),f'ICO contains exact tuned {size}px PNG')

im=Image.open(ROOT/'favicon/maskable-512.png').convert('RGBA')
check(im.getchannel('A').getextrema()==(255,255),'Maskable icon is fully opaque')
box=ImageChops.difference(im.convert('RGB'),Image.new('RGB',im.size,build.COL['white'])).getbbox()
check(all(math.hypot(x-256,y-256)<=204.8 for x in (box[0],box[2]) for y in (box[1],box[3])),'Maskable mark inside 80% safe circle')
check(Image.open(ROOT/'favicon/apple-touch-icon.png').getpixel((0,0))[:3]==build.rgb(build.COL['white']),'Apple icon white background')

for spec in build.COVERS:
    cx,cy,w=spec['logo']; h=w*300/510
    sx,sy,sw,sh=spec['safe']
    check(cx-w/2>=sx and cx+w/2<=sx+sw and cy-h/2>=sy and cy+h/2<=sy+sh,f'Cover logo within safe area: {spec["id"]}')
    if 'avatar' in spec:
        x,y,aw,ah=spec['avatar']; pad=w*75/510
        check(cx-w/2-pad>=x+aw or cx+w/2+pad<=x or cy+h/2+pad<=y or cy-h/2-pad>=y+ah,f'Logo clear space avoids avatar: {spec["id"]}')
    a=next(a for a in assets if a.get('cover')==spec['id'] and a['with_logo'])
    b=next(a for a in assets if a.get('cover')==spec['id'] and not a['with_logo'])
    check(Image.open(ROOT/a['path']).size==(spec['w'],spec['h']),f'Cover dimensions: {spec["id"]}')
    diff=ImageChops.difference(Image.open(ROOT/a['path']).convert('RGB'),Image.open(ROOT/b['path']).convert('RGB')).getbbox()
    check(diff is not None and diff[0]>=cx-w/2-1 and diff[2]<=cx+w/2+1 and diff[1]>=cy-h/2-1 and diff[3]<=cy+h/2+1,f'Background pair differs only in mark: {spec["id"]}')
    if spec['id']=='youtube': check((ROOT/a['path']).stat().st_size<6_000_000,'YouTube banner under 6 MB')

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ('href','src'): self.links.append(v)

def valid_link(link,base):
    if link.startswith(('https:','http:','data:','#','mailto:')): return
    target=link.split('#')[0]
    if not target: return
    p=(ROOT/target.lstrip('/')) if target.startswith('/') else base/target
    check(p.exists(),f'Local link exists: {link}')
for path in ['preview.html','favicon/head.html']:
    parser=Links(); parser.feed((ROOT/path).read_text())
    for link in parser.links: valid_link(link,(ROOT/path).parent)
for path in ['README.md','PLATFORM-NOTES.md']:
    s=(ROOT/path).read_text(); check('{{' not in s,f'No template placeholders: {path}')
    for link in re.findall(r'\]\(([^)]+)\)',s): valid_link(link,ROOT)
webmanifest=json.loads((ROOT/'favicon/site.webmanifest').read_text())
for icon in webmanifest['icons']: valid_link(icon['src'],ROOT/'favicon')
check(webmanifest['theme_color']==build.COL['primary'],'Manifest uses primary token')
coverage=json.loads((ROOT/'review/coverage.json').read_text())
shipped={a['path'] for a in assets if a['path'].endswith('.png') and a['kind']!='review'}
check(shipped<=set(coverage['pngs']),'Every shipped PNG is on a contact sheet')
check(near(build.contrast('#000000','#FFFFFF'),21),'Contrast calibration black/white = 21')
check(near(build.contrast(build.COL['ink'],build.COL['ink']),1),'Contrast same-colour calibration = 1')
check(near(build.contrast(build.COL['primary'],build.COL['white']),build.contrast(build.COL['white'],build.COL['primary'])),'Contrast is symmetric')
report={'result':'PASS','checks':len(checks),'geometry':geometry_stats,'assets':len(assets),'pngs':len(shipped),
        'note':'Automated checks only; visual inspection is recorded in STATUS.md.'}
(ROOT/'review/validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
