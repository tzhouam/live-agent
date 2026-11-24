import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {inflateSync} from 'node:zlib';
import {teacherState,armJoints,handSpec,handPose,segmentTransform,deformHead,expressionAlphas,deformArm,GESTURES} from '../public/assets/teacher-rig.js';
const rig=JSON.parse(readFileSync(new URL('../public/assets/teacher-mesh/rig-v2.json',import.meta.url)));
const adultRig=JSON.parse(readFileSync(new URL('../public/assets/teacher-mesh/rig-v3.json',import.meta.url)));
const registeredRig=JSON.parse(readFileSync(new URL('../public/assets/teacher-mesh/rig-v4.json',import.meta.url)));
const proportionedRig=JSON.parse(readFileSync(new URL('../public/assets/teacher-mesh/rig-v5.json',import.meta.url)));
const enlargedRig=JSON.parse(readFileSync(new URL('../public/assets/teacher-mesh/rig-v6.json',import.meta.url)));

// Read the actual RGBA runtime tiles, rather than trusting extraction metadata.
// Keeping alpha lets the bounds checks include fingers and exclude blank corners.
const pngCache=new Map();
function png(asset){
 if(pngCache.has(asset))return pngCache.get(asset);
 const bytes=readFileSync(new URL('../public/assets/teacher-mesh/'+asset,import.meta.url));
 assert.equal(bytes.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
 let width,height;const chunks=[];
 for(let offset=8;offset<bytes.length;){
  const length=bytes.readUInt32BE(offset),type=bytes.toString('ascii',offset+4,offset+8),data=bytes.subarray(offset+8,offset+8+length);
  if(type==='IHDR'){
   width=data.readUInt32BE(0);height=data.readUInt32BE(4);
   assert.deepEqual([...data.subarray(8)],[8,6,0,0,0],'Runtime tiles must remain noninterlaced RGBA8');
  }
  if(type==='IDAT')chunks.push(data);
  offset+=length+12;
 }
 const raw=inflateSync(Buffer.concat(chunks)),stride=width*4,pixels=Buffer.alloc(stride*height);
 assert.equal(raw.length,(stride+1)*height);
 const paeth=(a,b,c)=>{const p=a+b-c,pa=Math.abs(p-a),pb=Math.abs(p-b),pc=Math.abs(p-c);return pa<=pb&&pa<=pc?a:pb<=pc?b:c;};
 for(let y=0;y<height;y++){
  const filter=raw[y*(stride+1)];assert.ok(filter<=4);
  for(let x=0;x<stride;x++){
   const a=x>=4?pixels[y*stride+x-4]:0,b=y?pixels[(y-1)*stride+x]:0,c=y&&x>=4?pixels[(y-1)*stride+x-4]:0;
   const predictor=filter===0?0:filter===1?a:filter===2?b:filter===3?Math.floor((a+b)/2):paeth(a,b,c);
   pixels[y*stride+x]=(raw[y*(stride+1)+1+x]+predictor)&255;
  }
 }
 const image={width,height,pixels};pngCache.set(asset,image);return image;
}
function inPolygon(x,y,polygon){
 if(!polygon)return true;
 let inside=false;
 for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
  const [xi,yi]=polygon[i],[xj,yj]=polygon[j];
  if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi)inside=!inside;
 }
 return inside;
}
function hull(points){
 const sorted=points.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
 const cross=(o,a,b)=>(a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0]);
 const half=list=>{const out=[];for(const point of list){while(out.length>=2&&cross(out.at(-2),out.at(-1),point)<=0)out.pop();out.push(point);}return out;};
 return [...half(sorted).slice(0,-1),...half([...sorted].reverse()).slice(0,-1)];
}
const silhouetteCache=new Map();
function handSilhouette(spec){
 const key=JSON.stringify([spec.asset,spec.size,spec.anchor,spec.skin_mask]);
 if(silhouetteCache.has(key))return silhouetteCache.get(key);
 const image=png(spec.asset),points=[];
 for(let y=0;y<image.height;y++){
  let first=-1,last=-1;
  for(let x=0;x<image.width;x++){
   if(image.pixels[(y*image.width+x)*4+3]>0&&inPolygon((x+.5)/image.width,(y+.5)/image.height,spec.skin_mask)){
    if(first<0)first=x;last=x;
   }
  }
  if(first>=0)for(const x of [first,last])points.push([
   ((x+.5)/image.width-spec.anchor[0])*spec.size[0],
   ((y+.5)/image.height-spec.anchor[1])*spec.size[1]]);
 }
 assert.ok(points.length,`${spec.asset} has no visible skin`);
 const outline=hull(points);silhouetteCache.set(key,outline);return outline;
}
function projectedHand(model,side,pose,name){
 const {rotation}=pose.shapes[name],cos=Math.cos(rotation),sin=Math.sin(rotation);
 const scale=model.camera?.scale??1,pivot=model.camera?.pivot??[0,0];
 const spec=handSpec(model,name,side);
 return handSilhouette(spec).map(([x,y])=>{
  x*=spec.mirror?-1:1;
  const wx=pose.wrist[0]+x*cos-y*sin,wy=pose.wrist[1]+x*sin+y*cos;
  return [pivot[0]+(wx-pivot[0])*scale,pivot[1]+(wy-pivot[1])*scale];
 });
}
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);

