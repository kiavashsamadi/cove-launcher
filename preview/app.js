/* Local UI simulator only. No network, TV controls, storage or continuous animation. */
(() => {
 'use strict';
 const $ = selector => document.querySelector(selector);
 const home = $('#home'), simulation = $('#simulation');
 // Sample mappings only. Device names come from inventory, never port-number guesses.
 const ports = [
  {number:1,label:'Apple TV',connected:true,awake:true},
  {number:2,label:'PlayStation 5',connected:true,awake:false},
  {number:3,label:'HDMI 3',connected:false,awake:false},
  {number:4,label:'Nintendo Switch',connected:true,awake:false}
 ];
 let current = 1, lastPort = 1, opener = null, toastTimer, heroTimer;
 const reduceMotion=matchMedia('(prefers-reduced-motion: reduce)');
 const sources = [];
 const utility = [$('#brightness'),$('#day'),$('#night'),$('#settings')];
 let brightnessDraft=null,pictureScope='current',picturePending=false;
 const pictures=new Map([[1,{mode:'Standard SDR',value:50,scopeAvailable:true}],[2,{mode:'Game HDR',value:50,scopeAvailable:false}],[3,{mode:'Standard SDR',value:50,scopeAvailable:true}],[4,{mode:'Game SDR',value:50,scopeAvailable:false}]]);
 const profileLevels={day:50,night:0,selected:null};
 function picture(){return pictures.get(current);}
 function levels(){return profileLevels;}
 function selectedProfile(){const p=levels(),value=picture().value;if(!picturePending&&p.selected&&p[p.selected]===value)return p.selected;return null;}
 function eligible(){return !picturePending&&ports[current-1]?.connected&&ports[current-1]?.awake&&['current','all'].includes(pictureScope);}

 const brightnessPanel=$('#brightness-panel'),brightnessRange=$('#brightness-range');
 const connected = () => sources.filter(el => !el.hidden);
 function iconFor(label){const name=label.toLowerCase();
  if(name.includes('apple tv')||name.includes('appletv'))return 'tv';
  if(name.includes('playstation 5')||name==='ps5'||name.startsWith('ps5 ')||name.endsWith(' ps5'))return 'game';
  if(/^switch(?: 2| oled| lite)?$/.test(name)||/(^| )nintendo ?switch( |$)/.test(name))return 'switch';
  if(name.includes('xbox'))return 'xbox';
  if(/\bpc\b|computer|laptop/.test(name))return 'computer';
  if(/blu[ -]?ray|\bdvd\b/.test(name))return 'disc';
  if(/\bps4\b|playstation|nintendo|\bwii\b|console/.test(name))return 'console';
  return 'hdmi';
 }
 function artwork(kind){return 'shared/'+({tv:'brand-appletv',game:'brand-playstation',switch:'brand-nintendoswitch',xbox:'brand-xbox',hdmi:'symbol-hdmi',computer:'symbol-computer',disc:'symbol-disc',console:'symbol-game'}[kind]||'symbol-hdmi')+'.svg';}
 function notify(message){clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').hidden=false;toastTimer=setTimeout(()=>{$('#toast').hidden=true;},3200);}
 function fit(){document.documentElement.style.setProperty('--s',Math.min(innerWidth/1920,innerHeight/1080));}
 function render(){
  const active=document.activeElement, previous=Number(active?.dataset.port)||lastPort;
  ports.forEach((port,index)=>{
   const el=sources[index];el.hidden=!port.connected;
   const name=port.label.trim()||`HDMI ${port.number}`;
   el.querySelector('.source-label').textContent=name;

   el.querySelector('.port-label').textContent=`HDMI ${port.number}`;
   el.querySelector('.current-badge').hidden=port.number!==current;
   const kind=iconFor(name);el.dataset.kind=kind;el.querySelector('img').src=artwork(kind);
   el.setAttribute('aria-label',`${name}, HDMI ${port.number}${port.number===current?', current input':''}${!port.awake?', sleeping':''}, preview`);
   if(port.number===current)el.setAttribute('aria-current','true');else el.removeAttribute('aria-current');
  });
  const available=connected();$('#empty-state').hidden=available.length!==0;
  $('#input-count').textContent=`${available.length} connected`;

  const availablePicture=eligible(),appearance=selectedProfile();
  utility.slice(1,3).forEach(el=>{el.setAttribute('aria-disabled',String(!availablePicture));el.setAttribute('aria-pressed',String(availablePicture&&el.id===appearance));});
  $('#brightness').setAttribute('aria-disabled',String(!availablePicture));$('#brightness-current').textContent=picturePending?'…':availablePicture?picture().value:'';
  if(brightnessDraft&&(!availablePicture||brightnessDraft.scope!==pictureScope||brightnessDraft.source!==current||brightnessDraft.mode!==picture().mode))closeBrightness();
  if(!available.some(el=>Number(el.dataset.port)===lastPort))lastPort=Number(available.slice().sort((a,b)=>Math.abs(Number(a.dataset.port)-previous)-Math.abs(Number(b.dataset.port)-previous))[0]?.dataset.port)||0;
  if(sources.includes(active)&&active.hidden)(sources.find(el=>Number(el.dataset.port)===lastPort&&!el.hidden)||$('#settings')).focus();
  renderHero();
 }
 function renderHero(){
  const toolbar=utility.includes(document.activeElement)||!!brightnessDraft;
  const port=ports.find(p=>p.number===(toolbar?current:lastPort)&&p.connected)||(!toolbar&&ports.find(p=>p.connected));
  $('.hero').hidden=!port;if(!port)return;
  $('#hero-name').textContent=port.label.trim()||`HDMI ${port.number}`;
  $('#hero-current').hidden=port.number!==current;
  const kind=iconFor(port.label),art=$('#hero-art'),url=artwork(kind);$('.hero').dataset.kind=kind;
  if(art.getAttribute('src')!==url){clearTimeout(heroTimer);art.src=url;if(!reduceMotion.matches){art.classList.add('refreshing');heroTimer=setTimeout(()=>art.classList.remove('refreshing'),30);}else art.classList.remove('refreshing');}
 }
 ports.forEach(port=>{
  const el=document.createElement('button');el.className='source';el.type='button';el.dataset.port=port.number;
  el.innerHTML='<img class="poster" alt="" aria-hidden="true"><span class="source-label"></span><span class="port-label"></span><span class="current-badge">Current</span>';
  el.addEventListener('focus',()=>{lastPort=port.number;renderHero();});
  el.addEventListener('click',()=>{if(!port.connected)return;const follow=eligible()?selectedProfile():null,changed=current!==port.number;current=port.number;if(changed&&follow&&eligible())picture().value=levels()[follow];render();notify(`Preview: selected ${port.label}. On TV, Cove returns to the HDMI picture.`);});
  sources.push(el);$('.sources').append(el);
  const row=document.createElement('div');row.className='simulation-row';row.dataset.simulationPort=port.number;
  const label=document.createElement('label');label.textContent=`HDMI ${port.number}`;
  const input=document.createElement('input');input.value=port.label;input.maxLength=32;input.setAttribute('aria-label',`HDMI ${port.number} preview name`);input.addEventListener('input',()=>{port.label=input.value.trim()||`HDMI ${port.number}`;render();});label.append(input);row.append(label);
  ['connected','sleep'].forEach(kind=>{const button=document.createElement('button');button.type='button';button.dataset.sim=kind;button.setAttribute('aria-label',`${kind==='connected'?'Connection':'Sleep state'} for HDMI ${port.number}`);button.addEventListener('click',()=>{if(kind==='connected')port.connected=!port.connected;else port.awake=!port.awake;render();simulationRows();});row.append(button);});$('#simulation-ports').append(row);
 });
 function simulationRows(){ports.forEach(port=>{const row=$(`[data-simulation-port="${port.number}"]`);row.querySelector('input').value=port.label;const conn=row.querySelector('[data-sim="connected"]'),sleep=row.querySelector('[data-sim="sleep"]');conn.textContent=port.connected?'Connected':'Unplugged';conn.setAttribute('aria-pressed',String(port.connected));sleep.textContent=port.awake?'Awake':'Sleeping';sleep.setAttribute('aria-pressed',String(!port.awake));});}
 utility.forEach(el=>el.addEventListener('focus',renderHero));
 utility.slice(1,3).forEach(el=>el.addEventListener('click',()=>{if(el.getAttribute('aria-disabled')==='true'){notify('Brightness is unavailable for the current picture.');return;}picture().value=levels()[el.id];levels().selected=el.id;render();}));
 function scopeLabel(){return pictureScope==='all'?'All sources':pictureScope==='current'?'Current source':'Scope unavailable';}
 function drawBrightness(){const value=Number(brightnessRange.value);$('#brightness-title').textContent=brightnessDraft?.profile?`${brightnessDraft.profile==='day'?'Bright':'Dim'} level`:'Brightness';$('#brightness-value').textContent=value;$('#brightness-fill').style.transform=`scaleX(${value/50})`;$('#scope-current').setAttribute('aria-pressed',String(pictureScope==='current'));$('#scope-all').setAttribute('aria-pressed',String(pictureScope==='all'));for(const button of [$('#scope-current'),$('#scope-all')]){button.hidden=!picture().scopeAvailable;button.setAttribute('aria-disabled',String(!picture().scopeAvailable));}$('#scope-readonly').hidden=picture().scopeAvailable;$('#scope-readonly').textContent=scopeLabel();brightnessRange.setAttribute('aria-label',$('#brightness-title').textContent);brightnessRange.setAttribute('aria-valuetext',`${value} of 50, ${scopeLabel()}`);}
 function chooseScope(scope){if(!picture().scopeAvailable||!brightnessDraft||brightnessDraft.source!==current||brightnessDraft.mode!==picture().mode||brightnessDraft.scope!==pictureScope||!['current','all'].includes(scope))return;pictureScope=scope;brightnessDraft.scope=scope;brightnessDraft.profile=selectedProfile();drawBrightness();}
 $('#scope-current').addEventListener('click',()=>chooseScope('current'));$('#scope-all').addEventListener('click',()=>chooseScope('all'));
 function adjustBrightness(){if(!brightnessDraft)return;const valid=brightnessDraft.source===current&&brightnessDraft.mode===picture().mode&&brightnessDraft.scope===pictureScope&&$('#brightness').getAttribute('aria-disabled')!=='true';if(!valid){closeBrightness();return;}picture().value=Number(brightnessRange.value);if(brightnessDraft.profile){levels()[brightnessDraft.profile]=picture().value;levels().selected=brightnessDraft.profile;}else levels().selected=null;$('#brightness-current').textContent=picture().value;utility.slice(1,3).forEach(el=>el.setAttribute('aria-pressed',String(el.id===selectedProfile())));drawBrightness();}
 function closeBrightness(){if(!brightnessDraft)return;brightnessDraft=null;brightnessPanel.hidden=true;for(const el of home.children)el.inert=false;$('#brightness').setAttribute('aria-expanded','false');$('#brightness').focus();render();}
 $('#brightness').addEventListener('click',()=>{if($('#brightness').getAttribute('aria-disabled')==='true'){notify(pictureScope===null?'Picture settings scope is unavailable. Try again.':'Unavailable for this input.');return;}brightnessDraft={source:current,mode:picture().mode,scope:pictureScope,profile:selectedProfile()};brightnessRange.value=picture().value;drawBrightness();brightnessPanel.hidden=false;for(const el of home.children)el.inert=el!==brightnessPanel;$('#brightness').setAttribute('aria-expanded','true');brightnessRange.focus();});
 brightnessRange.addEventListener('input',adjustBrightness);document.addEventListener('pointerdown',e=>{if(brightnessDraft&&!brightnessPanel.contains(e.target))closeBrightness();});
 $('#settings').addEventListener('click',()=>notify('Preview: opens Samsung picture & sound settings directly.'));
 function open(){opener=document.activeElement;simulation.hidden=false;home.inert=true;home.setAttribute('aria-hidden','true');$('#close-simulation').focus();}
 function close(){simulation.hidden=true;home.inert=false;home.removeAttribute('aria-hidden');const target=opener&&!opener.hidden?opener:sources.find(el=>Number(el.dataset.port)===lastPort&&!el.hidden)||$('#settings');target.focus();}
 $('#open-simulation').addEventListener('click',open);$('#close-simulation').addEventListener('click',close);simulation.addEventListener('click',e=>{if(e.target===simulation)close();});$('#simulate-unknown').addEventListener('click',()=>notify('Preview: read unavailable; last known connections retained.'));
 window.previewPictureContext=Object.freeze({get:()=>({source:current,...picture(),scope:pictureScope,pending:picturePending,profile:selectedProfile(),levels:{...levels()}}),set:state=>{const before={source:current,mode:picture().mode,value:picture().value,pending:picturePending};if(typeof state.pending==='boolean')picturePending=state.pending;if(Number.isInteger(state.source)&&state.source>=1&&state.source<=4)current=state.source;if(typeof state.mode==='string')picture().mode=state.mode;if(!picturePending&&Number.isInteger(state.value)&&state.value>=0&&state.value<=50)picture().value=state.value;if(!before.pending&&!picturePending&&before.source===current&&before.mode===picture().mode&&before.value!==picture().value)levels().selected=null;render();}});
 window.previewPictureScope=Object.freeze({setCurrentSource:enabled=>{pictureScope=enabled===true?'current':'all';render();},set:scope=>{pictureScope=['current','all'].includes(scope)?scope:null;render();}});
 window.previewInputs=Object.freeze({get:()=>ports.map(p=>({...p})),update:(number,state)=>{const port=ports.find(p=>p.number===number);if(!port)throw new RangeError('Preview port must be 1–4');if(typeof state.connected==='boolean')port.connected=state.connected;if(typeof state.awake==='boolean')port.awake=state.awake;if(typeof state.label==='string')port.label=state.label.trim().slice(0,32)||`HDMI ${number}`;render();simulationRows();}});
 document.addEventListener('keydown',e=>{
  const key=e.key,editing=document.activeElement?.tagName==='INPUT';
  if(brightnessDraft){
   if(key==='Escape'||key==='Backspace'||e.keyCode===10009){e.preventDefault();closeBrightness();return;}
   const choices=picture().scopeAvailable?[brightnessRange,$('#scope-current'),$('#scope-all')]:[brightnessRange],scopeFocused=choices.slice(1).includes(document.activeElement);
   if(key==='Enter'){e.preventDefault();if(!e.repeat){if(scopeFocused)document.activeElement.click();else closeBrightness();}return;}
   if(key==='ArrowLeft'||key==='ArrowRight'){e.preventDefault();if(scopeFocused)choices[key==='ArrowRight'?2:1].focus();else{brightnessRange.value=Math.max(0,Math.min(50,Number(brightnessRange.value)+(key==='ArrowRight'?1:-1)));adjustBrightness();}return;}
   if(key==='ArrowDown'){e.preventDefault();(choices[pictureScope==='current'?1:2]||brightnessRange).focus();return;}
   if(key==='ArrowUp'){e.preventDefault();brightnessRange.focus();return;}
   if(key==='Tab'){e.preventDefault();const i=choices.indexOf(document.activeElement);choices[(i+(e.shiftKey?-1:1)+choices.length)%choices.length].focus();return;}
   if(key.startsWith('Arrow'))e.preventDefault();return;
  }
  if(key==='Enter'&&e.repeat){e.preventDefault();return;}
  if(key.toLowerCase()==='i'&&!editing&&simulation.hidden){e.preventDefault();open();return;}
  if((key==='Escape'||key==='Backspace'||e.keyCode===10009)&&!(editing&&key==='Backspace')){e.preventDefault();if(!simulation.hidden)close();else{$('#toast').hidden=true;(sources.find(el=>Number(el.dataset.port)===lastPort&&!el.hidden)||$('#settings')).focus();}return;}
  if(!simulation.hidden){if(key==='Tab'||key==='ArrowDown'||key==='ArrowUp'){e.preventDefault();const choices=Array.from(simulation.querySelectorAll('button,input')),i=choices.indexOf(document.activeElement),direction=key==='ArrowUp'||key==='Tab'&&e.shiftKey?-1:1;choices[(i+direction+choices.length)%choices.length].focus();}return;}
  if(!key.startsWith('Arrow'))return;e.preventDefault();const visible=connected(),active=document.activeElement,row=visible.includes(active)?visible:utility.includes(active)?utility:visible,index=Math.max(0,row.indexOf(active));
  if(!row.length){$('#settings').focus();return;}
  if(key==='ArrowLeft'||key==='ArrowRight')row[Math.max(0,Math.min(row.length-1,index+(key==='ArrowRight'?1:-1)))].focus();
  else if(key==='ArrowUp'&&row===visible)utility[Math.min(index,utility.length-1)].focus();
  else if(key==='ArrowDown'&&row===utility&&visible.length)(visible.find(el=>Number(el.dataset.port)===lastPort)||visible[0]).focus();
 });
 window.addEventListener('resize',fit);fit();render();simulationRows();sources[0].focus({preventScroll:true});
})();
