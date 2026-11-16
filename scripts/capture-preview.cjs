// Reproducible gallery from offline sample data. Never contacts a TV.
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs');
const root=path.resolve(__dirname,'..');
(async()=>{
 const server=spawn(process.env.PYTHON||'python',[path.join(root,'scripts','preview.py'),'--port','8775'],{windowsHide:true});
 let browser;
 try{
  await new Promise((resolve,reject)=>{server.stdout.once('data',resolve);server.once('error',reject);server.once('exit',code=>reject(new Error('Preview stopped: '+code)));});
  browser=await chromium.launch({headless:true,...(process.env.BROWSER_CHANNEL?{channel:process.env.BROWSER_CHANNEL}:{})});
  const page=await browser.newPage({viewport:{width:1920,height:1080},reducedMotion:'reduce'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith('http://127.0.0.1:8775/'))errors.push('Unexpected external request');});
  const fresh=async()=>{await page.goto('http://127.0.0.1:8775/');await page.locator('.source').first().waitFor();};
  const save=async name=>{await page.locator('#toast').evaluate(el=>el.hidden=true);await page.screenshot({path:path.join(root,'docs','images',name+'.png')});};
  await fresh();await page.locator('#day').click();await page.locator('[data-port="1"]').focus();await save('cove-launcher');
  await page.locator('#audio-output').focus();await save('cove-audio');
  for(const [port,name,label] of [[2,'cove-playstation5','PlayStation 5'],[4,'cove-switch','Nintendo Switch'],[4,'cove-hdmi','']]){
   await fresh();await page.evaluate(({port,label})=>{previewInputs.update(port,{awake:true,label});previewPictureContext.set({source:port});},{port,label});
   await page.locator('#day').click();await page.locator(`[data-port="${port}"]`).focus();await save(name);
  }
  for(const [scope,name] of [['current','cove-brightness-preview'],['all','cove-live-brightness']]){
   await fresh();await page.evaluate(scope=>previewPictureScope.set(scope),scope);await page.locator('#brightness').click();await save(name);
  }
  await fresh();await page.locator('#night').click();await page.locator('#brightness').click();await save('cove-dim-brightness');
  await fresh();await page.evaluate(()=>{previewInputs.update(2,{awake:true});previewPictureContext.set({source:2});});await page.locator('#day').click();await page.locator('#brightness').click();await save('cove-game-brightness');
  await fresh();await page.evaluate(()=>{previewInputs.update(2,{awake:true});previewPictureContext.set({source:2,pending:true});});await page.locator('[data-port="2"]').focus();await save('cove-pending');
  if(errors.length)throw new Error(JSON.stringify(errors));
  console.log(JSON.stringify({screenshots:10,source:'offline_sample_data',tv_contacted:false}));
 }finally{if(browser)await browser.close();server.kill();}
})().catch(e=>{console.error(e);process.exitCode=1;});
