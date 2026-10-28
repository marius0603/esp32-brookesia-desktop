const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const sharp=require(process.env.SHARP_MODULE||'sharp');
const root=path.resolve(__dirname,'..'),cache=process.argv[2]||path.join(os.tmpdir(),'light-learning-photos');
const photos=JSON.parse(fs.readFileSync(path.join(root,'packs/photo-sources.json'),'utf8')).photos;
(async()=>{
 fs.mkdirSync(cache,{recursive:true});
 for(const photo of photos){
  const local=path.join(cache,photo.id+'.jpg');
  if(!fs.existsSync(local)){
   const response=await fetch(photo.download_url);if(!response.ok)throw new Error('Photo download failed: '+photo.id);
   fs.writeFileSync(local,Buffer.from(await response.arrayBuffer()));
  }
  if(crypto.createHash('sha256').update(fs.readFileSync(local)).digest('hex')!==photo.original_sha256)throw new Error('Source photo checksum changed: '+photo.id);
  await sharp(local).rotate().resize(256,192,{fit:'contain',background:'#172638'}).png({palette:true,colours:128}).toFile(path.join(root,'packs/starter/images',photo.id+'.png'));
 }
 console.log(photos.length+' attributed animal photographs prepared as 256x192 PNGs.');
})().catch(e=>{console.error(e);process.exit(1)});
