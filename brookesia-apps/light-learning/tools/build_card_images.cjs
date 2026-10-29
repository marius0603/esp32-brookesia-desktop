const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const sharp=require(process.env.SHARP_MODULE||'sharp');
const root=path.resolve(__dirname,'..'),cache=process.argv[2]||path.join(os.tmpdir(),'light-learning-photos');
const sources=JSON.parse(fs.readFileSync(path.join(root,'packs/photo-sources.json'),'utf8'));
const photos=sources.photos,{width,height}=sources.output;
(function validate(){if(width!==240||height!==162)throw new Error('Card photos must match the 400x270 display aspect ratio');})();
(async()=>{
 fs.mkdirSync(cache,{recursive:true});
 for(const photo of photos){
  const local=path.join(cache,photo.id+'.jpg');
  if(!fs.existsSync(local)){
   const response=await fetch(photo.download_url);if(!response.ok)throw new Error('Photo download failed: '+photo.id);
   fs.writeFileSync(local,Buffer.from(await response.arrayBuffer()));
  }
  if(crypto.createHash('sha256').update(fs.readFileSync(local)).digest('hex')!==photo.original_sha256)throw new Error('Source photo checksum changed: '+photo.id);
  // Crop the original photograph before downsampling; never stretch or pad it.
  const {data,info}=await sharp(local).rotate().raw().toBuffer({resolveWithObject:true});
  const {center_x:x,center_y:y,zoom}=photo.crop;
  if(![x,y].every(v=>Number.isFinite(v)&&v>=0&&v<=1)||!Number.isFinite(zoom)||zoom<1)throw new Error('Invalid crop: '+photo.id);
  let cropWidth=info.width,cropHeight=cropWidth*height/width;
  if(cropHeight>info.height){cropHeight=info.height;cropWidth=cropHeight*width/height;}
  cropWidth=Math.max(1,Math.floor(cropWidth/zoom));cropHeight=Math.max(1,Math.floor(cropHeight/zoom));
  const left=Math.max(0,Math.min(info.width-cropWidth,Math.round(info.width*x-cropWidth/2)));
  const top=Math.max(0,Math.min(info.height-cropHeight,Math.round(info.height*y-cropHeight/2)));
  await sharp(data,{raw:info}).extract({left,top,width:cropWidth,height:cropHeight})
   .resize(width,height,{fit:'cover'}).png({palette:true,colours:128})
   .toFile(path.join(root,'packs/starter/images',photo.id+'.png'));
 }
 console.log(photos.length+' attributed animal photographs cropped to '+width+'x'+height+' landscape PNGs without padding.');
})().catch(e=>{console.error(e);process.exit(1)});
