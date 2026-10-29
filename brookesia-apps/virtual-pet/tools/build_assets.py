"""Register generated animation cells and export native frames for the 480px display."""
import hashlib,json,sys
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
from build_cyberpunk_theme import native
APP=ROOT/'brookesia-apps/virtual-pet'
BG='#fff7e8'

def frames(source,cols,rows,indices,height):
    im=Image.open(source).convert('RGB');result=[]
    for i in indices:
        x,y=i%cols,i//cols
        cell=im.crop((round(x*im.width/cols),round(y*im.height/rows),round((x+1)*im.width/cols),round((y+1)*im.height/rows)))
        # The middle idle cell contains a tiny spill from its right-hand neighbour.
        # Trim only that empty outer margin, outside the pony silhouette.
        if source.name=='idle-sheet.png' and i==1:
            cell=cell.crop((0,0,cell.width-12,cell.height))
        r,g,b=cell.split();mask=ImageChops.darker(ImageChops.darker(r,g),b).point(lambda p:255 if p<155 else 0)
        x0,y0,x1,y1=mask.getbbox()
        # Whole-pose registration, without changing the generated face or markings.
        scale=min(height/(y1-y0),296/(x1-x0))
        cropped=cell.crop((max(0,x0-8),max(0,y0-8),min(cell.width,x1+8),min(cell.height,y1+12)))
        cropped=cropped.resize((round(cropped.width*scale),round(cropped.height*scale)),Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',(320,320),BG)
        canvas.paste(cropped,((320-cropped.width)//2,298-round((y1-max(0,y0-8))*scale)))
        result.append(canvas)
    return result

def main():
    out=APP/'content/frames';out.mkdir(parents=True,exist_ok=True)
    (APP/'src/res/images').mkdir(parents=True,exist_ok=True)
    groups={
      'idle':frames(APP/'assets/source/idle-sheet.png',3,2,[0,1,2],272),
      'eat':frames(APP/'assets/source/eat-sheet.png',2,2,[0,1,2],258),
      'sleep':frames(APP/'assets/source/sleep-sheet.png',2,2,[0,1],222)}
    images=[{'id':'launcher_icon','src':'launcher_icon.png','width':92,'height':92,'preload':True}]
    contact=Image.new('RGB',(320*4,350*2),BG);draw=ImageDraw.Draw(contact);n=0
    for state,poses in groups.items():
        for i,im in enumerate(poses):
            name=state+'-'+str(i)+'.bin';native(im,out/name)
            images.append({'id':'pet_'+state+'_'+str(i),'src':'/sdcard/pets/xiaoli/frames/'+name,'width':320,'height':320,'preload':True})
            contact.paste(im,((n%4)*320,(n//4)*350));draw.text(((n%4)*320+12,(n//4)*350+322),state+' '+str(i),fill='#674536');n+=1
    icon=Image.new('RGB',(92,92),BG)
    hero=groups['idle'][0].crop((35,15,292,272)).resize((92,92),Image.Resampling.LANCZOS);icon.paste(hero)
    icon.save(APP/'src/res/images/launcher_icon.png');native(icon,APP/'content/launcher.bin')
    contact.save(APP/'assets/frames-preview.png')
    (APP/'src/res/images/index.json').write_text(json.dumps({'type':'imageSet','images':images},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files={p.relative_to(APP/'content').as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (APP/'content').rglob('*') if p.is_file() and p.name!='manifest.json'}
    manifest={'schema':1,'version':'1.0.0','pet':'xiaoli','frame_size':[320,320],'decoded_frame_bytes':8*320*320*2,'files':files}
    (APP/'content/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Built eight verified native animation frames; decoded memory',manifest['decoded_frame_bytes'])

if __name__=='__main__':main()