test('every supported gesture keeps connected bone anchors and hands on stage',()=>{
 for(const gesture of GESTURES)for(let i=0;i<=120;i++){
  const state=teacherState({gesture,requestTime:i/24,duration:5,motionTime:i/24,mouthOpen:.5},rig);
  for(const part of rig.layers.filter(p=>p.group==='arm')){
   const [, ,w,h]=part.rect, points=part.anchors.flatMap(([x,y])=>[x*w,y*h]);
   const joints=armJoints(rig,part.side,state),warped=deformArm(points,w,h,part.anchors,joints);
   for(let j=0;j<3;j++)for(let k=0;k<2;k++)assert.ok(Math.abs(warped[j*2+k]-joints[j][k])<1e-4);
   const armIndex=part.side>0?0:1,shoulder=rig.arms.shoulders[armIndex],restElbow=rig.arms.elbows[armIndex];
   const length=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
   assert.ok(Math.abs(length(joints[0],joints[1])-length(shoulder,restElbow))<1e-9);
   assert.ok(Math.abs(length(joints[1],joints[2])-rig.arms.forearm_length)<1e-9);
   // The outward board point reserves room for its authored finger silhouette.
   const minY=gesture==='wave'?350:gesture==='think'?385:450;
   assert.ok(joints[2][0]>60&&joints[2][0]<(gesture==='point'?440:420)&&joints[2][1]>minY&&joints[2][1]<650);
  }
 }
});
test('gesture rests agree at request boundaries and oscillation fades continuously',()=>{
 for(const gesture of GESTURES){
  const a=teacherState({gesture,requestTime:0,duration:5,motionTime:5},rig);
  const b=teacherState({gesture,requestTime:5,duration:5,motionTime:5},rig);
  assert.equal(a.angle,b.angle);assert.equal(a.upperAngle,b.upperAngle);assert.equal(a.palm,b.palm);assert.equal(a.weight,0);
  let last=armJoints(rig,1,a)[2];
  for(let i=1;i<=120;i++){
   const now=armJoints(rig,1,teacherState({gesture,requestTime:i/24,duration:5,motionTime:i/24},rig))[2];
   assert.ok(Math.hypot(now[0]-last[0],now[1]-last[1])<9);last=now;
  }
 }
});
test('wave lifts beside the face and thinking lifts toward the chin without hiding the face',()=>{
 const sample=gesture=>teacherState({gesture,requestTime:2.5,duration:5,motionTime:2.5},rig);
 const wave=armJoints(rig,1,sample('wave')),think=armJoints(rig,1,sample('think'));
 // Configuration targets: a relaxed outward elbow, vertical wrist beside the
 // shoulder, and enough clearance for the authored palm to stay outside hair.
 assert.ok(wave[1][0]>400&&wave[1][0]<430);
 assert.ok(wave[1][1]>460&&wave[1][1]<490);
 assert.ok(wave[2][0]>375&&wave[2][0]<420);
 assert.ok(wave[2][1]>350&&wave[2][1]<400);
 // The thinking fingertip is directed toward the chin but stays below the face.
 assert.ok(think[2][0]>270&&think[2][0]<300);
 assert.ok(think[2][1]>385&&think[2][1]<405);
 const fingertipBound=think[2][1]-rig.hands.point.size[1]*rig.hands.point.anchor[1];
 assert.ok(fingertipBound>338&&fingertipBound<365);
 assert.notDeepEqual(think,armJoints(rig,1,sample('explain')));
 for(const gesture of ['wave','think']){
  assert.deepEqual(armJoints(rig,-1,sample(gesture)),armJoints(rig,-1,sample('idle')));
 }
});
test('lifted gestures follow the request clock and settle independently of chunk boundaries',()=>{
 for(const gesture of ['wave','think']){
  for(const time of [.5,1.25,2.5,3.75,4.5]){
   const a=teacherState({gesture,requestTime:time,duration:5,motionTime:20+time},rig);
   const b=teacherState({gesture,requestTime:(time-.5)+.5,duration:5,motionTime:19.5+.5+time},rig);
   assert.deepEqual(armJoints(rig,1,a),armJoints(rig,1,b));
  }
  for(const end of [0,5]){
   const s=teacherState({gesture,requestTime:end,duration:5,motionTime:20+end},rig);
   assert.ok(s.upperAngle===0);
   assert.deepEqual(armJoints(rig,1,s),armJoints(rig,1,teacherState({gesture:'idle'},rig)));
  }
  // Oscillation has an independent session clock; its phase cannot introduce a
  // jump at another request's start or exceed the motion step target.
  for(const origin of [0,4.5,12.5,22.5]){
   let last=null;
   for(let frame=0;frame<=120;frame++){
    const time=frame/24;
    const wrist=armJoints(rig,1,teacherState({gesture,requestTime:time,duration:5,motionTime:origin+time},rig))[2];
    if(last)assert.ok(Math.hypot(wrist[0]-last[0],wrist[1]-last[1])<9);
    last=wrist;
   }
  }
 }
});
test('request continuation shares blink, breath and gesture clock across chunks',()=>{
 const input={gesture:'explain',requestTime:2.5,duration:5,motionTime:19.7,mouthOpen:.6};
 const fromFirst=teacherState(input,rig);
 const fromSecond=teacherState({...input,requestTime:1.25+1.25,motionTime:18.45+1.25},rig);
 assert.deepEqual(fromFirst,fromSecond);
});
test('silent reset closes lips and unknown gestures use a calm idle',()=>{
 assert.equal(teacherState({gesture:'idle',mouthOpen:0},rig).mouth,0);
 assert.equal(teacherState({gesture:'drink'},rig).gesture,'idle');
 assert.equal(teacherState({mouthOpen:99},rig).mouth,1);
});

test('adult artwork keeps every real runtime tile at its authored aspect ratio',()=>{
 for(const layer of adultRig.layers){
  const image=png(layer.asset),[,,w,h]=layer.rect;
  assert.ok(Math.abs((w/h)/(image.width/image.height)-1)<1e-10,`${layer.id} stretches the source artwork`);
  assert.deepEqual(adultRig.extraction[layer.id].size,[image.width,image.height],`${layer.id} extraction dimensions are stale`);
 }
 for(const [name,hand] of Object.entries(adultRig.hands)){
  const image=png(hand.asset);
  assert.ok(Math.abs((hand.size[0]/hand.size[1])/(image.width/image.height)-1)<1e-10,`${name} stretches the source hand`);
 }
 // Art-direction regression targets, not a claim of measured human anatomy:
 // the hair silhouette must leave substantial shoulder width on both sides.
 const hair=adultRig.layers.find(part=>part.id==='front-hair');
 const shoulderSpan=distance(...adultRig.arms.shoulders),headWidth=hair.rect[2]*adultRig.head_scale;
 assert.ok(headWidth/shoulderSpan<.75,'Head/hair has regressed toward the oversized doll silhouette');
 assert.ok(adultRig.arms.forearm_length/distance(adultRig.arms.shoulders[0],adultRig.arms.elbows[0])>.7,
   'Forearms have regressed toward miniature arms');
});

test('adult shoulders and cuffs attach inside real painted overlap',()=>{
 const body=adultRig.layers.find(part=>part.id==='body'),image=png(body.asset);
 function opaqueNear(tile,x,y,radius=3){
  for(let yy=Math.max(0,Math.floor(y-radius));yy<=Math.min(tile.height-1,Math.ceil(y+radius));yy++)
   for(let xx=Math.max(0,Math.floor(x-radius));xx<=Math.min(tile.width-1,Math.ceil(x+radius));xx++)
    if(tile.pixels[(yy*tile.width+xx)*4+3]>=64)return true;
  return false;
 }
 for(const part of adultRig.layers.filter(part=>part.group==='arm')){
  const side=part.side>0?0:1,[sx,sy]=adultRig.arms.shoulders[side];
  assert.ok(opaqueNear(image,(sx-body.rect[0])*image.width/body.rect[2],(sy-body.rect[1])*image.height/body.rect[3]),
   `${part.id} shoulder is outside painted torso overlap`);
  const sleeve=png(part.asset);
  for(const [name,anchor] of [['shoulder',part.anchors[0]],['elbow',part.anchors[1]],['cuff',part.anchors[2]]])
   assert.ok(opaqueNear(sleeve,anchor[0]*sleeve.width,anchor[1]*sleeve.height),`${part.id} ${name} is outside painted sleeve`);
 }
 for(const [name,hand] of Object.entries(adultRig.hands)){
  const tile=png(hand.asset);
  assert.ok(opaqueNear(tile,hand.anchor[0]*tile.width,hand.anchor[1]*tile.height),`${name} wrist is detached from skin`);
  assert.ok(inPolygon(...hand.anchor,hand.skin_mask),`${name} mask removes the wrist attachment`);
 }
});

test('adult gestures keep fixed shoulders and constant connected bone lengths',()=>{
 assert.deepEqual(new Set(adultRig.supported_gestures),GESTURES);
 for(const gesture of GESTURES)for(const duration of [1.8,5,12])for(let frame=0;frame<=120;frame++){
  const time=duration*frame/120,state=teacherState({gesture,requestTime:time,duration,motionTime:20+time},adultRig);
  for(const part of adultRig.layers.filter(part=>part.group==='arm')){
   const index=part.side>0?0:1,joints=armJoints(adultRig,part.side,state),[,,w,h]=part.rect;
   assert.deepEqual(joints[0],adultRig.arms.shoulders[index],`${gesture} moves its shoulder away from the torso`);
   assert.ok(Math.abs(distance(joints[0],joints[1])-distance(adultRig.arms.shoulders[index],adultRig.arms.elbows[index]))<1e-8);
   assert.ok(Math.abs(distance(joints[1],joints[2])-adultRig.arms.forearm_length)<1e-8);
   const anchors=part.anchors.flatMap(([x,y])=>[x*w,y*h]),warped=deformArm(anchors,w,h,part.anchors,joints);
   for(let joint=0;joint<3;joint++)assert.ok(distance([...warped.slice(joint*2,joint*2+2)],joints[joint])<1e-4,
    `${gesture} ${part.id} mesh separates at joint ${joint}`);
   for(const [x,y] of joints)assert.ok(x>0&&x<adultRig.canvas[0]&&y>0&&y<adultRig.canvas[1],`${gesture} bone leaves the viewport`);
  }
 }
});

