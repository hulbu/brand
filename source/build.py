#!/usr/bin/env python3
"""Generate the Hulbu brand kit. Run from any directory; no network required.

The two rear shapes are exact circle differences represented by two SVG arcs.
At each y in the rear disk, the front cutter's left edge is farther right than
that of the middle cutter (same radius, same y). Its cut is therefore redundant.
No polygon approximation, mask, stroke, font, or background is used in the mark.
"""
from pathlib import Path
from io import BytesIO
import hashlib
import html
import json
import math
import struct
import sys
import textwrap

import cairosvg
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'source'
CFG = json.loads((SOURCE / 'brand.json').read_text())
COL = {k: v['hex'] for k, v in CFG['palette'].items()}
G = CFG['geometry']
R, XS, Y = G['radius'], G['centers'], G['y']
BOUNDS = (XS[0]-R, Y-R, XS[-1]-XS[0]+2*R, 2*R)
FAVBOX = (280, 280, 520, 520)  # Integer framing, within 0.02% of studio 520.2.
ASSETS = []
VARIANTS = {'': ['yellow','teal','primary'], '-coral': ['primary']*3,
            '-ink': ['ink']*3, '-white': ['white']*3}
PROFILES = {'color-white': ('', 'white'), 'color-cloud': ('', 'canvas'),
            'white-coral': ('-white', 'primary'), 'white-ink': ('-white', 'ink')}
# Safe rectangles are conservative design decisions, not universal UI guarantees.
# Coordinates: x, y, width, height. Avatar rectangles are exclusion envelopes.
COVERS = [
 dict(id='og-default', label='Open Graph / Sunny', w=1200,h=630, style=0, logo=(600,315,306), safe=(100,80,1000,470)),
 dict(id='og-orbit', label='Open Graph / Orbit', w=1200,h=630, style=1, logo=(600,315,306), safe=(100,80,1000,470)),
 dict(id='og-confetti', label='Open Graph / Confetti', w=1200,h=630, style=2, logo=(600,315,306), safe=(100,80,1000,470)),
 dict(id='linkedin-company',label='LinkedIn company / brief size',w=1128,h=191,style=0,logo=(690,95.5,170),safe=(360,25,550,140),avatar=(0,85,290,106)),
 dict(id='linkedin-company-current',label='LinkedIn company / current upload',w=1512,h=256,style=0,logo=(925,128,228),safe=(483,33,738,189),avatar=(0,114,389,142)),
 dict(id='linkedin-personal',label='LinkedIn personal',w=1584,h=396,style=1,logo=(970,188,272),safe=(530,55,740,280),avatar=(0,150,480,246)),
 dict(id='youtube',label='YouTube channel',w=2560,h=1440,style=2,logo=(1280,720,408),safe=(507,508.5,1546,423)),
 dict(id='x',label='X header',w=1500,h=500,style=0,logo=(915,240,306),safe=(440,80,800,330),avatar=(0,260,410,240)),
 dict(id='facebook',label='Facebook / brief size',w=1640,h=624,style=1,logo=(940,255,306),safe=(410,80,820,370),avatar=(0,370,440,254)),
 dict(id='facebook-recommended',label='Facebook / recommended upload',w=851,h=315,style=1,logo=(488,129,153),safe=(212,40,426,186),avatar=(0,187,228,128)),
]


def write(path, data):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes): p.write_bytes(data)
    else: p.write_text(data, encoding='utf-8')


def record(path, kind, **extra):
    ASSETS.append(dict(path=path, kind=kind, **extra))


def f(n):
    return f'{n:.9f}'.rstrip('0').rstrip('.') if n else '0'


def circle(cx,cy,r):
    return f'M {f(cx-r)} {f(cy)} A {f(r)} {f(r)} 0 1 0 {f(cx+r)} {f(cy)} A {f(r)} {f(r)} 0 1 0 {f(cx-r)} {f(cy)} Z'


