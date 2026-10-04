// Optional browser verification; npm ci && npx playwright install chromium.
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, dirname, extname, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const out=resolve(root,'.cache/browser');
await mkdir(out,{recursive:true});
const mime={'.html':'text/html','.svg':'image/svg+xml','.png':'image/png','.ico':'image/x-icon','.json':'application/json','.webmanifest':'application/manifest+json','.css':'text/css'};
const server=createServer(async(req,res)=>{
  try{
    const path=resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://local').pathname));
    if(!path.startsWith(root+sep)) {res.writeHead(403).end();return;}
    const data=await readFile(path);
    res.writeHead(200,{'Content-Type':mime[extname(path)]||'text/plain'});res.end(data);
  }catch{res.writeHead(404).end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const url=`http://127.0.0.1:${server.address().port}`;
let browser;
try{
 browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1080},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url+'/preview.html');
 const comparisons=[];
 for(const [ref,generated] of [['src.svg','hulbu-mark.svg'],['src-32.svg','hulbu-mark-32.svg'],['src-16.svg','hulbu-mark-16.svg']]){
   const original=await readFile(resolve(root,'source/favicon-from-studio',ref),'utf8');
   let candidate=await readFile(resolve(root,'logo',generated),'utf8');
   candidate=candidate.replace(/viewBox="[^"]+"/,original.match(/viewBox="[^"]+"/)[0]);
   const result=await page.evaluate(async({original,candidate})=>{
     async function render(svg){const im=new Image();im.src='data:image/svg+xml,'+encodeURIComponent(svg);await im.decode();const c=document.createElement('canvas');c.width=c.height=1040;const x=c.getContext('2d');x.drawImage(im,0,0,1040,1040);return c;}
     const a=await render(original),b=await render(candidate);
     const aa=a.getContext('2d').getImageData(0,0,1040,1040).data,bb=b.getContext('2d').getImageData(0,0,1040,1040).data;
     let total=0,severe=0;
     for(let i=0;i<aa.length;i+=4){let m=0;for(let k=0;k<4;k++){const av=k===3?aa[i+3]:aa[i+k]*aa[i+3]/255;const bv=k===3?bb[i+3]:bb[i+k]*bb[i+3]/255;const delta=Math.abs(av-bv);total+=delta;m=Math.max(m,delta);}if(m>64)severe++;}
     const c=document.createElement('canvas');c.width=1440;c.height=600;const x=c.getContext('2d');x.fillStyle='#F4F0EC';x.fillRect(0,0,1440,600);x.fillStyle='#2E2C33';x.font='24px sans-serif';x.fillText('Studio mask reference',40,45);x.fillText('Generated circular paths',750,45);x.drawImage(a,65,80,500,500);x.drawImage(b,785,80,500,500);
     return {meanPremultipliedError:total/aa.length,severePixels:severe,severeFraction:severe/(1040*1040),png:c.toDataURL('image/png')};
   },{original,candidate});
   assert(result.meanPremultipliedError<0.5,ref+' average mismatch');
   assert(result.severeFraction<0.001,ref+' geometry mismatch');
   await writeFile(resolve(out,ref.replace('.svg','-comparison.png')),Buffer.from(result.png.split(',')[1],'base64'));
   delete result.png;comparisons.push({reference:ref,...result});
 }
 // Every asset should load, even below the lazy-load viewport.
 const imgs=await page.evaluate(async()=>{const all=[...document.images];for(const i of all)i.loading='eager';await Promise.all(all.map(i=>i.decode()));return all.map(i=>({src:i.getAttribute('src'),ok:i.naturalWidth>0}));});
 assert(imgs.every(i=>i.ok));
 await page.screenshot({path:resolve(out,'preview-desktop.png')});
 await page.locator('#circles').check();await page.locator('#guides').check();
 assert(await page.locator('body').evaluate(e=>e.classList.contains('circle-crops')&&e.classList.contains('show-guides')));
 await page.locator('#cover').screenshot({path:resolve(out,'cover-guides.png')});
 await page.locator('#profile').screenshot({path:resolve(out,'profile-crops.png')});
 await page.locator('#search').fill('instagram');
 assert.equal(await page.locator('.asset:visible').count(),4);
 await page.locator('#search').fill('no-such-asset');assert(await page.locator('#empty').isVisible());
 await page.locator('#search').fill('');
 const themes=[];
 for(const theme of ['light','dark']){
   await page.emulateMedia({colorScheme:theme});
   // Reload ensures external SVG image cache updates its preferred colour scheme.
   await page.reload();
   const pixel=await page.evaluate(async()=>{const i=document.querySelector('.native-auto img');await i.decode();const c=document.createElement('canvas');c.width=c.height=128;const x=c.getContext('2d');x.drawImage(i,0,0,128,128);return [...x.getImageData(90,64,1,1).data];});
   const cfg=JSON.parse(await readFile(resolve(root,'source/brand.json'),'utf8'));
   const hex=cfg.palette[theme==='dark'?'white':'primary'].hex;
   const expected=hex.slice(1).match(/../g).map(x=>parseInt(x,16)).concat(255);
   assert.deepEqual(pixel,expected,theme+' auto favicon');themes.push({theme,pixel});
   await page.locator('section[aria-label="Favicon pixel check"]').screenshot({path:resolve(out,`favicons-${theme}.png`)});
 }
 await page.emulateMedia({colorScheme:'light'});
 await page.setViewportSize({width:390,height:844});await page.reload();
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile horizontal overflow');
 await page.screenshot({path:resolve(out,'preview-mobile.png')});
 assert.equal(errors.length,0);
 const report={result:'PASS',referenceComparisons:comparisons,loadedImages:imgs.length,faviconThemes:themes,interactiveControls:'PASS',mobileOverflow:false,pageErrors:errors};
 await writeFile(resolve(out,'validation.json'),JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify(report,null,2));
}finally{await browser?.close();await new Promise(r=>server.close(r));}