test('full adult hand alpha silhouettes stay clear of every canvas edge through complete gestures',t=>{
 // Configuration target: 8 native pixels of clearance, beyond texture filtering.
 // Actual alpha and skin masks matter; the wrist alone can be inside while a
 // pointing finger clips. A convex hull gives exact affine silhouette extrema.
 const margin=8,extrema={left:Infinity,right:-Infinity,top:Infinity,bottom:-Infinity};
 for(const gesture of GESTURES)for(const origin of [0,4.5,12.5,22.5])for(const duration of [1.8,5,12]){
  const frames=Math.ceil(duration*24);
  for(let frame=0;frame<=frames;frame++){
   const time=duration*frame/frames,input={gesture,requestTime:time,duration,motionTime:origin+time};
   const state=teacherState(input,adultRig);
   for(const side of [1,-1]){
    const pose=handPose(adultRig,side,state,input);
    for(const [name,shape] of Object.entries(pose.shapes))if(shape.alpha>1/255){
     for(const [x,y] of projectedHand(adultRig,side,pose,name)){
      extrema.left=Math.min(extrema.left,x);extrema.right=Math.max(extrema.right,x);
      extrema.top=Math.min(extrema.top,y);extrema.bottom=Math.max(extrema.bottom,y);
      assert.ok(x>=margin&&x<=adultRig.canvas[0]-margin&&y>=margin&&y<=adultRig.canvas[1]-margin,
       `${gesture}/${name} side=${side} duration=${duration} origin=${origin} t=${time.toFixed(3)} silhouette=(${x.toFixed(3)},${y.toFixed(3)}) violates ${margin}px canvas clearance`);
     }
    }
   }
  }
 }
 t.diagnostic(`Measured alpha silhouette extrema in native canvas units: ${JSON.stringify(extrema)}`);
});

test('adult wrists and visible hand outlines move continuously and return to the same rest pose',()=>{
 for(const gesture of GESTURES)for(const origin of [0,4.5,12.5,22.5]){
  let previous=null;
  for(let frame=0;frame<=300;frame++){
   const time=frame/60,input={gesture,requestTime:time,duration:5,motionTime:origin+time};
   const state=teacherState(input,adultRig),now=[1,-1].map(side=>handPose(adultRig,side,state,input));
   if(previous)for(let index=0;index<now.length;index++){
    // Configuration target: less than 5% of a forearm per 60-Hz frame.
    const stepLimit=adultRig.arms.forearm_length*.05,side=index===0?1:-1;
    assert.ok(distance(now[index].wrist,previous[index].wrist)<stepLimit,`${gesture} wrist jumps`);
    for(const name of Object.keys(now[index].shapes))if(now[index].shapes[name].alpha>1/255&&previous[index].shapes[name].alpha>1/255){
     const a=projectedHand(adultRig,side,previous[index],name),b=projectedHand(adultRig,side,now[index],name);
     for(let point=0;point<a.length;point++)assert.ok(distance(a[point],b[point])<stepLimit,`${gesture}/${name} visible outline jumps`);
    }
   }
   previous=now;
  }
  for(const time of [0,5])for(const side of [1,-1]){
   const input={gesture,requestTime:time,duration:5,motionTime:origin+time};
   const pose=handPose(adultRig,side,teacherState(input,adultRig),input);
   const idle=handPose(adultRig,side,teacherState({...input,gesture:'idle'},adultRig),input);
   assert.deepEqual(pose.wrist,idle.wrist);assert.deepEqual(pose.shapes.relaxed,idle.shapes.relaxed);
   assert.equal(pose.shapes.relaxed.alpha,1);
   assert.ok(Object.entries(pose.shapes).every(([name,shape])=>name==='relaxed'||shape.alpha===0));
  }
 }
});

function transformSectionPoint(transform,[x,y]){
 const cos=Math.cos(transform.rotation)*transform.scale,sin=Math.sin(transform.rotation)*transform.scale;
 return [transform.position[0]+x*cos-y*sin,transform.position[1]+x*sin+y*cos];
}
test('rigid arm sections preserve painted width, orientation and bone registration through every gesture',()=>{
 // Deliberately asymmetric source anchors catch implicit texture mirroring or
 // an assumed vertical bone. Source lighting must rotate with its own section.
 for(const side of [-1,1])for(const bone of ['upper','forearm']){
  const spec={side,bone,size:[52,145],anchors:side>0?[[.72,.09],[.26,.91]]:[[.28,.09],[.74,.91]]};
  const authored=spec.anchors.map(point=>point.map((value,index)=>value*spec.size[index]));
  const sourceTriangle=[[0,0],[52,0],[0,145]],index=bone==='upper'?0:1;
  let restScale;
  for(const gesture of GESTURES)for(let frame=0;frame<=120;frame++){
   const input={gesture,requestTime:frame/24,duration:5,motionTime:22.5+frame/24};
   const joints=armJoints(adultRig,side,teacherState(input,adultRig)),transform=segmentTransform(spec,joints);
   assert.ok(Number.isFinite(transform.rotation)&&transform.position.every(Number.isFinite));
   assert.ok(transform.determinant>0,'Painted sleeve flips inside out');
   for(let endpoint=0;endpoint<2;endpoint++)assert.ok(distance(transformSectionPoint(transform,authored[endpoint]),joints[index+endpoint])<1e-9,
    `${gesture}/${bone} misses its bone endpoint`);
   if(restScale===undefined)restScale=transform.scale;
   assert.ok(Math.abs(transform.scale-restScale)<1e-12,`${gesture}/${bone} changes sleeve width or length`);
   const target=sourceTriangle.map(point=>transformSectionPoint(transform,point));
   const signedArea=points=>(points[1][0]-points[0][0])*(points[2][1]-points[0][1])-(points[1][1]-points[0][1])*(points[2][0]-points[0][0]);
   assert.ok(signedArea(target)>0,`${gesture}/${bone} inverts visible cloth geometry`);
   assert.ok(Math.abs(signedArea(target)/signedArea(sourceTriangle)-transform.determinant)<1e-10);
   // A uniform transform preserves all painted angles and distances, not only
   // the endpoints that the previous continuous elbow warp already matched.
   for(const [a,b] of [[0,1],[1,2],[2,0]])assert.ok(Math.abs(distance(target[a],target[b])-distance(sourceTriangle[a],sourceTriangle[b])*restScale)<1e-9);
  }
 }
});

test('painted elbow overlap stays registered without a blended rotation or reflected texture',()=>{
 for(const side of [-1,1])for(const rotation of [0,.4]){
  const spec={side,bone:'elbow',size:[48,42],anchor:[.47,.53],rotation};
  for(const gesture of GESTURES){
   const input={gesture,requestTime:2.5,duration:5,motionTime:22.5};
   const joints=armJoints(adultRig,side,teacherState(input,adultRig)),transform=segmentTransform(spec,joints);
   assert.ok(distance(transformSectionPoint(transform,spec.anchor.map((value,index)=>value*spec.size[index])),joints[1])<1e-9);
   assert.equal(transform.scale,1);assert.equal(transform.determinant,1);assert.equal(transform.rotation,rotation);
  }
 }
});

test('invalid painted arm registration fails before it can produce NaN or folded geometry',()=>{
 const joints=[[100,100],[110,220],[105,330]],valid={bone:'upper',size:[50,140],anchors:[[.5,.1],[.5,.9]]};
 for(const spec of [
  {...valid,size:[0,140]}, {...valid,size:[50,NaN]}, {...valid,bone:'unknown'},
  {...valid,anchors:[[.5,.5],[.5,.5]]}, {...valid,anchors:[[.5,-.1],[.5,.9]]},
  {bone:'elbow',size:[48,48],anchor:[2,.5]}, {bone:'elbow',size:[48,48],rotation:NaN}
 ])assert.throws(()=>segmentTransform(spec,joints));
 assert.throws(()=>segmentTransform(valid,[[100,100],[100,100],[105,330]]));
 assert.throws(()=>segmentTransform(valid,[[100,100],[NaN,220],[105,330]]));
});