def crescent(cx, cy, r, distance, gap):
    cutter = r + gap
    a = (r*r - cutter*cutter + distance*distance) / (2*distance)
    h = math.sqrt(r*r-a*a)
    return (f'M {f(cx+a)} {f(cy-h)} A {f(r)} {f(r)} 0 {int(a > 0)} 0 {f(cx+a)} {f(cy+h)} '
            f'A {f(cutter)} {f(cutter)} 0 0 1 {f(cx+a)} {f(cy-h)} Z')


def mark_paths(gap=22, variant='', cx=540, cy=540, width=510):
    scale=width/BOUNDS[2]
    xs=[cx+(x-540)*scale for x in XS]
    ds=[crescent(xs[i],cy,R*scale,(XS[i+1]-XS[i])*scale,gap*scale) for i in (0,1)]
    ds.append(circle(xs[2],cy,R*scale))
    return '\n'.join(f'<path fill="{COL[c]}" d="{d}"/>' for c,d in zip(VARIANTS[variant],ds))


def svg(body, box, title, style=''):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{" ".join(map(str,box))}" role="img">\n'
            f'<title>{html.escape(title)}</title>\n{style}{body}\n</svg>\n')


def rect(x,y,w,h,c):
    return f'<path fill="{COL.get(c,c)}" d="M {f(x)} {f(y)} h {f(w)} v {f(h)} h {f(-w)} Z"/>'


def disk(cx,cy,r,c):
    return f'<path fill="{COL.get(c,c)}" d="{circle(cx,cy,r)}"/>'


def half(cx,cy,r,c,flip=False):
    sweep=0 if flip else 1
    return f'<path fill="{COL[c]}" d="M {f(cx-r)} {f(cy)} A {f(r)} {f(r)} 0 0 {sweep} {f(cx+r)} {f(cy)} Z"/>'


def raster(s,w,h):
    return Image.open(BytesIO(cairosvg.svg2png(bytestring=s.encode(),output_width=w,output_height=h))).convert('RGBA')


def save_png(path, im, kind, **extra):
    info=PngImagePlugin.PngInfo(); info.add(b'sRGB', b'\x00')
    buf=BytesIO(); im.save(buf, format='PNG', optimize=True, pnginfo=info)
    write(path,buf.getvalue()); record(path,kind,width=im.width,height=im.height,**extra)


def export(path, body, w,h,kind,**extra):
    save_png(path,raster(svg(body,(0,0,w,h),'Hulbu'),w,h),kind,**extra)


def logos():
    for variant in VARIANTS:
        for cut,gap in G['gaps'].items():
            stem='hulbu-mark'+variant+('' if cut=='standard' else '-'+cut)
            s=svg(mark_paths(gap,variant),BOUNDS,'Hulbu mark — '+(variant[1:] or 'Sunny sky')+' / '+cut)
            write(f'logo/{stem}.svg',s)
            record(f'logo/{stem}.svg','logo',variant=variant,cut=cut,gap=gap)
            for size in (512,1024,2048):
                save_png(f'logo/png/{stem}-{size}.png',raster(s,size,round(size*300/510)), 'logo',variant=variant,cut=cut,gap=gap)


