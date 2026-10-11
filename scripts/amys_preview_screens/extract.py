import sys,os,re
from PIL import Image
import numpy as np
def parse(path):
    lines=open(path).read().splitlines(); regs={}; cur=None
    for l in lines[1:]:
        if not l.strip(): continue
        if ':' not in l: cur=l.strip(); regs[cur]={}; continue
        k,v=l.split(':',1)
        if cur: regs[cur][k.strip()]=v.strip()
    return regs
def unpma(im):
    a=np.asarray(im.convert('RGBA')).astype(np.float32)
    al=a[...,3:4]/255.0
    rgb=np.where(al>0, a[...,:3]/np.maximum(al,1e-6),0).clip(0,255)
    return Image.fromarray(np.concatenate([rgb,a[...,3:4]],-1).astype(np.uint8))
src,out,prefix=sys.argv[1:4]
regs=parse(os.path.join(src,'animation.atlas'))
page=Image.open(os.path.join(src,'animation.png')).convert('RGBA')
for n,r in regs.items():
    if 'bounds' not in r: continue
    x,y,w,h=map(int,r['bounds'].split(','))
    rot=r.get('rotate','0')
    if rot in('90','true'):
        c=page.crop((x,y,x+h,y+w)).rotate(-90,expand=True)  # stored rotated CW -> rotate back CCW
    else: c=page.crop((x,y,x+w,y+h))
    unpma(c).save(os.path.join(out,f'{prefix}_{n.replace(" ","_")}.png'))