test('coherent painted heads and registered facial patches keep identical landmark coordinates in motion',()=>{
 const model={...adultRig,coherent_head:true,jaw_width:.08};
 const base={id:'face',rect:[140,180,200,260]};
 const patches=[
  {id:'lids',rect:[185,288,105,28],landmark:[210,302]},
  {id:'eyes',rect:[185,288,105,28],landmark:[220,300]},
  {id:'mouth-a',rect:[212,318,42,34],landmark:[225,330]},
  {id:'front-hair',rect:[130,160,220,300],landmark:[235,250]}
 ];
 for(const gesture of GESTURES)for(let frame=0;frame<=120;frame++){
  const state=teacherState({gesture,requestTime:frame/24,duration:5,motionTime:frame/24,mouthOpen:.8},model);
  state.hair=2.6; // Strong hair input must not slide intact artwork off patches.
  for(const patch of patches){
   const original=new Float32Array([patch.landmark[0]-patch.rect[0],patch.landmark[1]-patch.rect[1]]);
   const parent=new Float32Array([patch.landmark[0]-base.rect[0],patch.landmark[1]-base.rect[1]]);
   const out=new Float32Array(2);
   assert.equal(deformHead(original,...patch.rect.slice(2),patch,state,model,out),out);
   const baseOut=deformHead(parent,...base.rect.slice(2),base,state,model);
   assert.deepEqual(out,original,`${gesture}/${patch.id} distorts an intact painted feature`);
   assert.deepEqual([out[0]+patch.rect[0],out[1]+patch.rect[1]],[baseOut[0]+base.rect[0],baseOut[1]+base.rect[1]],
    `${gesture}/${patch.id} slides away from the same landmark on the base head`);
   assert.deepEqual(original,new Float32Array([patch.landmark[0]-patch.rect[0],patch.landmark[1]-patch.rect[1]]));
  }
 }
});

test('legacy head deformation remains active unless coherent_head is explicitly true',()=>{
 const vertices=new Float32Array([20,10,50,35]),copy=vertices.slice();
 const state={turn:.5,hair:2,gazeX:.4,gazeY:-.2,smile:.7},spec={id:'mouth-a'};
 const legacy=deformHead(vertices,80,50,spec,state,adultRig);
 assert.notDeepEqual(legacy,vertices);
 assert.deepEqual(deformHead(vertices,80,50,spec,state,{...adultRig,coherent_head:false}),legacy);
 assert.deepEqual(deformHead(vertices,80,50,spec,state,{...adultRig,coherent_head:true}),vertices);
 assert.deepEqual(vertices,copy,'Deformation must not mutate source coordinates');
});

test('authored left and right hands resolve their own artwork and wrist registration without mirroring',()=>{
 const model={...adultRig,hands:{...adultRig.hands,relaxed:{...adultRig.hands.relaxed,sides:{
  '1':{asset:'right-rest.png',size:[64,52],anchor:[.55,.12],rest_rotation:.21,rotation_offset:.08,contact_shadow:false},
  '-1':{asset:'left-rest.png',size:[61,49],anchor:[.43,.15],rest_rotation:-.17,rotation_offset:-.04,contact_shadow:true}
 }}}};
 const right=handSpec(model,'relaxed',1),left=handSpec(model,'relaxed',-1);
 assert.equal(right.asset,'right-rest.png');assert.equal(left.asset,'left-rest.png');
 assert.deepEqual(right.size,[64,52]);assert.deepEqual(left.anchor,[.43,.15]);
 assert.equal(right.mirror,false);assert.equal(left.mirror,false);
 assert.equal(right.contact_shadow,false);assert.equal(left.contact_shadow,true);
 assert.equal(handSpec(adultRig,'relaxed',-1).mirror,true,'Old left-hand tiles still require their original mirror');
 assert.equal(handSpec(adultRig,'relaxed',1).mirror,false);
 assert.equal(adultRig.hands.relaxed.asset,'relaxed-hand-v3.png','Resolving another side must not mutate old model artwork');
 const input={gesture:'idle',requestTime:0,duration:5,motionTime:0},state=teacherState(input,model);
 for(const [side,spec] of [[1,right],[-1,left]]){
  const [,elbow,wrist]=armJoints(model,side,state),axis=-Math.atan2(wrist[0]-elbow[0],wrist[1]-elbow[1]);
  assert.ok(Math.abs(handPose(model,side,state,input).shapes.relaxed.rotation-axis-spec.rest_rotation-spec.rotation_offset)<1e-12,
   'A separately painted left hand must use its authored wrist angle directly');
 }
});

test('canonical hand orientation overrides legacy shape corrections and rejects invalid rotations',()=>{
 const hands=Object.fromEntries(Object.entries(adultRig.hands).map(([name,spec])=>[name,{...spec,sides:{
  '1':{rotation_offset:0,wrist_flex:.12,skin_mask:null},'-1':{rotation_offset:0,wrist_flex:.12,skin_mask:null}
 }}]));
 const model={...adultRig,hands};
 for(const gesture of ['explain','point','think','wave']){
  const input={gesture,requestTime:2.5,duration:5,motionTime:22.5},state=teacherState(input,model);
  const [,elbow,wrist]=armJoints(model,1,state),axis=-Math.atan2(wrist[0]-elbow[0],wrist[1]-elbow[1]);
  const pose=handPose(model,1,state,input);
  for(const name of ['open','point'])assert.ok(Math.abs(pose.shapes[name].rotation-axis-.12*state.weight)<1e-12);
  assert.ok(Math.abs(pose.shapes.wave.rotation-axis-.12*state.weight-Math.sin(input.motionTime*5)*.07*state.weight)<1e-12);
  assert.equal(handSpec(model,'point',1).skin_mask,null,'New canonical fingers must not inherit an old sideways clipping mask');
 }
 const invalid={...model,hands:{...hands,point:{...hands.point,sides:{'1':{rotation_offset:NaN}}}}};
 assert.throws(()=>handSpec(invalid,'point',1));
});

test('registered expression patches select one fully painted eye and mouth shape without ghost blends',()=>{
 const model={expression_states:{mode:'registered-opaque'}};
 for(const blink of [0,.01,.149,.15,.3,.5,.749,.75,.9,1])
  for(const mouth of [0,.039,.04,.1,.359,.36,.6,1])for(const round of [0,.549,.55,.8,1]){
   const alpha=expressionAlphas({blink,mouth,round},model);
   assert.ok(Object.values(alpha).every(value=>value===0||value===1),'Edited features must never be partially transparent');
   assert.equal(alpha.eyes+alpha.lids+alpha['lids-half'],1,'One eye state is visible');
   assert.equal(alpha.lids,blink>=.75?1:0);
   assert.equal(alpha['lids-half'],blink>=.15&&blink<.75?1:0);
   assert.equal(alpha['mouth-neutral'],0,'The intact base supplies its neutral mouth');
   assert.equal(alpha['mouth-soft'],mouth>=.04&&mouth<.36?1:0);
   assert.equal(alpha['mouth-a'],mouth>=.36&&round<.55?1:0);
   assert.equal(alpha['mouth-o'],mouth>=.36&&round>=.55?1:0);
   assert.equal(alpha['mouth-soft']+alpha['mouth-a']+alpha['mouth-o'],mouth<.04?0:1,
    'Neutral stays on the base; a speaking patch completely replaces it');
  }
});

test('registered expression thresholds are configurable and also preserve facial patch geometry',()=>{
 const model={coherent_head:false,expression_states:{mode:'registered-opaque',blink_half_threshold:.2,
  blink_closed_threshold:.8,mouth_soft_threshold:.1,mouth_open_threshold:.5,mouth_round_threshold:.7}};
 assert.equal(expressionAlphas({blink:.19,mouth:.09,round:1},model).eyes,1);
 assert.equal(expressionAlphas({blink:.2,mouth:.1,round:1},model)['lids-half'],1);
 assert.equal(expressionAlphas({blink:.8,mouth:.499,round:1},model).lids,1);
 assert.equal(expressionAlphas({blink:1,mouth:.5,round:.699},model)['mouth-a'],1);
 assert.equal(expressionAlphas({blink:1,mouth:.5,round:.7},model)['mouth-o'],1);
 const vertices=new Float32Array([12,7,31,22]);
 assert.deepEqual(deformHead(vertices,44,32,{id:'mouth-o'},{turn:.5,smile:1,hair:2},model),vertices,
  'Opaque registered features must remain registered even if coherent_head was omitted');
 for(const invalid of [{blink_half_threshold:NaN},{blink_half_threshold:.9,blink_closed_threshold:.8},
  {mouth_soft_threshold:.5,mouth_open_threshold:.5},{mouth_round_threshold:2}])
  assert.throws(()=>expressionAlphas({blink:.5,mouth:.5,round:.5},{expression_states:{...model.expression_states,...invalid}}));
});