def favicons():
    for auto in (False,True):
        style=f'<style>@media (prefers-color-scheme: dark) {{ path {{ fill: {COL["white"]}; }} }}</style>\n' if auto else ''
        path='favicon/favicon'+('-auto' if auto else '')+'.svg'
        write(path,svg(mark_paths(32),FAVBOX,'Hulbu favicon',style)); record(path,'favicon')
    pngs=[]
    for size in (16,32,48):
        gap=G['gaps'].get(str(size),22)
        save_png(f'favicon/favicon-{size}.png',raster(svg(mark_paths(gap),FAVBOX,'Hulbu'),size,size),'favicon',gap=gap)
        pngs.append((ROOT/f'favicon/favicon-{size}.png').read_bytes())
    # Pack the tuned PNGs verbatim; never let an ICO library rescale a 48 px cut.
    head=struct.pack('<HHH',0,1,3); entries=b''; offset=6+3*16
    for size,data in zip((16,32,48),pngs):
        entries+=struct.pack('<BBBBHHII',size,size,0,0,1,32,len(data),offset); offset+=len(data)
    write('favicon/favicon.ico',head+entries+b''.join(pngs)); record('favicon/favicon.ico','favicon')
    for name,size,bg,width in [('apple-touch-icon',180,'white',.70),('android-chrome-192',192,None,.90),
                                ('android-chrome-512',512,None,.90),('maskable-512',512,'white',.68)]:
        body=(rect(0,0,size,size,bg) if bg else '')+mark_paths(cx=size/2,cy=size/2,width=size*width)
        export(f'favicon/{name}.png',body,size,size,'favicon')
    manifest={'name':'Hulbu','short_name':'Hulbu','start_url':'/','scope':'/','display':'standalone',
              'background_color':COL['white'],'theme_color':COL['primary'],
              'icons':[{'src':f'android-chrome-{s}.png','sizes':f'{s}x{s}','type':'image/png','purpose':'any'} for s in (192,512)] +
                      [{'src':'maskable-512.png','sizes':'512x512','type':'image/png','purpose':'maskable'}]}
    write('favicon/site.webmanifest',json.dumps(manifest,indent=2)+'\n'); record('favicon/site.webmanifest','integration')
    write('favicon/head.html',f'''<!-- Copy favicon/ to your public web root. Adjust /favicon/ if it lives elsewhere. -->
<link rel="icon" href="/favicon/favicon.ico" sizes="16x16 32x32 48x48">
<link rel="icon" href="/favicon/favicon-auto.svg" type="image/svg+xml" sizes="any">
<link rel="apple-touch-icon" href="/favicon/apple-touch-icon.png" sizes="180x180">
<link rel="manifest" href="/favicon/site.webmanifest">
<meta name="theme-color" content="{COL['primary']}">
'''); record('favicon/head.html','integration')


def profiles():
    for variant,(mark,bg) in PROFILES.items():
        for platform,size in CFG['profiles'].items():
            path=f'social/profile/{variant}/{platform}-{size}.png'
            body=rect(0,0,size,size,bg)+mark_paths(variant=mark,cx=size/2,cy=size/2,width=size*.68)
            export(path,body,size,size,'profile',variant=variant,platform=platform)


def cover_body(spec):
    w,h,sty=spec['w'],spec['h'],spec['style']
    body=rect(0,0,w,h,'white' if sty!=1 else 'canvas')
    # Deliberate edge compositions: only decoration is allowed to bleed/crop.
    # Keep the central content field clear on all three responsive compositions.
    if sty==0:
        body+=disk(w*.04,h*.12,min(h*.82,w*.19),'yellow')
        body+=half(w*.91,h*.12,min(h*.64,w*.14),'teal',True)
        body+=disk(w*1.015,h*.97,min(h*.77,w*.18),'primary')
        body+=disk(w*.19,h*1.04,min(h*.17,w*.038),'teal')
    elif sty==1:
        rr=min(h*.74,w*.18)
        body+=f'<path fill="{COL["teal"]}" d="{crescent(w*.12,h*.82,rr,rr*.75,rr*.15)}"/>'
        body+=half(w*.91,h*.18,min(h*.74,w*.17),'primary',True)
        body+=disk(w*.91,h*1.09,min(h*.60,w*.14),'yellow')
        body+=disk(w*.22,h*.11,min(h*.10,w*.027),'primary')
    else:
        body+=half(w*.055,h*.25,min(h*.42,w*.18),'yellow',True)
        body+=disk(w*.95,h*.16,min(h*.31,w*.12),'teal')
        body+=half(w*.83,h*.93,min(h*.34,w*.15),'primary')
        body+=disk(w*.14,h*.81,min(h*.13,w*.06),'primary')
        body+=disk(w*.29,h*.12,min(h*.052,w*.025),'teal')
    return body


def covers():
    for spec in COVERS:
        base=cover_body(spec)
        for with_logo in (False,True):
            # OG's default file is the ready-to-use marked version.
            suffix='' if spec['id'].startswith('og-') and with_logo else '-with-logo' if with_logo else '-background'
            path=f'social/covers/{spec["id"]}{suffix}.png'
            body=base
            if with_logo:
                cx,cy,width=spec['logo']; body+=mark_paths(cx=cx,cy=cy,width=width)
            export(path,body,spec['w'],spec['h'],'cover',cover=spec['id'],with_logo=with_logo)


