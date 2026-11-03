// Rasterize our original vector radio artwork; preserve transparent outer area.
const fs=require('node:fs'),path=require('node:path');
const sharp=require(process.env.SHARP_MODULE||'sharp');
const root=path.resolve(__dirname,'..');
(async()=>{
 const svg=fs.readFileSync(path.join(root,'assets/launcher-icon.svg'));
 const out=path.join(root,'src/res/images');fs.mkdirSync(out,{recursive:true});
 await sharp(svg).resize(96,96).png().toFile(path.join(out,'launcher_icon.png'));
 const illustration=Buffer.from(svg.toString().replace(/<rect id="icon-frame"[^>]*\/>/,''));
 await sharp(illustration).resize(166,166).png().toFile(path.join(out,'radio_art.png'));
 await sharp(svg).resize(384,384).png().toFile(path.join(root,'assets/launcher-icon-preview.png'));
 console.log('Rendered transparent original radio icon and in-app artwork');
})().catch(e=>{console.error(e);process.exit(1)});