test('legacy eye and mouth alpha blending remains unchanged outside registered-opaque mode',()=>{
 const alpha=expressionAlphas({blink:.4,mouth:1,round:1},{});
 assert.deepEqual(alpha,{eyes:.6,lids:.4,'lids-half':0,'mouth-neutral':0,'mouth-soft':0,'mouth-a':.25,'mouth-o':.75});
 const partial=expressionAlphas({blink:.2,mouth:.2,round:.6},{});
 assert.ok(partial['mouth-neutral']>0&&partial['mouth-a']>0&&partial['mouth-o']>0);
 assert.ok(Math.abs(partial['mouth-neutral']+partial['mouth-a']+partial['mouth-o']-1)<1e-12);
});

test('actual registered face patches retain the intact source head coordinate system',()=>{
 const face=registeredRig.layers.find(part=>part.id==='face'),reference=png(face.asset);
 const source=registeredRig.extraction.face,scale=source.shared_source_scale_configuration;
 assert.equal(registeredRig.coherent_head,true);
 assert.equal(registeredRig.expression_states.mode,'registered-opaque');
 assert.deepEqual([reference.width,reference.height],source.size);
 for(let axis=0;axis<2;axis++)assert.ok(Math.abs(face.rect[axis+2]-source.size[axis]*scale)<1e-9,
  'The intact head must use the common source scale');
 const patches=['lids-half','lids','mouth-soft','mouth-a','mouth-o'];
 for(const id of patches){
  const part=registeredRig.layers.find(layer=>layer.id===id),meta=registeredRig.extraction[id],tile=png(part.asset);
  const [x0,y0,x1,y1]=meta.source_region;
  assert.deepEqual([tile.width,tile.height],[x1-x0,y1-y0],`${id} tile no longer matches its registered source crop`);
  assert.deepEqual(meta.source_size,source.size,`${id} uses a different source head canvas`);
  assert.equal(meta.shared_source_scale_configuration,scale,`${id} independently scales a facial feature`);
  const expected=[face.rect[0]+x0*scale,face.rect[1]+y0*scale,tile.width*scale,tile.height*scale];
  for(let coordinate=0;coordinate<4;coordinate++)assert.ok(Math.abs(part.rect[coordinate]-expected[coordinate])<1e-9,
   `${id} loses source registration at rectangle coordinate ${coordinate}`);
 }
});

function stageSilhouetteAudit(model){
 // Configuration target: retain 8 native pixels around every painted outline.
 // These checks measure geometry only; cloth style and believable joints still
 // require review of the actual renderer, including torso/desk occlusion.
 const margin=8,extrema={left:Infinity,right:-Infinity,top:Infinity,bottom:-Infinity},failures=[];
 const project=([x,y])=>{
  const scale=model.camera?.scale??1,pivot=model.camera?.pivot??[0,0];
  return [pivot[0]+(x-pivot[0])*scale,pivot[1]+(y-pivot[1])*scale];
 };
 const outlines=model.arm_segments.map(spec=>({spec,outline:handSilhouette({...spec,anchor:[0,0]})}));
 function check(points,label){
  for(const [x,y] of points){
   extrema.left=Math.min(extrema.left,x);extrema.right=Math.max(extrema.right,x);
   extrema.top=Math.min(extrema.top,y);extrema.bottom=Math.max(extrema.bottom,y);
   if(x<margin||x>model.canvas[0]-margin||y<margin||y>model.canvas[1]-margin)
    failures.push(`${label} alpha silhouette=(${x.toFixed(3)},${y.toFixed(3)}) violates configuration ${margin}px canvas clearance`);
  }
 }
 for(const gesture of GESTURES)for(const origin of [0,4.5,12.5,22.5])for(const duration of [1.8,5,12]){
  const frames=Math.ceil(duration*24);
  for(let frame=0;frame<=frames;frame++){
   const time=duration*frame/frames,input={gesture,requestTime:time,duration,motionTime:origin+time};
   const state=teacherState(input,model),label=`${gesture} duration=${duration} origin=${origin} t=${time.toFixed(3)}`;
   for(const {spec,outline} of outlines){
    const transform=segmentTransform(spec,armJoints(model,spec.side,state));
    check(outline.map(point=>project(transformSectionPoint(transform,point))),`${label}/${spec.id}`);
   }
   for(const side of [1,-1]){
    const pose=handPose(model,side,state,input);
    for(const [name,shape] of Object.entries(pose.shapes))if(shape.alpha>1/255){
     const points=projectedHand(model,side,pose,name),handLabel=`${label}/${name} side=${side}`;
     check(points,handLabel);
     // The front desk lip is drawn over hands before the viewport ends.
     // Configuration target: 3 native pixels of filtering clearance above it.
     if(Number.isFinite(model.foreground_y))for(const [x,y] of points)
      if(y>project([0,model.foreground_y])[1]-3)failures.push(`${handLabel} fingertip (${x},${y}) is hidden by the foreground desk lip`);
    }
   }
  }
 }
 return {extrema,failures};
}
test('actual segmented sleeves and authored hands stay inside the canvas throughout complete gestures',t=>{
 const {extrema,failures}=stageSilhouetteAudit(registeredRig);
 t.diagnostic(`Measured full sleeve/hand alpha hull extrema in native canvas units: ${JSON.stringify(extrema)}`);
 assert.equal(failures.length,0,failures[0]);
});

const wristPathRig={...registeredRig,arms:{...registeredRig.arms,gesture_paths:{
 wave:{target:[332,456],outward_offset:10,hand_shape_start:.6,hand_shape_end:.8,min_duration:3.5},
 think:{target:[300,420],outward_offset:10,hand_shape_start:.6,hand_shape_end:.8,min_duration:3.5},
 point:{target:[325,482],outward_offset:5,hand_shape_start:.6,hand_shape_end:.8,min_duration:3.5}
}}};
test('authored wrist lifts stay outside the blouse, preserve both bones and never flip the elbow branch',()=>{
 const idle=armJoints(wristPathRig,1,teacherState({gesture:'idle'},wristPathRig));
 const restCross=(idle[2][0]-idle[0][0])*(idle[1][1]-idle[0][1])-(idle[2][1]-idle[0][1])*(idle[1][0]-idle[0][0]);
 for(const gesture of ['wave','think','point'])for(const duration of [1.8,5,12]){
  let previous;
  const frames=Math.ceil(duration*60);
  for(let frame=0;frame<=frames;frame++){
   const time=duration*frame/frames,input={gesture,requestTime:time,duration,motionTime:20+time};
   const state=teacherState(input,wristPathRig),joints=armJoints(wristPathRig,1,state),[shoulder,elbow,wrist]=joints;
   assert.deepEqual(shoulder,idle[0]);
   for(const [a,b] of [[0,1],[1,2]])assert.ok(Math.abs(distance(joints[a],joints[b])-distance(idle[a],idle[b]))<1e-8);
   assert.ok(wrist[0]>=295,'Lift crosses into the blouse before reaching the configured target');
   const cross=(wrist[0]-shoulder[0])*(elbow[1]-shoulder[1])-(wrist[1]-shoulder[1])*(elbow[0]-shoulder[0]);
   assert.ok(cross*restCross>0,'The solver jumps to the opposite elbow branch');
   if(previous)for(let joint=1;joint<3;joint++)assert.ok(distance(joints[joint],previous[joint])<wristPathRig.arms.forearm_length*.05,
    `${gesture} duration=${duration} t=${time} jumps at joint ${joint}`);
   previous=joints;
   const pose=handPose(wristPathRig,1,state,input);
   if(pose.shapes.wave.alpha>0||pose.shapes.point.alpha>0)assert.ok(wrist[0]>=295,
    'An active gesture hand enters the blouse before its wrist clears the side-lift path');
   assert.deepEqual(armJoints(wristPathRig,-1,state),armJoints(wristPathRig,-1,teacherState({gesture:'idle'},wristPathRig)),
    'The resting arm follows a right-hand wrist path');
  }
  for(const time of [0,duration])assert.deepEqual(armJoints(wristPathRig,1,teacherState({gesture,requestTime:time,duration},wristPathRig)),idle);
  const held=armJoints(wristPathRig,1,teacherState({gesture,requestTime:duration/2,duration},wristPathRig));
  if(duration>=3.5)assert.ok(distance(held[2],wristPathRig.arms.gesture_paths[gesture].target)<1e-8);
  else assert.ok(distance(held[2],wristPathRig.arms.gesture_paths[gesture].target)>1,
   'A short request must stop before the full lift rather than accelerating it');
 }
});

