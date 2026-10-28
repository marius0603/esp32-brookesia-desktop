const fs=require('node:fs'),path=require('node:path'),sharp=require(process.env.SHARP_MODULE||'sharp');
const dir=path.join(__dirname,'../packs/starter/images');
Promise.all(fs.readdirSync(dir).filter(n=>n.endsWith('.svg')).map(n=>sharp(path.join(dir,n)).resize(168,168).png().toFile(path.join(dir,n.replace('.svg','.png'))))).then(()=>console.log('Six lightweight animal illustrations rendered.')).catch(e=>{console.error(e);process.exit(1)});
