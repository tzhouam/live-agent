// Deterministic, model-local deformation. All limits are configuration targets.
export const GESTURES = new Set(['idle','listen','explain','present','point','smile','think','nod','shake','wave']);
export const clamp = (v,a=0,b=1) => Math.min(b,Math.max(a,Number.isFinite(v)?v:0));
export const ease = v => {const x=clamp(v);return x*x*(3-2*x);};
export function teacherState(input={}, rig) {
  const t=Math.max(0,input.motionTime||0), duration=Math.max(.1,input.duration||5);
  const u=clamp((input.requestTime||0)/duration), gesture=GESTURES.has(input.gesture)?input.gesture:'idle';
  // Larger lifts take longer to rise and settle than small desk gestures.
  // The envelope uses the whole request clock, so a chunk change cannot restart it.
  const rise=gesture==='wave'?.46:gesture==='think'?.40:.24;
  const fall=gesture==='wave'?.46:gesture==='think'?.40:.30;
  const weight=ease(u/rise)*ease((1-u)/fall);
  const pulse=Math.sin(t*2.1)*.018*weight;
  let angle=rig.arms.rest_angle, upperAngle=0, palm=0, nod=0, tilt=0, turn=0;
  if(['explain','point','present','think','wave'].includes(gesture)){
    const desired=gesture==='point'?rig.arms.point_angle:
      gesture==='present'?rig.arms.present_angle:
      gesture==='wave'?(rig.arms.wave_angle??-2.927):
      gesture==='think'?(rig.arms.think_angle??-3.00):rig.arms.explain_angle;
    angle+=(desired-angle)*weight+pulse;
    palm=weight;
  }
  if(gesture==='wave'){
    upperAngle=(rig.arms.wave_upper_angle??.54)*weight;
    angle-=.04*Math.sin(t*5.4)*weight;
  }
  if(gesture==='listen')tilt=.025*weight;
  if(gesture==='think'){
    upperAngle=(rig.arms.think_upper_angle??-.52)*weight;
    tilt=-.032*weight;turn=-.20*weight;
  }
  if(gesture==='nod')nod=3.4*Math.sin(u*Math.PI*4)*weight;
  if(gesture==='shake')turn=.55*Math.sin(u*Math.PI*4)*weight;
  const blinkPhase=(t+.7)%3.7;
  const blink=blinkPhase<.26?(blinkPhase<.09?ease(blinkPhase/.09):1-ease((blinkPhase-.09)/.17)):0;
  const breath=rig.limits.breath*Math.sin(t*2*Math.PI/4.6);
  const path=rig.arms.gesture_paths?.[gesture];
  const pathState={};
  if(path){
    const minimum=path.min_duration??0;
    if(!Number.isFinite(minimum)||minimum<0)throw new Error('Invalid wrist path minimum duration');
    pathState.pathWeight=weight*(minimum>0?Math.min(1,duration/minimum):1);
  }
  return {gesture,weight,palm,angle,upperAngle,blink,breath,nod,
    gazeX:gesture==='think'?-.60*weight:0,
    gazeY:gesture==='think'?-.25*weight:gesture==='listen'?.12*weight:0,
    tilt:clamp(tilt+Math.sin(t*.43)*.006,-rig.limits.head_tilt,rig.limits.head_tilt),
    turn:clamp(turn+Math.sin(t*.29)*.10,-rig.limits.head_turn,rig.limits.head_turn),
    hair:Math.sin(t*1.05-.8)*rig.limits.hair_sway,
    mouth:clamp(input.mouthOpen),round:clamp(input.mouthRound),smile:gesture==='smile'?weight:.12,...pathState};
}
export function armJoints(rig, side, state) {
  const i=side>0?0:1, shoulder=rig.arms.shoulders[i], restElbow=rig.arms.elbows[i];
  const path=side>0?rig.arms.gesture_paths?.[state.gesture]:undefined;
  if(path){
    const target=path.target,offset=path.outward_offset??0;
    if(!Array.isArray(target)||target.length!==2||target.some(value=>!Number.isFinite(value))||!Number.isFinite(offset)||offset<0)
      throw new Error('Invalid authored wrist path');
    const upper=Math.hypot(restElbow[0]-shoulder[0],restElbow[1]-shoulder[1]),lower=rig.arms.forearm_length;
    if(!Number.isFinite(upper)||upper<=0||!Number.isFinite(lower)||lower<=0)throw new Error('Invalid wrist path bones');
    const rest=[restElbow[0]+side*lower*Math.sin(rig.arms.rest_angle),restElbow[1]+lower*Math.cos(rig.arms.rest_angle)];
    const weight=clamp(state.pathWeight??state.weight);
    if(weight===0)return [shoulder,restElbow,rest];
    // The wrist rises outside the blouse before approaching the final pose.
    // One request-relative weight drives both lift and return; chunks carry no
    // solver state that could restart the path or select another elbow branch.
    let dx=rest[0]+(target[0]-rest[0])*weight+offset*Math.sin(Math.PI*weight)-shoulder[0];
    let dy=rest[1]+(target[1]-rest[1])*weight-shoulder[1];
    let distance=Math.hypot(dx,dy);
    if(distance<1e-9){dx=rest[0]-shoulder[0];dy=rest[1]-shoulder[1];distance=Math.hypot(dx,dy);}
    const ux=dx/distance,uy=dy/distance;
    const epsilon=Math.min(upper,lower)*1e-4;
    const reach=clamp(distance,Math.abs(upper-lower)+epsilon,upper+lower-epsilon);
    const along=(upper*upper-lower*lower+reach*reach)/(2*reach);
    const height=Math.sqrt(Math.max(0,upper*upper-along*along));
    // Select the rest elbow's side of its shoulder-wrist axis once, rather
    // than choosing whichever candidate is closest at each animation frame.
    const restCross=(rest[0]-shoulder[0])*(restElbow[1]-shoulder[1])-(rest[1]-shoulder[1])*(restElbow[0]-shoulder[0]);
    const branch=restCross<0?-1:1;
    const elbow=[shoulder[0]+ux*along-branch*uy*height,shoulder[1]+uy*along+branch*ux*height];
    return [shoulder,elbow,[shoulder[0]+ux*reach,shoulder[1]+uy*reach]];
  }
  const lift=side>0?(state.upperAngle||0):0;
  const dx=restElbow[0]-shoulder[0],dy=restElbow[1]-shoulder[1];
  // Rotate the upper bone about its fixed shoulder rather than translating the
  // elbow. Sleeve length stays constant when a hand rises beside the face.
  const elbow=[shoulder[0]+dx*Math.cos(lift)+dy*Math.sin(lift),
               shoulder[1]+dy*Math.cos(lift)-dx*Math.sin(lift)];
  const angle=side>0?state.angle:rig.arms.rest_angle;
  const wrist=[elbow[0]+side*rig.arms.forearm_length*Math.sin(angle),
               elbow[1]+rig.arms.forearm_length*Math.cos(angle)];
  return [shoulder,elbow,wrist];
}
// Authored wrist registration shared by the renderer and geometry checks.
// This reports actual sprite transforms, including the brief rest/gesture fade.
export function handSpec(rig,name,side) {
  const base=rig.hands?.[name],override=base?.sides?.[String(side)];
  if(!base||override!==undefined&&(!override||typeof override!=='object'||Array.isArray(override)))
    throw new Error('Invalid side-specific hand artwork');
  const spec={...base,...override,mirror:override===undefined&&side<0};
  for(const key of ['rotation_offset','wrist_flex','rest_rotation'])
    if(spec[key]!==undefined&&!Number.isFinite(spec[key]))throw new Error('Invalid authored hand rotation');
  return spec;
}
export function handPose(rig,side,state,input={}) {
  const [,elbow,wrist]=armJoints(rig,side,state);
  const angle=-Math.atan2(wrist[0]-elbow[0],wrist[1]-elbow[1]);
  const duration=Math.max(.1,input.duration||5),requestTime=clamp(input.requestTime||0,0,duration);
  const transition=ease(Math.min(requestTime,duration-requestTime)/.16);
  const path=side>0?rig.arms.gesture_paths?.[state.gesture]:undefined;
  let activation=1,opaque=false,rotationOffset=0;
  if(path){
    const start=path.hand_shape_start??.6,end=path.hand_shape_end??.8;
    if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end>1||start>=end)
      throw new Error('Invalid wrist path hand thresholds');
    const weight=clamp(state.pathWeight??state.weight),offset=path.hand_rotation_offset??0;
    if(!Number.isFinite(offset))throw new Error('Invalid wrist path hand rotation');
    opaque=path.hand_shape_mode==='opaque';
    activation=opaque?(weight>=end?1:0):ease((weight-start)/(end-start));
    rotationOffset=offset*weight;
  }
  const open=side>0&&state.palm>0?(opaque?activation:transition*activation):0;
  const relaxed=handSpec(rig,'relaxed',side);
  const rotation=(name,legacy)=>{
    const spec=handSpec(rig,name,side);
    return (spec.rotation_offset===undefined?legacy:angle+spec.rotation_offset+(spec.wrist_flex||0)*state.weight)+rotationOffset;
  };
  return {wrist,elbow,shapes:{
    relaxed:{rotation:angle+(relaxed.rotation_offset||0)+(relaxed.mirror?-1:1)*(relaxed.rest_rotation||0)+(relaxed.wrist_flex||0)*state.weight,alpha:1-open},
    open:{rotation:rotation('open',angle-1.51+.41*state.weight),alpha:['point','wave','think'].includes(state.gesture)?0:open},
    point:{rotation:rotation('point',angle-2.43+(state.gesture==='think'?-.37:-1.35)*state.weight),
           alpha:['point','think'].includes(state.gesture)?open:0},
    wave:{rotation:rotation('wave',angle-Math.PI)+Math.sin((input.motionTime||0)*5)*.07*state.weight,
          alpha:state.gesture==='wave'?open:0}
  }};
}
// A section is a rigid piece of painted cloth. Similarity registration rotates
// and uniformly scales its authored bone onto a target bone; it never blends
// incompatible rotations through elbow pixels or reflects the source lighting.
export function segmentTransform(spec,joints) {
  const size=spec?.size;
  if(!Array.isArray(size)||size.length!==2||size.some(value=>!Number.isFinite(value)||value<=0)||
     !Array.isArray(joints)||joints.length!==3||joints.some(point=>!Array.isArray(point)||point.length!==2||point.some(value=>!Number.isFinite(value))))
    throw new Error('Invalid segmented arm geometry');
  const normalized=point=>Array.isArray(point)&&point.length===2&&point.every(value=>Number.isFinite(value)&&value>=0&&value<=1);
  if(spec.bone==='elbow'){
    const anchor=spec.anchor??[.5,.5],rotation=spec.rotation??0;
    if(!normalized(anchor)||!Number.isFinite(rotation))throw new Error('Invalid painted elbow registration');
    const [x,y]=anchor.map((value,index)=>value*size[index]),cos=Math.cos(rotation),sin=Math.sin(rotation);
    return {position:[joints[1][0]-x*cos+y*sin,joints[1][1]-x*sin-y*cos],rotation,scale:1,determinant:1};
  }
  if(!['upper','forearm'].includes(spec.bone)||!Array.isArray(spec.anchors)||spec.anchors.length!==2||!spec.anchors.every(normalized))
    throw new Error('Invalid painted arm registration');
  const [a,b]=spec.anchors.map(point=>point.map((value,index)=>value*size[index]));
  const index=spec.bone==='upper'?0:1,c=joints[index],d=joints[index+1];
  const sourceLength=Math.hypot(b[0]-a[0],b[1]-a[1]),targetLength=Math.hypot(d[0]-c[0],d[1]-c[1]);
  if(sourceLength<1e-6||targetLength<1e-6)throw new Error('Degenerate segmented arm bone');
  const scale=targetLength/sourceLength,rotation=Math.atan2(d[1]-c[1],d[0]-c[0])-Math.atan2(b[1]-a[1],b[0]-a[0]);
  const cos=Math.cos(rotation)*scale,sin=Math.sin(rotation)*scale;
  return {position:[c[0]-a[0]*cos+a[1]*sin,c[1]-a[0]*sin-a[1]*cos],rotation,scale,determinant:scale*scale};
}
// Registered facial patches and an intact painted head share one authored
// coordinate system. Their common container moves; individual patches must
// not bend according to their unrelated local crop heights.
export function deformHead(vertices,width,height,spec,state,rig,out=new Float32Array(vertices.length)) {
  if(rig.coherent_head===true||rig.expression_states?.mode==='registered-opaque'){out.set(vertices);return out;}
  for(let i=0;i<vertices.length;i+=2){
    const x=vertices[i],y=vertices[i+1],ny=y/height;
    let dx=state.turn*(ny-.35)*4,dy=0;
    if(spec.id==='face')dx+=(x-width/2)*(rig.jaw_width||0)*Math.exp(-Math.pow((ny-.52)/.10,2));
    if(spec.id.includes('hair'))dx+=state.hair*ny*ny;
    if(spec.id==='eyes'){dx+=state.turn*1.3+(state.gazeX||0)*2;dy+=(state.gazeY||0)*2;}
    if(spec.id==='brows')dy=-state.smile*.6;
    if(spec.id.startsWith('mouth')){dx+=(x-width/2)*state.smile*.06;dy-=state.smile*Math.pow(Math.abs(2*x/width-1),1.5)*1.8;}
    out[i]=x+dx;out[i+1]=y+dy;
  }
  return out;
}
// Edited expression patches contain the complete painted feature and its skin.
// Blending them over open eyes or another phoneme makes both features visible.
export function expressionAlphas(state,rig) {
  const blink=clamp(state.blink),mouth=clamp(state.mouth),round=clamp(state.round);
  const config=rig.expression_states;
  if(config?.mode!=='registered-opaque'){
    const open=ease(mouth*1.65);
    return {eyes:1-blink,lids:blink,'lids-half':0,'mouth-neutral':1-open,'mouth-soft':0,
            'mouth-a':open*(1-round*.75),'mouth-o':open*round*.75};
  }
  const half=config.blink_half_threshold??.15,closed=config.blink_closed_threshold??.75;
  const soft=config.mouth_soft_threshold??.04,open=config.mouth_open_threshold??.36,rounded=config.mouth_round_threshold??.55;
  if([half,closed,soft,open,rounded].some(value=>!Number.isFinite(value)||value<0||value>1)||half>=closed||soft>=open)
    throw new Error('Invalid registered expression thresholds');
  const closedEye=blink>=closed,halfEye=blink>=half&&!closedEye,openMouth=mouth>=open;
  return {eyes:blink<half?1:0,lids:closedEye?1:0,'lids-half':halfEye?1:0,'mouth-neutral':0,
          'mouth-soft':mouth>=soft&&!openMouth?1:0,
          'mouth-a':openMouth&&round<rounded?1:0,'mouth-o':openMouth&&round>=rounded?1:0};
}
function bonePoint(point,a,b,c,d){
  const dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy);
  const x=point[0]-a[0],y=point[1]-a[1],along=(x*dx+y*dy)/(length*length);
  const normal=(x*-dy+y*dx)/length;
  const tx=d[0]-c[0],ty=d[1]-c[1],l=Math.hypot(tx,ty);
  return [c[0]+tx*along-ty/l*normal,c[1]+ty*along+tx/l*normal];
}
export function deformArm(vertices, width, height, anchors, joints){
  const a=anchors.map(p=>[p[0]*width,p[1]*height]);
  const out=new Float32Array(vertices.length);
  for(let i=0;i<vertices.length;i+=2){
    const p=[vertices[i],vertices[i+1]];
    const upper=bonePoint(p,a[0],a[1],joints[0],joints[1]);
    const lower=bonePoint(p,a[1],a[2],joints[1],joints[2]);
    const mix=ease((p[1]/height-(anchors[1][1]-.08))/.16);
    out[i]=upper[0]*(1-mix)+lower[0]*mix;out[i+1]=upper[1]*(1-mix)+lower[1]*mix;
  }
  return out;
}