test('wrist path shape changes wait for the side lift and reverse on the same request clock',()=>{
 for(const gesture of ['wave','think'])for(const weight of [0,.2,.59,.6,.65,.7,.8,.9,1]){
  const input={gesture,requestTime:2.5,duration:5,motionTime:22.5};
  const state={...teacherState(input,wristPathRig),weight,pathWeight:weight,palm:weight};
  const pose=handPose(wristPathRig,1,state,input),active=gesture==='wave'?pose.shapes.wave:pose.shapes.point;
  assert.equal(pose.shapes.relaxed.alpha+active.alpha,1);
  if(weight<=.6)assert.equal(active.alpha,0,'A splayed palm or pointing finger appears during early lift');
  if(weight>=.8)assert.equal(active.alpha,1);
  if(weight>.6&&weight<.8)assert.ok(active.alpha>0&&active.alpha<1);
 }
 for(const gesture of ['wave','think'])for(const time of [.5,1,1.25,2,4,4.5]){
  const input={gesture,requestTime:time,duration:5,motionTime:20+time};
  const state=teacherState(input,wristPathRig);
  const continued={...input,requestTime:(time-.5)+.5,motionTime:19.5+.5+time};
  assert.deepEqual(armJoints(wristPathRig,1,state),armJoints(wristPathRig,1,teacherState(continued,wristPathRig)));
  assert.deepEqual(handPose(wristPathRig,1,state,input),handPose(wristPathRig,1,teacherState(continued,wristPathRig),continued));
 }
});

test('unreachable wrist paths clamp safely and invalid path configuration fails explicitly',()=>{
 for(const target of [[374,411],[10000,-10000]]){
  const model={...wristPathRig,arms:{...wristPathRig.arms,gesture_paths:{wave:{target,outward_offset:0}}}};
  const joints=armJoints(model,1,teacherState({gesture:'wave',requestTime:2.5,duration:5},model));
  assert.ok(joints.flat().every(Number.isFinite));
  assert.ok(Math.abs(distance(joints[0],joints[1])-distance(model.arms.shoulders[0],model.arms.elbows[0]))<1e-8);
  assert.ok(Math.abs(distance(joints[1],joints[2])-model.arms.forearm_length)<1e-8);
 }
 for(const config of [{target:[NaN,420]},{target:[300]}, {target:[300,420],outward_offset:-1},
  {target:[300,420],hand_shape_start:.8,hand_shape_end:.7}]){
  const model={...wristPathRig,arms:{...wristPathRig.arms,gesture_paths:{wave:config}}};
  const input={gesture:'wave',requestTime:2.5,duration:5},state=teacherState(input,model);
  assert.throws(()=>handPose(model,1,state,input));
 }
 const invalid={...wristPathRig,arms:{...wristPathRig.arms,gesture_paths:{wave:{target:[332,456],min_duration:NaN}}}};
 assert.throws(()=>teacherState({gesture:'wave'},invalid));
});

test('actual sleeve bind sizes preserve source artwork and both authored hand sides retain their wrist anchors',()=>{
 for(const spec of registeredRig.arm_segments){
  const tile=png(spec.asset),meta=registeredRig.extraction[spec.id];
  assert.deepEqual([tile.width,tile.height],meta.size,`${spec.id} source dimensions are stale`);
  assert.ok(Math.abs(spec.size[0]/spec.size[1]-tile.width/tile.height)<1e-10,`${spec.id} stretches its painted aspect ratio`);
  if(spec.bone==='elbow')continue;
  for(let axis=0;axis<2;axis++)assert.ok(Math.abs(spec.size[axis]-meta.size[axis]*meta.runtime_uniform_scale_configuration)<1e-9);
  for(let joint=0;joint<2;joint++)for(let axis=0;axis<2;axis++)assert.ok(Math.abs(
   spec.anchors[joint][axis]*meta.size[axis]+meta.bounds_in_source[axis]-meta.bone_anchors_source_configuration[joint][axis])<1e-9,
   `${spec.id} attachment no longer follows its authored source joint`);
  const rest=segmentTransform(spec,armJoints(registeredRig,spec.side,teacherState({gesture:'idle'},registeredRig)));
  // Configuration tolerance for native bind dimensions. Hidden extra limb
  // scaling must not reintroduce the old 20% upper-sleeve length correction.
  assert.ok(Math.abs(rest.scale-1)<.02,`${spec.id} requires additional scaling beyond its native authored bind size`);
  for(const gesture of GESTURES)for(let frame=0;frame<=120;frame++){
   const input={gesture,requestTime:frame/24,duration:5,motionTime:22.5+frame/24};
   const transform=segmentTransform(spec,armJoints(registeredRig,spec.side,teacherState(input,registeredRig)));
   assert.ok(transform.determinant>0,`${gesture}/${spec.id} reflects the painted sleeve`);
   assert.ok(Math.abs(transform.scale-rest.scale)<1e-12,`${gesture}/${spec.id} changes painted width or length`);
  }
 }
 for(const name of ['relaxed','open','point','wave']){
  const right=handSpec(registeredRig,name,1),left=handSpec(registeredRig,name,-1);
  assert.notEqual(left.asset,right.asset,`${name} needs separately authored left and right hands`);
  assert.ok(!png(left.asset).pixels.equals(png(right.asset).pixels),`${name} reuses the same hand pixels on both sides`);
  for(const [side,spec] of [[-1,left],[1,right]]){
   const tile=png(spec.asset),meta=registeredRig.extraction[`${name}-hand-${side<0?'left':'right'}`];
   assert.equal(spec.mirror,false,`${name}/${side} mirrors its authored lighting`);
   assert.deepEqual([tile.width,tile.height],meta.size);
   assert.ok(Math.abs(spec.size[0]/spec.size[1]-tile.width/tile.height)<1e-10,`${name}/${side} stretches its hand artwork`);
   for(let axis=0;axis<2;axis++)assert.ok(Math.abs(
    spec.anchor[axis]*meta.size[axis]+meta.bounds_in_source[axis]-meta.wrist_anchor_source_configuration[axis])<1e-9,
    `${name}/${side} detaches from its authored wrist`);
  }
 }
});

