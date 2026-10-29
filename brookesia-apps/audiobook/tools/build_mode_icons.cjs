// Native vector artwork; rasterize small PNGs for the device image decoder.
const fs=require('node:fs'),path=require('node:path');
const sharp=require(process.env.SHARP_MODULE||'sharp');
const shapes={
 sequence:'<path d="M7 10h22m-5-5 5 5-5 5M29 26H7m5-5-5 5 5 5"/>',
 random:'<path d="M6 10h4c7 0 9 16 16 16h4m-5-5 5 5-5 5M6 26h4c3 0 5-3 7-6m3-5c2-3 3-5 6-5h4m-5-5 5 5-5 5"/>',
 repeat_one:'<path d="M6 15v-3a5 5 0 0 1 5-5h19m-5-5 5 5-5 5M30 21v3a5 5 0 0 1-5 5H6m5-5-5 5 5 5"/><path d="M16 16l3-2v9m-3 0h6"/>'
};
(async()=>{for(const [name,shape] of Object.entries(shapes)){
 const svg='<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36"><g fill="none" stroke="#f2d38b" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'+shape+'</g></svg>';
 const dir=path.resolve(__dirname,'../assets');fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path.join(dir,'mode-'+name+'.svg'),svg+'\n');
 await sharp(Buffer.from(svg)).png().toFile(path.resolve(__dirname,'../src/res/images/mode-'+name+'.png'));
}})().catch(e=>{console.error(e);process.exit(1)});