def rgb(c): return tuple(int(c[i:i+2],16) for i in (1,3,5))

def cmyk(c):
    vals=[n/255 for n in rgb(c)]; k=1-max(vals)
    return tuple(round(100*(1-n-k)/(1-k)) if k<1 else 0 for n in vals)+(round(k*100),)

def lum(c):
    def lin(n):
        n/=255
        return n/12.92 if n<=.04045 else ((n+.055)/1.055)**2.4
    return sum(a*lin(n) for a,n in zip((.2126,.7152,.0722),rgb(c)))

def contrast(a,b):
    l1,l2=sorted((lum(a),lum(b)))
    return (l2+.05)/(l1+.05)

def font(size): return ImageFont.load_default(size=size)

def label(draw,xy,txt,size=20,color=None): draw.text(xy,txt,font=font(size),fill=color or COL['ink'])


def colors():
    tokens={'name':'Hulbu / Sunny sky','colorSpace':'sRGB','primary':'primary', 'colors': {}}
    for key,meta in CFG['palette'].items():
        c=meta['hex']
        tokens['colors'][key]={**meta,'rgb':list(rgb(c)),'cmykApprox':list(cmyk(c)),
                               'contrastOnWhite':round(contrast(c,COL['white']),4),
                               'contrastOnInk':round(contrast(c,COL['ink']),4)}
    tokens['notes']='CMYK is an unprofiled approximation, not a press specification. Coral is the primary token.'
    write('colors/tokens.json',json.dumps(tokens,indent=2)+'\n')
    write('colors/tokens.css','/* Generated from source/brand.json. */\n:root {\n'+''.join(f'  --hulbu-{k}: {c};\n' for k,c in COL.items())+'}\n')
    write('colors/tokens.ts','// Generated from source/brand.json.\nexport const hulbuColors = '+json.dumps(COL,indent=2)+' as const;\nexport type HulbuColor = keyof typeof hulbuColors;\nexport const primaryColor = hulbuColors.primary;\n')
    for ext in ('json','css','ts'): record(f'colors/tokens.{ext}','color-data')
    im=Image.new('RGB',(1440,1080),COL['canvas']); d=ImageDraw.Draw(im)
    label(d,(60,42),'HULBU / SUNNY SKY',22); label(d,(60,84),'A little more colour.',52)
    for i,(key,meta) in enumerate(CFG['palette'].items()):
        x=60+(i%3)*450; y=190+(i//3)*385; c=meta['hex']
        d.rectangle((x,y,x+420,y+145),fill=c,outline=COL['ink'],width=1)
        label(d,(x,y+168),meta['name']+(' / Primary' if key=='primary' else ''),26)
        label(d,(x,y+211),c+'   RGB '+', '.join(map(str,rgb(c))),18)
        label(d,(x,y+245),'CMYK '+ ' / '.join(map(str,cmyk(c)))+' % (approx.)',18)
        label(d,(x,y+285),f'On white  {contrast(c,COL["white"]):.2f}:1',20)
        label(d,(x,y+315),f'On ink      {contrast(c,COL["ink"]):.2f}:1',20)
    label(d,(60,998),'WCAG AA: 4.5:1 normal text; 3:1 large text. Choose text using the ratios above.',19)
    label(d,(60,1030),'CMYK is unprofiled. Request a colour-managed proof for print.',19)
    save_png('colors/swatches.png',im,'color-data')
    return tokens


def docs_images():
    # Clear space diagram. The dimension labels describe the artwork, not a wordmark.
    im=Image.new('RGB',(1200,650),COL['canvas']); d=ImageDraw.Draw(im)
    m=raster(svg(mark_paths(),BOUNDS,'Hulbu'),510,300)
    im.paste(m,(345,175),m)
    d.rectangle((270,100,930,550),outline=COL['ink'],width=2)
    d.rectangle((345,175,855,475),outline=COL['ink'],width=1)
    label(d,(60,34),'GIVE IT SPACE',22); label(d,(950,305),'75 units',22)
    label(d,(390,583),'Clear space = half the radius',26)
    save_png('guidelines/clear-space.png',im,'guideline')
    examples=[('do-color','DO / Colour on light','', 'white',False),
              ('do-white','DO / White on dark','-white','ink',False),
              ('dont-stretch','DON\'T / Stretch the mark','','white',True),
              ('dont-fill-gaps','DON\'T / Fill the transparent gaps','','teal',False),
              ('dont-frame','DON\'T / Add an avatar frame','','white',False)]
    for id,title,variant,bg,stretch in examples:
        im=Image.new('RGB',(600,420),COL[bg]); d=ImageDraw.Draw(im)
        fw,fh=(360,135) if stretch else (306,180)
        logo=raster(svg(mark_paths(variant=variant),BOUNDS,'Hulbu'),fw,fh)
        if id=='dont-fill-gaps':
            # Deliberately wrong example, labelled and isolated from downloadable logos.
            for cx in (237,300,363): d.ellipse((cx-90,120,cx+90,300),fill=COL['white'])
        if id=='dont-frame': d.ellipse((130,65,470,405),outline=COL['primary'],width=12)
        im.paste(logo,((600-fw)//2,(420-fh)//2+(25 if id=='dont-frame' else 0)),logo)
        d=ImageDraw.Draw(im); label(d,(28,22),title,22,COL['white'] if bg=='ink' else COL['ink'])
        save_png(f'guidelines/{id}.png',im,'guideline')
    # Pixel proof is displayed at native size first, then nearest-neighbour magnified.
    im=Image.new('RGB',(1100,560),COL['canvas']); d=ImageDraw.Draw(im)
    label(d,(34,26),'FAVICONS / NATIVE PIXELS + 8x / 8x / 6x',24)
    for i,size in enumerate((16,32,48)):
        x=40+i*355
        im.paste(COL['white'],(x,85,x+325,510))
        a=Image.open(ROOT/f'favicon/favicon-{size}.png').convert('RGBA')
        im.paste(a,(x+25,108),a)
        z=a.resize((size*6,size*6),Image.Resampling.NEAREST)
        # 16 / 32 use 8x, 48 uses 6x to fit the panel.
        if size<48: z=a.resize((size*8,size*8),Image.Resampling.NEAREST)
        im.paste(z,(x+18,180),z)
        label(d,(x+18,466),f'{size} px / gap {44 if size==16 else 32 if size==32 else 22}',21)
    save_png('guidelines/favicon-pixels.png',im,'guideline')


def template(name,variables):
    s=(SOURCE/'templates'/name).read_text()
    for key,value in variables.items(): s=s.replace('{{'+key+'}}',str(value))
    return s


def documents(tokens):
    rows='\n'.join(f'| {v["name"]}{" (primary)" if k=="primary" else ""} | `{v["hex"]}` | {", ".join(map(str,v["rgb"]))} | {" / ".join(map(str,v["cmykApprox"]))} | {v["contrastOnWhite"]:.2f}:1 | {v["contrastOnInk"]:.2f}:1 |' for k,v in tokens['colors'].items())
    bright=[(CFG['palette'][k]['name'],COL[k]) for k in ('primary','yellow','teal')]
    ink_ok=[n for n,c in bright if contrast(c,COL['ink'])>=4.5]
    low=[n for n,c in bright if contrast(c,COL['white'])<3]
    guidance=('Ink meets AA for normal text on '+', '.join(ink_ok)+'. ' if ink_ok else '')
    if low: guidance+=', '.join(low)+' on white fall below 3:1; white text on those colours also falls below 3:1. '
    guidance+='Logos have an exemption, which does not extend to interface text or essential controls.'
    replacements={**COL,'COLOR_TABLE':rows,'COLOR_GUIDANCE':guidance,'DATE':CFG['checked'],'ASSET_COUNT':len(ASSETS)}
    for filename in ('README.md','LICENSE','PLATFORM-NOTES.md'):
        write(filename,template(filename,replacements)); record(filename,'documentation')
    write('source/README.md',template('source-readme.md',replacements))


def preview():
    sections=[]
    for kind,title in [('logo','01 / The mark'),('favicon','02 / Every little pixel'),('profile','03 / A face for every place'),('cover','04 / Room to play'),('color-data','05 / Sunny sky'),('guideline','06 / Use it well')]:
        cards=[]
        for a in ASSETS:
            if a['kind']!=kind or not a['path'].endswith(('.svg','.png','.ico')): continue
            path=a['path']; name=Path(path).name
            classes='asset '+('dark' if a.get('variant')=='-white' else '')
            details=''
            if kind=='cover':
                spec=next(s for s in COVERS if s['id']==a['cover']); w,h=spec['w'],spec['h']
                x,y,sw,sh=spec['safe']
                details=f'<span class="safe" style="left:{x/w*100}%;top:{y/h*100}%;width:{sw/w*100}%;height:{sh/h*100}%">Safe content</span>'
                if 'avatar' in spec:
                    x,y,sw,sh=spec['avatar']
                    details+=f'<span class="avatar" style="left:{x/w*100}%;top:{y/h*100}%;width:{sw/w*100}%;height:{sh/h*100}%">Avatar envelope</span>'
            native=kind=='favicon' and a.get('width',100)>0 and a.get('width',100)<=48
            style=f'width:{a["width"]}px;height:{a["height"]}px' if native else ''
            cards.append(f'<article class="{classes}" data-kind="{kind}" data-name="{html.escape(path)}"><div class="art {"profile" if kind=="profile" else ""} {"cover" if kind=="cover" else ""}"><div class="image-wrap"><img src="{path}" alt="{html.escape(path)}" style="{style}" loading="lazy">{details}</div></div><a href="{path}" download>{html.escape(name)} <span aria-hidden="true">↗</span></a><small>{a.get("width", "Vector")}'+(f' × {a["height"]} px' if 'height' in a else '')+f' · {html.escape(str(a.get("cut",a.get("variant",""))))}</small></article>')
        sections.append(f'<section id="{kind}"><h2>{title}</h2><div class="grid {kind}">{"".join(cards)}</div></section>')
    files=''.join(f'<li><a href="{a["path"]}">{a["path"]}</a></li>' for a in ASSETS if not a['path'].endswith(('.png','.svg','.ico')))
    write('preview.html',template('preview.html',{**COL,'SECTIONS':'\n'.join(sections),'FILES':files,'DATE':CFG['checked']}))
    record('preview.html','documentation')


def review_sheets():
    # Every shipped PNG, plus reference PNGs, appears once on a labelled sheet.
    paths=[a['path'] for a in ASSETS if a['path'].endswith('.png')]
    paths+=['source/favicon-from-studio/'+p.name for p in sorted((SOURCE/'favicon-from-studio').glob('*.png'))]
    for i in range(0,len(paths),12):
        group=paths[i:i+12]
        im=Image.new('RGB',(1440,1420),COL['canvas']); d=ImageDraw.Draw(im)
        label(d,(30,18),f'HULBU / ALL RASTER EXPORTS / SHEET {i//12+1}',22)
        for j,p in enumerate(group):
            x=25+(j%3)*475; y=65+(j//3)*335
            bg=COL['ink'] if 'mark-white' in p else COL['white']
            d.rectangle((x,y,x+450,y+278),fill=bg)
            a=Image.open(ROOT/p).convert('RGBA'); a.thumbnail((424,255))
            im.paste(a,(x+(450-a.width)//2,y+(278-a.height)//2),a)
            for k,line in enumerate(textwrap.wrap(p,48)):
                label(d,(x,y+285+k*19),line,16)
        dest=f'review/contact-{i//12+1:02}.png'
        save_png(dest,im,'review')
    write('review/coverage.json',json.dumps({'pngs':paths,'sheets':math.ceil(len(paths)/12)},indent=2)+'\n')


def main():
    logos(); favicons(); profiles(); covers(); tokens=colors(); docs_images(); documents(tokens); preview(); review_sheets()
    inventory={'generated_by':'source/build.py','checked':CFG['checked'],'assets':ASSETS,'covers':COVERS}
    write('source/asset-manifest.json',json.dumps(inventory,indent=2)+'\n')
    print(f'Generated {len(ASSETS)} assets. Open preview.html; run python3 source/validate.py.')

if __name__=='__main__': main()