test('opaque path hand states never blend fingers and apply gesture rotation only to the active hand',()=>{
 const offsets={wave:.62,think:-.2,point:.7};
 for(const gesture of Object.keys(offsets)){
  const path={...wristPathRig.arms.gesture_paths[gesture],hand_shape_mode:'opaque',hand_rotation_offset:offsets[gesture]};
  const model={...wristPathRig,arms:{...wristPathRig.arms,gesture_paths:{[gesture]:path}}};
  const baseline={...model,arms:{...model.arms,gesture_paths:{[gesture]:{...path,hand_rotation_offset:0}}}};
  for(const weight of [0,.2,.59,.6,.7,.799,.8,.9,1])for(const requestTime of [.01,2.5,4.99]){
   const input={gesture,requestTime,duration:5,motionTime:20+requestTime};
   const state={...teacherState(input,model),weight,pathWeight:weight,palm:weight};
   const pose=handPose(model,1,state,input),original=handPose(baseline,1,state,input);
   assert.ok(Object.values(pose.shapes).every(shape=>shape.alpha===0||shape.alpha===1),
    'Opaque hand mode must bypass the old request-edge sprite fade');
   assert.equal(Object.values(pose.shapes).reduce((sum,shape)=>sum+shape.alpha,0),1,
    'Exactly one complete painted hand must remain visible');
   const active=gesture==='wave'?'wave':'point';
   assert.equal(pose.shapes[active].alpha,weight>=path.hand_shape_end?1:0);
   assert.equal(pose.shapes.relaxed.rotation,original.shapes.relaxed.rotation,'Gesture rotation must not twist the resting hand');
   assert.ok(Math.abs(pose.shapes[active].rotation-original.shapes[active].rotation-offsets[gesture]*weight)<1e-12);
   assert.deepEqual(handPose(model,-1,state,input),handPose(baseline,-1,state,input),'The resting left hand inherits a right-hand rotation');
  }
  const input={gesture,requestTime:2.5,duration:5},state={...teacherState(input,wristPathRig),weight:.7,pathWeight:.7,palm:.7};
  const faded=handPose(wristPathRig,1,state,input);
  assert.ok(faded.shapes.relaxed.alpha>0&&faded.shapes.relaxed.alpha<1,'Unconfigured paths must retain their original fade');
  const invalid={...model,arms:{...model.arms,gesture_paths:{[gesture]:{...path,hand_rotation_offset:Infinity}}}};
  assert.throws(()=>handPose(invalid,1,state,input));
 }
});

test('the arm proportion revision preserves every registered head layer and expression setting',()=>{
 assert.deepEqual(proportionedRig.layers.filter(part=>part.group==='head'),registeredRig.layers.filter(part=>part.group==='head'));
 for(const key of ['coherent_head','head_scale','head_pivot','neck_mask','expression_states','hair_physics'])
  assert.deepEqual(proportionedRig[key],registeredRig[key],`${key} changes the accepted face during an arm-only revision`);
 for(const part of registeredRig.layers.filter(part=>part.group==='head'))
  assert.deepEqual(proportionedRig.extraction[part.id],registeredRig.extraction[part.id],`${part.id} source registration changed`);
});

const paintedSectionCache=new Map();
function sectionWidth(spec,station){
 const key=JSON.stringify([spec.asset,spec.size,spec.anchors]);
 let points=paintedSectionCache.get(key);
 if(!points){
  const image=png(spec.asset),[a,b]=spec.anchors.map(point=>point.map((value,index)=>value*spec.size[index]));
  const length=distance(a,b),ux=(b[0]-a[0])/length,uy=(b[1]-a[1])/length;
  points=[];
  for(let y=0;y<image.height;y++)for(let x=0;x<image.width;x++)if(image.pixels[(y*image.width+x)*4+3]>=128){
   const dx=(x+.5)*spec.size[0]/image.width-a[0],dy=(y+.5)*spec.size[1]/image.height-a[1];
   points.push([dx*ux+dy*uy,-dx*uy+dy*ux]);
  }
  points={length,values:points};paintedSectionCache.set(key,points);
 }
 const band=points.values.filter(point=>Math.abs(point[0]-points.length*station)<=1.5).map(point=>point[1]);
 assert.ok(band.length,`${spec.id} has no painted cloth at bone station ${station}`);
 return Math.max(...band)-Math.min(...band);
}
test('actual revised sleeves taper toward the wrist and preserve authored native bind dimensions',t=>{
 const measured={};
 for(const side of [-1,1]){
  const upper=proportionedRig.arm_segments.find(part=>part.side===side&&part.bone==='upper');
  const forearm=proportionedRig.arm_segments.find(part=>part.side===side&&part.bone==='forearm');
  const upperMid=sectionWidth(upper,.5),forearmMid=sectionWidth(forearm,.5),cuff=sectionWidth(forearm,1);
  measured[side]={upperMid,forearmMid,cuff,forearmProximal:sectionWidth(forearm,0),upperDistal:sectionWidth(upper,1)};
  // Art-direction targets for this tailored jacket, not anatomical standards.
  // The half-pixel allowance covers the sampled raster/antialias boundary.
  assert.ok(forearmMid<=upperMid*.9+.5,`${side} forearm is as bulky as its upper sleeve`);
  assert.ok(cuff<=forearmMid*.9+.5,`${side} sleeve widens again into an oversized cuff`);
  assert.ok(measured[side].forearmProximal<=measured[side].upperDistal*1.1+.5,`${side} sleeve inflates across the elbow joint`);
  for(const part of [upper,forearm]){
   const image=png(part.asset),meta=proportionedRig.extraction[part.id];
   assert.deepEqual([image.width,image.height],meta.size);
   assert.ok(Math.abs(part.size[0]/part.size[1]-image.width/image.height)<1e-10,`${part.id} stretches the source aspect`);
   const transform=segmentTransform(part,armJoints(proportionedRig,side,teacherState({gesture:'idle'},proportionedRig)));
   assert.ok(Math.abs(transform.scale-1)<.02,`${part.id} adds a hidden bind length correction`);
   for(let endpoint=0;endpoint<2;endpoint++)for(let axis=0;axis<2;axis++)assert.ok(Math.abs(
    part.anchors[endpoint][axis]*meta.size[axis]+meta.bounds_in_source[axis]-meta.bone_anchors_source_configuration[endpoint][axis])<1e-9);
  }
 }
 t.diagnostic(`Measured alpha128 sleeve cross-sections in native pixels: ${JSON.stringify(measured)}`);
});

function handLandmarkAudit(model){
 const measured={},failures=[];
 const require=(condition,message)=>{if(!condition)failures.push(message);};
 for(const side of [-1,1]){
  measured[side]={};
  for(const name of ['relaxed','open','point','wave']){
   const spec=handSpec(model,name,side),meta=model.extraction[`${name}-hand-${side<0?'left':'right'}`];
   const image=png(spec.asset),landmarks=meta.landmarks_source_configuration;
   assert.ok(landmarks,`${name}/${side} requires authored anatomical landmarks`);
   const [x0,y0]=meta.bounds_in_source,scale=spec.size[0]/image.width;
   assert.equal(spec.mirror,false);
   assert.ok(Math.abs(scale-spec.size[1]/image.height)<1e-12,`${name}/${side} stretches the authored hand`);
   for(let axis=0;axis<2;axis++)assert.ok(Math.abs(spec.anchor[axis]*meta.size[axis]+meta.bounds_in_source[axis]-landmarks.wrist[axis])<1e-9);
   const pairSpan=pair=>distance(...pair)*scale;
   measured[side][name]={wrist:pairSpan(landmarks.wrist_edges),palm:pairSpan(landmarks.palm_edges),
    wristMcp:distance(landmarks.wrist,landmarks.middle_mcp)*scale,tip:distance(landmarks.wrist,landmarks.main_tip)*scale};
   require(Math.abs(measured[side][name].tip-spec.wrist_tip_length_native_configuration)<.01,`${name}/${side} tip calibration is stale`);
   // Every landmark must touch real authored skin, allowing 2 native pixels
   // for manual annotation and feathering rather than trusting metadata alone.
   for(const [label,value] of Object.entries(landmarks))for(const point of label.endsWith('_edges')?value:[value]){
    const px=point[0]-x0,py=point[1]-y0,radius=Math.ceil(2/scale);
    let alpha=0;
    for(let y=Math.max(0,Math.floor(py-radius));y<=Math.min(image.height-1,Math.ceil(py+radius));y++)
     for(let x=Math.max(0,Math.floor(px-radius));x<=Math.min(image.width-1,Math.ceil(px+radius));x++)
      if(Math.hypot(x-px,y-py)*scale<=2)alpha=Math.max(alpha,image.pixels[(y*image.width+x)*4+3]);
    require(alpha>=32,`${name}/${side} ${label} landmark (${point}) is outside actual skin alpha`);
   }
  }
  // Configuration tolerance: 18% permits modest projected pose differences
  // while catching a hand that grows its wrist or palm when its fingers bend.
  for(const dimension of ['wrist','wristMcp']){
   const values=Object.values(measured[side]).map(pose=>pose[dimension]);
   require(Math.max(...values)/Math.min(...values)<=1.18,`${side} ${dimension} scale changes across poses: ${values}`);
  }
  const palms=['relaxed','open','wave'].map(name=>measured[side][name].palm);
  require(Math.max(...palms)/Math.min(...palms)<=1.18,`${side} open-palm breadth changes across poses: ${palms}`);
  const median=[...palms].sort((a,b)=>a-b)[1],folded=measured[side].point.palm;
  // Curled fingers obscure more of the palm outline, so the index gesture has
  // a separate 25% lower allowance while retaining its MCP/wrist checks above.
  require(folded>=median*.75&&folded<=median*1.18,`${side} folded index palm changes scale: ${folded} vs ${median}`);
 }
 return {measured,failures};
}
test('actual revised hand landmarks preserve palm and wrist scale across pose switches',t=>{
 const {measured,failures}=handLandmarkAudit(proportionedRig);
 t.diagnostic(`Measured authored hand landmark dimensions in native pixels: ${JSON.stringify(measured)}`);
 t.diagnostic(`Hand landmark concerns: ${JSON.stringify(failures)}`);
 assert.equal(failures.length,0,failures[0]);
});

