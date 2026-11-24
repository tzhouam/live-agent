import {teacherState,armJoints,handSpec,handPose,segmentTransform,deformHead,expressionAlphas,deformArm,clamp} from './teacher-rig.js';

const DEFAULT_MODEL='/assets/teacher-mesh/rig-v7.json';
export async function createTeacherAvatar({container,fallbackCanvas,modelUrl=DEFAULT_MODEL,onFallback=()=>{}}={}){
  if(!container||!fallbackCanvas)throw new Error('Avatar requires a stage and fallback canvas');
  const url=new URL(modelUrl,location.href);
  if(url.origin!==location.origin)throw new Error('Avatar model must be served locally');
  const response=await fetch(url);if(!response.ok)throw new Error('Teacher model could not load');
  const rig=await response.json();
  if(rig.version!==1||rig.model!=='teacher-mesh-v1'||rig.canvas?.[0]!==480||rig.canvas?.[1]!==864)throw new Error('Unsupported teacher model');
  if(rig.arm_segments!==undefined&&!Array.isArray(rig.arm_segments))throw new Error('Unsupported arm sections');
  const segmented=Array.isArray(rig.arm_segments)&&rig.arm_segments.length>0;
  const authoredLayers=rig.layers.filter(layer=>!segmented||layer.group!=='arm');
  const coherentHead=rig.coherent_head===true||rig.expression_states?.mode==='registered-opaque';
  const P=await import('/vendor/pixi/pixi-8.22.0.min.mjs');
  const app=new P.Application();
  try{
    await app.init({width:480,height:864,resolution:1,autoDensity:false,antialias:true,
      backgroundAlpha:0,preference:'webgl',preserveDrawingBuffer:true,autoStart:false});
  }catch(error){
    // A failed WebGL setup may still have allocated application resources.
    try{app.destroy(true,{children:true});}catch{}
    throw error;
  }
  const webgl=app.canvas;
  webgl.className='teacher-avatar-canvas';webgl.setAttribute('aria-label','AI teacher avatar');
  Object.assign(webgl.style,{position:'absolute',inset:'0',width:'100%',height:'100%',objectFit:'contain'});
  const state={active:true,model:rig.model,renderer:'mesh',canvas:webgl,rig};
  const layers=[],hands=[],segments=[],ownedTextures=[];
  const assetUrl=name=>{const u=new URL(name,url);if(u.origin!==location.origin)throw new Error('Non-local avatar asset');return u.href;};
  async function texture(name){return P.Assets.load(assetUrl(name));}
  function ownedTexture(texture,destroySource=false){ownedTextures.push([texture,destroySource]);return texture;}
  function mesh(tex,width,height,grid){
    const object=new P.MeshPlane({texture:tex,verticesX:grid[0],verticesY:grid[1]});
    // MeshPlane uses source-image coordinates; work in the model's authored units.
    const positions=object.geometry.getBuffer('aPosition').data;
    const original=Float32Array.from(positions,(value,i)=>value*(i%2?height/tex.height:width/tex.width));
    object.geometry.getBuffer('aPosition').data.set(original);object.geometry.getBuffer('aPosition').update();
    return {object,original,width,height};
  }
  let dead=false;
  function fail(reason){
    if(!state.active)return;
    state.active=false;fallbackCanvas.style.visibility='visible';webgl.hidden=true;
    try{onFallback(reason);}catch{}
  }
  function cleanup(){
    if(dead)return;dead=true;state.active=false;
    fallbackCanvas.style.visibility='visible';webgl.removeEventListener('webglcontextlost',contextLost);
    webgl.remove();
    try{app.destroy(false,{children:true,texture:false,textureSource:false});}
    finally{
      // Dispose only per-instance masks/views. Assets.load textures are shared.
      for(const [texture,destroySource] of ownedTextures)texture.destroy(destroySource);
      ownedTextures.length=0;
    }
  }
  const contextLost=e=>{e.preventDefault();fail('webgl_context_lost');};
  try{
    // Start independent local image requests together instead of accumulating
    // one network round trip for every layer in a cold classroom.
    const handAssets=Object.keys(rig.hands).flatMap(name=>[1,-1].map(side=>handSpec(rig,name,side).asset));
    const assets=[rig.background,...authoredLayers.map(layer=>layer.asset),...(segmented?rig.arm_segments.map(part=>part.asset):[]),...handAssets];
    await Promise.all([...new Set(assets)].map(texture));
    const background=await texture(rig.background);
    if(rig.camera){
      const {scale,pivot}=rig.camera;
      app.stage.scale.set(scale);app.stage.position.set(pivot[0]*(1-scale),pivot[1]*(1-scale));
    }
    const backdrop=new P.Sprite(background);backdrop.width=480;backdrop.height=864;app.stage.addChild(backdrop);
    const person=new P.Container();app.stage.addChild(person);
    const upperSegments=segmented?new P.Container():null;
    if(upperSegments)person.addChild(upperSegments);
    const headPivot=rig.head_pivot||[240,360];
    const head=new P.Container();head.pivot.set(...headPivot);head.position.set(...headPivot);head.scale.set(rig.head_scale);
    // Body and head layers share authored coordinates, maintaining neck overlap.
    for(const layer of authoredLayers){
      const tex=await texture(layer.asset),[x,y,w,h]=layer.rect;
      const item=mesh(tex,w,h,layer.grid);Object.assign(item,{spec:layer});
      if(layer.group==='arm'){
        item.object.position.set(0,0);person.addChild(item.object);
      }else{
        item.object.position.set(x,y);(layer.group==='head'?head:person).addChild(item.object);
      }
      layers.push(item);
    }
    // Put back hair behind the bust; its movement remains attached to the head.
    const back=layers.find(v=>v.spec.id==='back-hair');
    const backGroup=new P.Container();backGroup.pivot.set(...headPivot);backGroup.position.set(...headPivot);
    if(back){head.removeChild(back.object);backGroup.addChild(back.object);}
    person.addChildAt(backGroup,0);
    backGroup.scale.set(rig.head_scale);
    // The painted neck is behind the jacket/collar. Facial details remain
    // above the body, but never cover its neckline with a rectangular skin edge.
    const face=layers.find(v=>v.spec.id==='face');head.removeChild(face.object);
    const faceGroup=new P.Container();faceGroup.pivot.set(...headPivot);faceGroup.position.set(...headPivot);faceGroup.scale.set(rig.head_scale);
    faceGroup.addChild(face.object);person.addChildAt(faceGroup,1);
    if(rig.neck_mask){
      const neckMask=new P.Graphics().poly(rig.neck_mask.flat()).fill(0xffffff);
      faceGroup.addChild(neckMask);face.object.mask=neckMask;
    }
    // Blend the independently authored collar's neck into the face underneath.
    const body=layers.find(v=>v.spec.id==='body');
    if(rig.collar_blend!==false){
    const blendCanvas=document.createElement('canvas');blendCanvas.width=254;blendCanvas.height=314;
    const blendContext=blendCanvas.getContext('2d');
    const gradient=blendContext.createLinearGradient(0,0,0,24);
    gradient.addColorStop(0,'rgba(255,255,255,0)');gradient.addColorStop(1,'white');
    blendContext.fillStyle=gradient;blendContext.fillRect(0,0,254,314);
    const collarMask=new P.Sprite(ownedTexture(P.Texture.from(blendCanvas,true),true));collarMask.position.set(113,357);
    person.addChild(collarMask);body.object.mask=collarMask;
    }
    if(segmented){
      if(rig.arm_depth==='over-body')person.addChild(upperSegments);
      const lowerSegments=new P.Container();person.addChild(lowerSegments);
      for(const spec of rig.arm_segments){
        if(![-1,1].includes(spec.side))throw new Error('Invalid painted arm side');
        // Validate attachment points before accepting the model. Source anchors
        // encode the left/right artwork explicitly; neither side is mirrored.
        segmentTransform(spec,armJoints(rig,spec.side,teacherState({},rig)));
        const tex=await texture(spec.asset),item=mesh(tex,...spec.size,[2,2]);
        Object.assign(item,{spec});
        (spec.bone==='upper'?upperSegments:lowerSegments).addChild(item.object);
        segments.push(item);
      }
    }
    person.addChild(head);
    const deskTexture=ownedTexture(new P.Texture({source:background.source,frame:new P.Rectangle(0,background.height*rig.tabletop_y/864,background.width,background.height*(864-rig.tabletop_y)/864)}));
    const desk=new P.Sprite(deskTexture);desk.position.set(0,rig.tabletop_y);desk.width=480;desk.height=864-rig.tabletop_y;app.stage.addChild(desk);
    // Forearms/hands are above the tabletop. The same arm mesh is drawn once
    // more through a desk-area mask, preserving correct torso/desk depth.
    const forearms=new P.Container();app.stage.addChild(forearms);
    const mask=new P.Graphics().rect(0,rig.tabletop_y,480,rig.foreground_y-rig.tabletop_y).fill(0xffffff);
    app.stage.addChild(mask);forearms.mask=mask;
    for(const item of layers.filter(v=>v.spec.group==='arm')){
      const front=new P.Mesh({geometry:item.object.geometry,texture:item.object.texture});
      forearms.addChild(front);item.front=front;
    }
    for(const item of segments.filter(item=>item.spec.bone!=='upper')){
      const front=new P.Mesh({geometry:item.object.geometry,texture:item.object.texture});
      forearms.addChild(front);item.front=front;
    }
    const contactGroup=new P.Container();app.stage.addChild(contactGroup);
    const handGroup=new P.Container();app.stage.addChild(handGroup);
    let contactTexture=null;
    if([1,-1].some(side=>handSpec(rig,'relaxed',side).contact_shadow)){
      const contactCanvas=document.createElement('canvas');contactCanvas.width=96;contactCanvas.height=32;
      const c=contactCanvas.getContext('2d');c.scale(1,1/3);
      const g=c.createRadialGradient(48,48,2,48,48,45);
      g.addColorStop(0,'rgba(67,39,23,.28)');g.addColorStop(1,'rgba(67,39,23,0)');
      c.fillStyle=g;c.fillRect(0,0,96,96);
      contactTexture=ownedTexture(P.Texture.from(contactCanvas,true),true);
    }
    for(const side of [1,-1]){
      const group=new P.Container();handGroup.addChild(group);
      async function handPart(spec){
        const part=new P.Container(),sprite=new P.Sprite(await texture(spec.asset));
        sprite.width=spec.size[0];sprite.height=spec.size[1];sprite.anchor.set(...spec.anchor);
        part.addChild(sprite);
        if(spec.skin_mask){
          const points=spec.skin_mask.flatMap(([x,y])=>[(x-spec.anchor[0])*spec.size[0],(y-spec.anchor[1])*spec.size[1]]);
          const mask=new P.Graphics().poly(points).fill(0xffffff);
          part.addChild(mask);sprite.mask=mask;
        }
        if(spec.mirror)part.scale.x=-1;group.addChild(part);return part;
      }
      const relaxedSpec=handSpec(rig,'relaxed',side);
      const relaxed=await handPart(relaxedSpec),open=await handPart(handSpec(rig,'open',side));
      const point=await handPart(handSpec(rig,'point',side)),wave=await handPart(handSpec(rig,'wave',side));
      let contact=null;
      if(contactTexture&&relaxedSpec.contact_shadow){contact=new P.Sprite(contactTexture);contact.anchor.set(.5);contactGroup.addChild(contact);}
      hands.push({side,group,relaxed,open,point,wave,contact,relaxedSpec});
    }
    const lipTexture=ownedTexture(new P.Texture({source:background.source,frame:new P.Rectangle(0,background.height*rig.foreground_y/864,background.width,background.height*(864-rig.foreground_y)/864)}));
    const lip=new P.Sprite(lipTexture);lip.position.set(0,rig.foreground_y);lip.width=480;lip.height=864-rig.foreground_y;app.stage.addChild(lip);
    // QC already consumes this size on the backend; keep native display and
    // captureStream recording unchanged while reducing synchronous readback.
    const captureCanvas=document.createElement('canvas');captureCanvas.width=320;captureCanvas.height=576;
    const captureContext=captureCanvas.getContext('2d');
    let previousMotion=null,hairOffset=0,hairVelocity=0;
    state.render=input=>{
      if(!state.active)return false;
      try{
        const s=teacherState(input,rig);
        const expressions=expressionAlphas(s,rig);
        const time=Math.max(0,input.motionTime||0);
        if(previousMotion===null||time<previousMotion){hairOffset=hairVelocity=0;}
        const dt=Math.min(.05,Math.max(0,time-(previousMotion??time)));previousMotion=time;
        const physics=rig.hair_physics,target=s.turn*2-s.tilt*30;
        hairVelocity+=(physics.stiffness*(target-hairOffset)-physics.damping*hairVelocity)*dt;
        hairOffset=clamp(hairOffset+hairVelocity*dt,-physics.max_offset,physics.max_offset);
        s.hair=s.hair*.25+hairOffset;
        head.rotation=s.tilt;head.position.set(headPivot[0]+s.turn*12,headPivot[1]+s.breath+s.nod);
        backGroup.rotation=s.tilt;backGroup.position.copyFrom(head.position);
        faceGroup.rotation=s.tilt;faceGroup.position.copyFrom(head.position);
        for(const item of layers){
          const {object,original,spec}=item;const buf=object.geometry.getBuffer('aPosition');
          if(spec.group==='arm')buf.data.set(deformArm(original,item.width,item.height,spec.anchors,armJoints(rig,spec.side,s)));
          else if(spec.group==='head')deformHead(original,item.width,item.height,spec,s,rig,buf.data);
          else{
            for(let i=0;i<original.length;i+=2){
              const x=original[i],y=original[i+1],ny=y/item.height;
              let dx=0,dy=0;
              if(spec.group==='body'){dx=(x-item.width/2)*s.breath*.002;dy=-s.breath*(1-ny)*.28;}
              buf.data[i]=x+dx;buf.data[i+1]=y+dy;
            }
          }
          buf.update();
          if(Object.hasOwn(expressions,spec.id))object.alpha=expressions[spec.id];
          if(spec.id==='eyes'){
            object.scale.y=coherentHead?1:1-s.blink*.86;
            object.y=spec.rect[1]+(coherentHead?0:s.blink*12);
          }
        }
        for(const item of segments){
          const transform=segmentTransform(item.spec,armJoints(rig,item.spec.side,s));
          for(const object of [item.object,item.front])if(object){
            object.position.set(...transform.position);object.rotation=transform.rotation;object.scale.set(transform.scale);
          }
        }
        for(const hand of hands){
          const pose=handPose(rig,hand.side,s,input),wrist=pose.wrist;
          hand.group.position.set(...wrist);
          for(const [name,shape] of Object.entries(pose.shapes)){
            hand[name].rotation=shape.rotation;hand[name].alpha=shape.alpha;
          }
          if(hand.contact){
            const restRotation=hand.relaxed.rotation;
            const [w,h]=hand.relaxedSpec.size,[ax,ay]=hand.relaxedSpec.anchor;
            const dx=(hand.relaxedSpec.mirror?-1:1)*(.5-ax)*w,dy=(.5-ay)*h;
            hand.contact.position.set(wrist[0]+dx*Math.cos(restRotation)-dy*Math.sin(restRotation),
                                      wrist[1]+dx*Math.sin(restRotation)+dy*Math.cos(restRotation)+7);
            hand.contact.alpha=pose.shapes.relaxed.alpha*clamp((wrist[1]-rig.tabletop_y)/24);
            hand.contact.width=w*1.05;hand.contact.height=18;
          }
        }
        app.renderer.render(app.stage);return true;
      }catch(error){fail('render_failed');return false;}
    };
    state.capture=()=>{
      if(!state.active)return null;
      try{captureContext.drawImage(webgl,0,0,320,576);return captureCanvas.toDataURL('image/jpeg',.70);}catch{fail('capture_failed');return null;}
    };
    state.reset=()=>{previousMotion=null;hairOffset=hairVelocity=0;return state.render({gesture:'idle',motionTime:0,mouthOpen:0,mouthRound:0});};
    state.destroy=cleanup;
    state.debug=()=>({active:state.active,model:state.model,canvas:[webgl.width,webgl.height],layers:layers.length,
                     ...(segmented?{arm_segments:segments.length}: {})});
    container.appendChild(webgl);webgl.addEventListener('webglcontextlost',contextLost);
    state.reset();fallbackCanvas.style.visibility='hidden';return state;
  }catch(error){cleanup();throw error;}
}
