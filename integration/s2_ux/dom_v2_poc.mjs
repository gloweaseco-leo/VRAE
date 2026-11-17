// OFFLINE POC ONLY. Never imported by the application, pack or rule executor.
// A producer label/hash is consistency metadata, never signed provenance.
import assert from 'node:assert/strict';

export const PRODUCER='c2-rich-dom-offline-poc-1';
export const SCRIPT=`(()=>{
  const all=[...document.querySelectorAll('h1,h2,a,button,input,img')];
  const num=n=>Math.round(n*100)/100;
  return {producer:'${PRODUCER}',poc_only:true,authority:'NONE_NO_EV_REF',url:location.href,
    viewport:{width:innerWidth,height:innerHeight,clientWidth:document.documentElement.clientWidth,
      scrollWidth:document.documentElement.scrollWidth},truncated:all.length>128,
    elements:all.slice(0,128).map((e,index)=>{
      const r=e.getBoundingClientRect(),s=getComputedStyle(e);
      const x=Math.max(0,Math.min(innerWidth-1,r.x+r.width/2)),y=Math.max(0,Math.min(innerHeight-1,r.y+r.height/2));
      const inViewport=r.width>0&&r.height>0&&r.x+r.width>0&&r.y+r.height>0&&r.x<innerWidth&&r.y<innerHeight;
      const hit=inViewport?document.elementFromPoint(x,y):null;
      return {index,tag:e.tagName,text:(e.textContent||'').slice(0,160),
        href:e.tagName==='A'?(e.getAttribute('href')||'').slice(0,2048):null,
        rect:{x:num(r.x),y:num(r.y),width:num(r.width),height:num(r.height)},
        style:{display:s.display,visibility:s.visibility,opacity:s.opacity},
        disabled:!!e.disabled,inert:!!e.closest('[inert]'),inViewport,
        centerHit:!!hit&&(hit===e||e.contains(hit)),
        image:e.tagName==='IMG'?{src:(e.getAttribute('src')||'').slice(0,2048),
          alt:e.getAttribute('alt')===null?null:e.getAttribute('alt').slice(0,256),
          complete:e.complete,naturalWidth:e.naturalWidth}:null};
    })};
})()`;

export function validatePoc(value, expectedUrl, expectedWidth){
  const keys=(v,k)=>assert.deepEqual(Object.keys(v).sort(),k.split(' ').sort());
  keys(value,'producer poc_only authority url viewport capture_viewport truncated elements');
  assert.equal(value.producer,PRODUCER);assert.equal(value.poc_only,true);
  assert.equal(value.authority,'NONE_NO_EV_REF');assert.equal(value.url,expectedUrl);
  // Mobile Chrome can expand its layout viewport to overflowing content.
  // The capture configuration and measured CSS viewport are distinct facts.
  keys(value.capture_viewport,'width height');
  assert.equal(value.capture_viewport.width,expectedWidth);
  assert(Number.isFinite(value.capture_viewport.height)&&value.capture_viewport.height>0);
  keys(value.viewport,'width height clientWidth scrollWidth');
  assert(Object.values(value.viewport).every(x=>Number.isFinite(x)&&x>=0));
  assert(Array.isArray(value.elements)&&value.elements.length<=128);
  for(const [index,e] of value.elements.entries()){
    keys(e,'index tag text href rect style disabled inert inViewport centerHit image');
    assert.equal(e.index,index);assert(['H1','H2','A','BUTTON','INPUT','IMG'].includes(e.tag));
    assert(typeof e.text==='string'&&e.text.length<=160);
    assert(e.href===null||typeof e.href==='string'&&e.href.length<=2048);
    keys(e.rect,'x y width height');assert(Object.values(e.rect).every(Number.isFinite));
    keys(e.style,'display visibility opacity');
    for(const k of ['disabled','inert','inViewport','centerHit'])assert.equal(typeof e[k],'boolean');
    if(e.image!==null){keys(e.image,'src alt complete naturalWidth');assert.equal(e.tag,'IMG');
      assert(typeof e.image.src==='string'&&e.image.src.length<=2048);
      assert(e.image.alt===null||typeof e.image.alt==='string'&&e.image.alt.length<=256);
      assert.equal(typeof e.image.complete,'boolean');assert(Number.isFinite(e.image.naturalWidth)&&e.image.naturalWidth>=0);
    }
  }
  return value; // Still no source authority, Observation or production finding.
}