test('actual revised painted arms and hands clear the viewport throughout every gesture clock',t=>{
 const {extrema,failures}=stageSilhouetteAudit(proportionedRig);
 t.diagnostic(`Measured revised full sleeve/hand alpha hull extrema: ${JSON.stringify(extrema)}`);
 assert.equal(failures.length,0,failures[0]);
 for(const gesture of GESTURES)for(const duration of [1.8,5,12]){
  let previous;const upper=distance(proportionedRig.arms.shoulders[0],proportionedRig.arms.elbows[0]);
  for(let frame=0;frame<=Math.ceil(duration*60);frame++){
   const time=duration*frame/Math.ceil(duration*60),state=teacherState({gesture,requestTime:time,duration,motionTime:20+time},proportionedRig);
   const joints=armJoints(proportionedRig,1,state);
   assert.ok(Math.abs(distance(joints[0],joints[1])-upper)<1e-8);
   assert.ok(Math.abs(distance(joints[1],joints[2])-proportionedRig.arms.forearm_length)<1e-8);
   if(previous)for(let joint=1;joint<3;joint++)assert.ok(distance(joints[joint],previous[joint])<proportionedRig.arms.forearm_length*.05,
    `${gesture} duration=${duration} t=${time} moves too far between adjacent 60-Hz samples`);
   previous=joints;
  }
 }
});

test('the larger-arm composition translates the intact face and torso together without shrinking either',()=>{
 const body5=proportionedRig.layers.find(part=>part.id==='body'),body6=enlargedRig.layers.find(part=>part.id==='body');
 const offset=body6.rect.slice(0,2).map((value,axis)=>value-body5.rect[axis]);
 assert.ok(offset[1]<0,'The intact composition must make desk space above the original shoulder position');
 assert.deepEqual(enlargedRig.layers.map(part=>part.id),proportionedRig.layers.map(part=>part.id));
 for(const previous of proportionedRig.layers){
  const current=enlargedRig.layers.find(part=>part.id===previous.id);
  assert.deepEqual(current,{...previous,rect:previous.rect.map((value,index)=>index<2?value+offset[index]:value)},
   `${previous.id} changed its artwork, aspect or relative facial registration`);
 }
 assert.deepEqual(enlargedRig.head_pivot,proportionedRig.head_pivot.map((value,axis)=>value+offset[axis]));
 for(const key of ['head_scale','coherent_head','neck_mask','expression_states','hair_physics','background','tabletop_y','foreground_y','camera'])
  assert.deepEqual(enlargedRig[key],proportionedRig[key],`${key} changed during an arm/hand enlargement`);
 for(const part of proportionedRig.layers.filter(part=>part.group==='head'))
  assert.deepEqual(enlargedRig.extraction[part.id],proportionedRig.extraction[part.id]);
 for(let side=0;side<2;side++)assert.deepEqual(enlargedRig.arms.shoulders[side],
  proportionedRig.arms.shoulders[side].map((value,axis)=>value+offset[axis]),'Shoulders must follow the translated torso');
});

test('actual enlarged hands preserve source anatomy and increase every pose relative to v5',t=>{
 const {measured,failures}=handLandmarkAudit(enlargedRig),previous=handLandmarkAudit(proportionedRig).measured;
 // Directional regression targets from the user's correction: at least 10%
 // longer bones and 20% larger hands, with no camera reduction hiding growth.
 for(let side=0;side<2;side++)assert.ok(distance(enlargedRig.arms.shoulders[side],enlargedRig.arms.elbows[side])>=
  distance(proportionedRig.arms.shoulders[side],proportionedRig.arms.elbows[side])*1.1);
 assert.ok(enlargedRig.arms.forearm_length>=proportionedRig.arms.forearm_length*1.1);
 for(const side of [-1,1])for(const name of ['relaxed','open','point','wave']){
  for(const dimension of ['wrist','palm','wristMcp','tip'])assert.ok(measured[side][name][dimension]>=previous[side][name][dimension]*1.2,
   `${name}/${side} ${dimension} shrinks while the user requested larger hands`);
 }
 t.diagnostic(`Measured enlarged anatomical hand landmarks in native pixels: ${JSON.stringify(measured)}`);
 t.diagnostic(`Enlarged-hand landmark concerns: ${JSON.stringify(failures)}`);
 assert.equal(failures.length,0,failures[0]);
});

test('actual larger arm and hand silhouettes clear the viewport, desk lip and resting opposite hand',t=>{
 const {extrema,failures}=stageSilhouetteAudit(enlargedRig);
 t.diagnostic(`Measured enlarged full sleeve/hand alpha hull extrema: ${JSON.stringify(extrema)}`);
 assert.equal(failures.length,0,failures[0]);
 const input={gesture:'idle',requestTime:2.5,duration:5,motionTime:22.5},state=teacherState(input,enlargedRig);
 const right=projectedHand(enlargedRig,1,handPose(enlargedRig,1,state,input),'relaxed');
 const left=projectedHand(enlargedRig,-1,handPose(enlargedRig,-1,state,input),'relaxed');
 const gap=Math.min(...right.map(point=>point[0]))-Math.max(...left.map(point=>point[0]));
 t.diagnostic(`Measured resting painted-hand hull separation: ${gap} native pixels`);
 assert.ok(gap>=4,'The enlarged resting hands collide at the centre of the desk (configuration clearance: 4 pixels)');
 for(const gesture of GESTURES)for(const duration of [1.8,5,12]){
  let previous;
  const upper=distance(enlargedRig.arms.shoulders[0],enlargedRig.arms.elbows[0]);
  for(let frame=0;frame<=Math.ceil(duration*60);frame++){
   const time=duration*frame/Math.ceil(duration*60),pose=teacherState({gesture,requestTime:time,duration,motionTime:20+time},enlargedRig);
   const joints=armJoints(enlargedRig,1,pose);
   assert.ok(Math.abs(distance(joints[0],joints[1])-upper)<1e-8);
   assert.ok(Math.abs(distance(joints[1],joints[2])-enlargedRig.arms.forearm_length)<1e-8);
   if(previous)for(let joint=1;joint<3;joint++)assert.ok(distance(joints[joint],previous[joint])<enlargedRig.arms.forearm_length*.05,
    `${gesture} duration=${duration} t=${time} jumps between adjacent 60-Hz samples`);
   previous=joints;
  }
 }
});
