"use strict";
// World-space geometry and smooth growth. DepthRenderer handles per-pixel
// visibility; only the backend owns elapsed time and countdown progression.
(() => {
 const canvas=document.getElementById("scene-canvas"), renderer=new window.FocusDepthRenderer(canvas);
 const TAU=Math.PI*2, DEFAULT_YAW=.72, DEFAULT_PITCH=.48;
 let yaw=DEFAULT_YAW,pitch=DEFAULT_PITCH,drag=null,state={scene:"tree",progress:0,status:"work"};
 let faces=[],sceneMeshes=[],meshLayer=0,width=700,height=370,last=0,animationTime=0,dirty=true,lastBuild="",frameCount=0;
 let targetProgress=0,displayProgress=0,initialised=false;
 let monitorTime="",flowerCount=0;
 let forestLayout=[],forestTotal=0,clearTrees=0,distantTrees=0;
 const matureTrees=new Map();
 let fruitCount=0,plotFlowerCount=0,renderMs=0,geometryMs=0;
 let celebrationKey="",celebrationStart=0,celebrationYaw=DEFAULT_YAW,celebrationPitch=DEFAULT_PITCH;
 let reveal=0,landSpread=0,forestGrowth=0,zoom=1,landX=2.35,landZ=2.35;
 let viewOffsetY=0,celebrationScale=1;
 let cameraSy=0,cameraCy=1,cameraSp=0,cameraCp=1,viewScale=1;
 const seeded=(seed,salt)=>{let x=(Number(seed)^(salt*2654435761))>>>0;x=Math.imul(x^(x>>>16),2246822507);return ((x^(x>>>13))>>>0)/4294967296;};
 const weather=()=>state.weather?.kind||"neutral";
 const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
 const lerp=(a,b,t)=>a+(b-a)*t;
 const smooth=(a,b,value)=>{const t=clamp((value-a)/(b-a),0,1);return t*t*(3-2*t);};
 const mix=(a,b,t)=>a.map((v,i)=>lerp(v,b[i],t));
 const rgb=hex=>[parseInt(hex.slice(1,3),16),parseInt(hex.slice(3,5),16),parseInt(hex.slice(5,7),16)];
 const color=(value,shade=1,alpha=1)=>{const c=typeof value==="string"?rgb(value):value;return `rgba(${c.map(v=>Math.round(clamp(v*shade,0,255))).join(",")},${alpha})`;};
 function face(points,fill,alpha=1,emissive=false,normals=null){
  sceneMeshes.push({points,fill,alpha,emissive,normals});
 }
 function box(x,y,z,sx,sy,sz,fill){
  const a=x-sx/2,b=x+sx/2,c=y,d=y+sy,e=z-sz/2,f=z+sz/2;
  const side=(points,n)=>face(points,fill,1,false,points.map(()=>n));
  side([[a,c,e],[b,c,e],[b,d,e],[a,d,e]],[0,0,-1]);side([[b,c,e],[b,c,f],[b,d,f],[b,d,e]],[1,0,0]);
  side([[b,c,f],[a,c,f],[a,d,f],[b,d,f]],[0,0,1]);side([[a,c,f],[a,c,e],[a,d,e],[a,d,f]],[-1,0,0]);
  side([[a,d,e],[b,d,e],[b,d,f],[a,d,f]],[0,1,0]);
 }
 function cylinder(x,y,z,r0,r1,h,fill,n=10){
  const top=[];
  for(let i=0;i<n;i++){const a=i*TAU/n,b=(i+1)*TAU/n;const v0=[x+Math.cos(a)*r0,y,z+Math.sin(a)*r0],v1=[x+Math.cos(b)*r0,y,z+Math.sin(b)*r0],v2=[x+Math.cos(b)*r1,y+h,z+Math.sin(b)*r1],v3=[x+Math.cos(a)*r1,y+h,z+Math.sin(a)*r1],normal=q=>[Math.cos(q),(r0-r1)/Math.max(h,.001),Math.sin(q)];face([v0,v1,v2,v3],fill,1,false,[normal(a),normal(b),normal(b),normal(a)]);top.push(v3);}
  face(top,fill,1,false,top.map(()=>[0,1,0]));
 }
 function branch(a,b,r,fill){
  const d=b.map((v,i)=>v-a[i]),length=Math.hypot(...d),n=d.map(v=>v/length),ref=Math.abs(n[1])<.9?[0,1,0]:[1,0,0];
  const cross=(u,v)=>[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],u0=cross(n,ref),ul=Math.hypot(...u0),u=u0.map(v=>v/ul),v=cross(n,u);
  for(let i=0;i<6;i++){const angle=i*TAU/6,next=(i+1)*TAU/6;const p=(base,angle,radius)=>base.map((t,k)=>t+(u[k]*Math.cos(angle)+v[k]*Math.sin(angle))*radius);face([p(a,angle,r),p(a,next,r),p(b,next,r*.55),p(b,angle,r*.55)],fill);}
 }
 function sphere(x,y,z,rx,ry,rz,fill,n=16,rings=10,organic=false){
  const p=(i,j)=>{const a=i*TAU/n,b=-Math.PI/2+j*Math.PI/rings,lobe=organic?1+.045*Math.sin(a*3+.4)*Math.cos(b)**2+.022*Math.sin(b*5+a*2):1;return[x+Math.cos(a)*Math.cos(b)*rx*lobe,y+Math.sin(b)*ry*lobe,z+Math.sin(a)*Math.cos(b)*rz*lobe];};
  const normal=point=>{const v=[(point[0]-x)/Math.max(.001,rx*rx),(point[1]-y)/Math.max(.001,ry*ry),(point[2]-z)/Math.max(.001,rz*rz)],length=Math.hypot(...v)||1;return v.map(t=>t/length);};
  for(let j=0;j<rings;j++)for(let i=0;i<n;i++){const points=[p(i,j),p(i+1,j),p(i+1,j+1),p(i,j+1)];face(points,fill,1,false,points.map(normal));}
 }
 function disc(x,y,z,r,fill,plane="floor",alpha=1){const points=[];for(let i=0;i<24;i++){const a=i*TAU/24;points.push(plane==="window"?[x,y+Math.sin(a)*r,z+Math.cos(a)*r]:[x+Math.cos(a)*r,y,z+Math.sin(a)*r]);}face(points,fill,alpha,true);}
 function island(progress){
  const x=landX,z=landZ,c=.4;
  const corners=[[-x,-z+c],[-x+c,-z],[x-c,-z],[x,-z+c],[x,z-c],[x-c,z],[-x+c,z],[-x,z-c]];
  for(let i=0;i<8;i++){const a=corners[i],b=corners[(i+1)%8];face([[a[0],-.48,a[1]],[b[0],-.48,b[1]],[b[0],0,b[1]],[a[0],0,a[1]]],"#385849");}
  face(corners.map(p=>[p[0],0,p[1]]),"#789b80");
  disc(.1,.015,.1,1.02,"#315d44","floor",.28);
  for(let i=0;i<23;i++){const a=i*2.399,r=1.25+(i%4)*.19,x=Math.cos(a)*r,z=Math.sin(a)*r,h=.13+(i%3)*.05;
   for(let j=0;j<3;j++){const angle=j*TAU/3;face([[x-.026*Math.cos(angle),.01,z-.026*Math.sin(angle)],[x+.055*Math.cos(angle),h,z+.055*Math.sin(angle)],[x+.026*Math.cos(angle),.01,z+.026*Math.sin(angle)]],i%2?"#aac695":"#729a73");}
  }
  flowerCount=0;
  for(let i=0;i<12;i++){const a=i*2.399+.4,r=1.45+(i%3)*.18;flower(Math.cos(a)*r,Math.sin(a)*r,.16+(i%3)*.05,progress,i);}
  box(1.6,.025,-.85,.36,.12,.3,"#a9b39d");
 }
 function flower(x,z,height,progress,index){
  flowerCount++;
  const bloom=.45+.55*smooth(.08+(index%3)*.1,.8,progress),y=height+.02,fill=["#df8d89","#f1bb9f","#e8d8a5","#cbb2cf"][index%4];
  branch([x,.01,z],[x,y,z],.008,"#577c58");
  face([[x,height*.3,z],[x-.12,height*.56,z+.04],[x-.045,height*.64,z+.02]],"#83a477");
  face([[x,height*.5,z],[x+.11,height*.70,z-.06],[x+.035,height*.77,z-.02]],"#9ab487");
  for(let k=0;k<5;k++){const a=k*TAU/5,points=[];for(let j=0;j<8;j++){const t=j*TAU/8,radial=(.054+.049*Math.cos(t))*bloom,lateral=.036*Math.sin(t)*bloom;points.push([x+Math.cos(a)*radial-Math.sin(a)*lateral,y+.012*Math.cos(t),z+Math.sin(a)*radial+Math.cos(a)*lateral]);}face(points,fill);}
  sphere(x,y+.025,z,.027,.022,.027,"#f4d17a",8,4);
 }
 function growingTree(progress,seed=0,lod=32){
  const g=clamp(progress,0,1),stretch=smooth(0,.94,g),unfold=smooth(.04,1,g),h=.44+stretch*(2.02+seeded(seed,10)*.4),r=.035+stretch*.095;
  cylinder(0,0,0,r,r*.48,h,"#a88d65",lod>=32?16:9);
  for(let i=0;i<4;i++){const a=i*TAU/4+.25;branch([0,.15*stretch,0],[Math.cos(a)*.28*stretch,.014,Math.sin(a)*.28*stretch],r*.43,"#917750");}
  for(let i=0;i<3;i++){const y=h*(.24+i*.18);face([[-r*.72,y,.05],[r*.18,y+.026,.082],[r*.17,y+.045,.082],[-r*.73,y+.014,.05]],"#85704f");}
  const foliage=.15+unfold*1.05;
  const left=smooth(.14,.65,g),right=smooth(.27,.85,g);
  if(left>.001)branch([0,h*.57,0],[-.50*left,h*.88,.13*left],r*.46,"#b1976c");
  if(right>.001)branch([0,h*.65,0],[.56*right,h*.91,-.12*right],r*.43,"#b1976c");
  const greens=["#95ba7c","#89b083","#a7bf82","#83a97c","#9dbb8a"];
  const family=seed%4,rx=foliage*(family===1?.79:family===2?1.16:1),ry=(.17+unfold*.79)*(family===1?1.28:family===2?.78:1),rz=foliage*(.78+seeded(seed,11)*.27),cy=h+.17*unfold;
  // One closed, asymmetrical surface with large lobes and fine leaf-edge ripples.
  // Seeded proportions, lean and colour distinguish each recorded tree.
  const surface=(a,b,offset=0)=>{const rim=Math.cos(b),lobe=1+(.11+.03*family)*Math.sin(a*3+seed*.013)*rim*rim+.075*Math.sin(a*5+b*3+seed*.009)*rim+.027*Math.sin(a*9-b*5)*rim*rim,lean=.15*unfold*Math.sin(b+.3+seeded(seed,12)*2);return[Math.cos(a)*rim*(rx*lobe*shape(b)+offset)+lean,cy+Math.sin(b)*(ry*lobe+offset)+.08*unfold*Math.sin(a*2)*rim,z0(a,b,lobe,offset)];};
  const shape=b=>{const t=(Math.sin(b)+1)/2;return family===1?.60+(1-t)*(.68+.15*Math.cos(t*TAU*3)):1;};
  const z0=(a,b,lobe,offset)=>Math.sin(a)*Math.cos(b)*(rz*lobe*shape(b)+offset)+.07*unfold*Math.sin(b*2+seeded(seed,13)*3);
  const normal=p=>{const n=[p[0]/(rx*rx),(p[1]-cy)/(ry*ry),p[2]/(rz*rz)],len=Math.hypot(...n)||1;return n.map(v=>v/len);};
  const rings=lod>=32?18:lod>=14?8:5;
  for(let j=0;j<rings;j++)for(let i=0;i<lod;i++){const a=i*TAU/lod,b=-Math.PI/2+j*Math.PI/rings,points=[surface(a,b),surface(a+TAU/lod,b),surface(a+TAU/lod,b+Math.PI/rings),surface(a,b+Math.PI/rings)];face(points,greens[seed%greens.length],1,false,points.map(normal));}
  const ripe=smooth(.34,.88,g),detail=lod>=14;
  if(detail&&ripe>.005){
   const ornaments=lod>=32?7:3;
   for(let i=0;i<ornaments;i++){const a=i*2.399+seeded(seed,14)*TAU,b=-.50+(i%3)*.20,p=surface(a,b,.032),s=(.073+(i%2)*.018)*ripe;
    if(family!==1&&i%3!==2){sphere(p[0],p[1]-.032,p[2],s,s*.93,s*.85,i%2?"#dc8663":"#c96d61",lod>=32?10:6,lod>=32?6:4);branch([p[0],p[1]+s*.77,p[2]],[p[0]+.012,p[1]+s*1.45,p[2]],.008,"#6e7652");fruitCount++;}
    else{const [x,y,z]=p;face([[x-s,y,z],[x,y+s*.7,z+.02],[x+s,y,z],[x,y-s*.7,z-.01]],family===3?"#e3c6bd":"#bdd491");}
   }
   for(let i=0;i<(lod>=32?16:5);i++){const a=i*2.399+seed*.07,b=-.45+(i%5)*.24,[x,y,z]=surface(a,b,.025),s=.09*ripe;face([[x-s,y,z],[x,y+s*.7,z+.035],[x+s,y,z],[x,y-s*.5,z-.025]],i%2?"#abc88b":"#86aa73");}
  }
  // Tiny buds unfurl early, then are enclosed by the growing crown.
  if(g<.42){const bud=smooth(.025,.20,g)*(1-smooth(.28,.42,g));if(bud>.005){sphere(-.16*bud,h*.81,.08,.14*bud,.055*bud,.07*bud,"#bdd395",16,8);sphere(.15*bud,h*.87,-.05,.14*bud,.055*bud,.07*bud,"#b0cc8a",16,8);}}
 }
 function wildPlot(seed){
  for(let i=0;i<3;i++){const a=i*2.399+seeded(seed,15)*TAU,r=1.03+seeded(seed,i+16)*.33,x=Math.cos(a)*r,z=Math.sin(a)*r,y=.14+seeded(seed,i+20)*.12;
   for(let k=0;k<3;k++){const q=k*TAU/3;face([[x-.025,.012,z],[x+.075*Math.cos(q),y,z+.075*Math.sin(q)],[x+.025,.012,z]],k%2?"#9eb786":"#78986f");}
   if(i<2){face([[x-.008,.012,z],[x+.008,.012,z],[x+.008,y+.06,z],[x-.008,y+.06,z]],"#567b54");for(let k=0;k<5;k++){const q=k*TAU/5,s=.058;face([[x,y+.065,z],[x+Math.cos(q-.4)*s,y+.078,z+Math.sin(q-.4)*s],[x+Math.cos(q)*s*1.35,y+.087,z+Math.sin(q)*s*1.35],[x+Math.cos(q+.4)*s,y+.078,z+Math.sin(q+.4)*s]],i%2?"#edba9f":"#d9949e");}disc(x,y+.095,z,.022,"#edd58e");plotFlowerCount++;}
  }
 }
 // All trees share the island's world coordinates and the same depth buffer.
 // The newest tree remains at the centre; earlier records occupy spiral plots.
 function arrangeForest(){
  const records=Array.isArray(state.forest)?state.forest:[];
  forestTotal=records.length;
  const history=records.filter(item=>item.id!==state.sessionId);
  forestLayout=[];clearTrees=Math.min(30,forestTotal);distantTrees=0;
  let gx=0,gz=0,dx=1,dz=0,segment=1,walked=0,turns=0;
  for(let i=0;i<Math.min(29,history.length);i++){
   gx+=dx;gz+=dz;walked++;
   const record=history[i],seed=Number(record.seed)>>>0;
   forestLayout.push({id:record.id,seed,x:gx*2.8,z:gz*2.8,scale:.78+seeded(seed,4)*.17,alpha:1,lod:16});
   if(walked===segment){walked=0;[dx,dz]=[-dz,dx];if(++turns%2===0)segment++;}
  }
  const radius=Math.max(3.4,...forestLayout.map(t=>Math.max(Math.abs(t.x),Math.abs(t.z))+1.45));
  // Beyond 30 clear trees, compress the next ranks into distant, fading rows.
  // More records still count, without unbounded meshes or giant world bounds.
  const extra=history.slice(29,59);distantTrees=extra.length;
  for(let i=0;i<extra.length;i++){
   const record=extra[i],seed=Number(record.seed)>>>0,row=Math.floor(i/10),col=i%10;
   const side=(col-4.5)*radius*.19,back=radius*.94+row*1.15;
   forestLayout.push({id:record.id,seed,x:Math.cos(DEFAULT_YAW)*side-Math.sin(DEFAULT_YAW)*back,z:-Math.sin(DEFAULT_YAW)*side-Math.cos(DEFAULT_YAW)*back,scale:.69-row*.11,alpha:Math.max(.04,.45-row*.16),lod:10});
  }
 }
 function tree(progress){
  fruitCount=plotFlowerCount=0;island(progress);growingTree(progress,Number(state.sessionSeed)>>>0);
  if(!state.celebrating)return;
  for(const item of forestLayout){
   const growth=smooth(1.08+seeded(item.seed,6)*.08,1.92,reveal*2.8);
   if(growth<.004)continue;
   const template=matureTemplate(item);
   if(item.lod>=14)plotFlowerCount+=2;
   // Unfold cached 3D meshes rather than tessellating every historical tree on
   // every animation frame. Trunks lead, then crowns spring gently into place.
   const spring=1+.035*Math.sin(growth*Math.PI)*Math.sin(growth*Math.PI*2),sx=item.scale*(.12+.88*smooth(0,.9,growth))*spring,sy=item.scale*growth;
   for(const mesh of template)sceneMeshes.push({...mesh,alpha:mesh.alpha*item.alpha,points:mesh.points.map(p=>[item.x+p[0]*sx,p[1]*sy,item.z+p[2]*sx])});
  }
 }
 function matureTemplate(item){
  const key=item.seed+":"+item.lod;
  if(matureTrees.has(key))return matureTrees.get(key);
  const saved=sceneMeshes,savedFruit=fruitCount,savedFlowers=plotFlowerCount;sceneMeshes=[];
  disc(0,.012,0,.70,"#315d44","floor",.18);growingTree(1,item.seed,item.lod);if(item.lod>=14)wildPlot(item.seed);
  const template=sceneMeshes;sceneMeshes=saved;fruitCount=savedFruit;plotFlowerCount=savedFlowers;
  matureTrees.set(key,template);if(matureTrees.size>128)matureTrees.delete(matureTrees.keys().next().value);
  return template;
 }
 function warmForest(){
  let warmed=0;
  for(const item of forestLayout)if(!matureTrees.has(item.seed+":"+item.lod)){matureTemplate(item);if(++warmed===2)break;}
 }
 function unfoldForest(now){
  if(!state.celebrating){reveal=landSpread=forestGrowth=0;zoom=1;landX=landZ=2.35;viewOffsetY=height*(state.scene==="room"?.66:.58);return;}
  const elapsed=(now-celebrationStart)/1000;
  reveal=reduceMotion.matches?1:clamp(elapsed/2.8,0,1);
  const camera=smooth(0,.9,reveal*2.8);
  if(reveal<1){yaw=lerp(celebrationYaw,DEFAULT_YAW,camera);pitch=lerp(celebrationPitch,DEFAULT_PITCH,camera);}
  landSpread=smooth(.18,1.65,reveal*2.8);forestGrowth=smooth(1.16,1.92,reveal*2.8);
  const targetX=Math.max(2.35,...forestLayout.map(t=>Math.abs(t.x)+1.4));
  const targetZ=Math.max(2.35,...forestLayout.map(t=>Math.abs(t.z)+1.4));
  landX=lerp(2.35,targetX,landSpread);landZ=lerp(2.35,targetZ,landSpread);
  // Fit the complete projected terrain and crowns, including perspective.
  // A fixed vertical origin clips the front edge as the island spreads out.
  const bounds=[];
  for(const x of[-targetX,targetX])for(const y of[-.48,0])for(const z of[-targetZ,targetZ])bounds.push([x,y,z]);
  for(const t of[{x:0,z:0,scale:1},...forestLayout])for(const x of[t.x-1.55*t.scale,t.x+1.55*t.scale])for(const y of[0,4.35*t.scale])for(const z of[t.z-1.4*t.scale,t.z+1.4*t.scale])bounds.push([x,y,z]);
  const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
  const projected=bounds.map(([x,y,z])=>{const toward=sy*x+cy*z,depth=cp*toward+sp*(y-.85),p=11/(11-depth*.16);return[(cy*x-sy*z)*p,-(cp*(y-.85)-sp*toward)*p];});
  const xs=projected.map(p=>p[0]),ys=projected.map(p=>p[1]),minY=Math.min(...ys),maxY=Math.max(...ys);
  const baseScale=Math.min(width/9.2,height/6.3);
  const fit=Math.min(width*.92/(Math.max(...xs)-Math.min(...xs)),height*.93/(maxY-minY));
  const framing=smooth(.1,1.7,reveal*2.8);
  zoom=lerp(celebrationScale/baseScale,Math.min(1,fit/baseScale),framing);
  viewOffsetY=lerp(height*.58,height/2-(minY+maxY)/2*fit,framing);
 }
 function room(progress){
  const day=clamp(progress,0,1),overcast=["rain","cloudy","snow"].includes(weather()),sky=mix(rgb("#213b52"),rgb(overcast?"#91aab4":"#a5d8dd"),day),wall=mix(rgb("#a69a83"),rgb(overcast?"#c4c9c2":"#ded2b8"),day*.7);
  box(0,-.30,0,5.2,.3,5.2,"#6a5141");box(0,0,0,5.2,.07,5.2,"#b3916c");
  // Hide the outer wall when orbiting behind it: this is a cutaway room.
  meshLayer=-80;
  if(Math.cos(yaw)>-.08)box(0,.06,-2.55,5.2,3.65,.1,wall);
  if(Math.sin(yaw)>-.08)box(-2.55,.06,0,.1,3.65,5.2,wall);
  meshLayer=-70;
  if(Math.cos(yaw)>-.08)wallArt(day);
  if(Math.sin(yaw)>-.08)roomWindow(sky,day);
  meshLayer=0;
  for(let i=-2;i<=2;i++)box(i,.073,0,.016,.003,5.14,"#c4a580");
  // Woven rug with a soft border.
  box(.65,.08,.55,2.9,.02,2.15,"#d8bea0");box(.65,.102,.55,2.68,.003,1.93,"#c9ad87");
  for(let i=0;i<7;i++)box(-.65+i*.43,.107,.55,.02,.002,1.92,"#d9c3a3");
  // Couch, backrest, seat cushions, arms, pillow.
  box(1.53,.16,.12,1.36,.4,2.22,"#77886b");box(2.10,.56,.12,.32,.80,2.22,"#a8b28e");
  box(1.48,.55,-.43,1.03,.26,1.00,"#a6b28f");box(1.48,.55,.64,1.03,.26,1.00,"#a6b28f");
  box(1.52,.56,-1.08,1.42,.61,.22,"#b0b898");box(1.52,.56,1.32,1.42,.61,.22,"#b0b898");
  box(1.85,.79,-.59,.24,.42,.5,"#d2b88f");
  // Desk and four slender legs.
  box(-.8,1.16,-.60,1.65,.16,1.47,"#d4b080");
  for(const x of[-1.46,-.16])for(const z of[-1.2,-.03])box(x,.08,z,.095,1.08,.095,"#806043");
  // Monitor: real local wall-clock time, independent of the focus countdown.
  box(-.77,1.32,-1.02,.12,.22,.12,"#625b4f");box(-.77,1.30,-1.02,.52,.03,.30,"#736c5b");
  box(-.77,1.48,-1.02,.87,.72,.095,"#5a584d");
  meshLayer=2;
  box(-.77,1.53,-.962,.72,.56,.012,"#283e3b");
  meshLayer=3;
  monitorClock();
  // Keyboard keys, trackpad and status light make the desk feel inhabited.
  box(-.77,1.329,-.43,.62,.018,.23,"#857c68");
  for(let row=0;row<3;row++)for(let col=0;col<8;col++)box(-1.02+col*.071,1.350,-.50+row*.065,.050,.006,.043,"#c6c3ad");
  box(-.24,1.329,-.03,.12,.03,.19,"#c6c3ad");
  meshLayer=0;
  // Notebook, pen, cup and stacked books.
  box(-.85,1.324,-.09,.70,.025,.42,"#f0e2c5");box(-.52,1.351,-.05,.014,.006,.3,"#a29578");
  cylinder(-.17,1.32,-.36,.11,.12,.21,"#e4d2ac",10);disc(-.17,1.537,-.36,.088,"#71513b");
  box(-1.45,1.33,-.63,.25,.045,.39,"#7d987b");box(-1.45,1.376,-.63,.28,.04,.37,"#c9b491");
  // Desk lamp: geometry remains warm while daylight gradually takes over.
  cylinder(-1.35,1.32,-1.05,.15,.15,.035,"#806c50",10);cylinder(-1.35,1.35,-1.05,.022,.022,.48,"#716349",6);
  cylinder(-1.35,1.8,-1.05,.21,.11,.30,"#edd291",10);
  face([[-1.55,1.32,-1.4],[-.92,1.32,-1.32],[-.73,1.32,-.56],[-1.54,1.32,-.59]],"#fbe3a2",.18*(1-day),true);
  // Chair and little storage cabinet.
  box(-.71,.55,.95,.66,.10,.68,"#b49b79");box(-.71,.64,1.24,.66,.50,.10,"#bba280");
  for(const x of[-.97,-.45])for(const z of[.70,1.2])box(x,.07,z,.075,.48,.075,"#74614a");
  box(.24,.08,-2.03,.73,.62,.66,"#b09873");box(.24,.32,-1.69,.57,.25,.018,"#c2aa83");box(.24,.45,-1.667,.12,.026,.02,"#716650");
  // Tall plant in a terracotta pot.
  cylinder(1.69,.08,-1.85,.22,.31,.56,"#b99b73",9);disc(1.69,.65,-1.85,.27,"#5b5d40");
  branch([1.69,.65,-1.85],[1.69,1.9,-1.85],.024,"#768665");
  sphere(1.48,1.43,-1.82,.13,.4,.12,"#92aa80",6,3);sphere(1.88,1.55,-1.86,.13,.4,.12,"#81a075",6,3);sphere(1.69,1.89,-1.84,.11,.39,.11,"#9cb486",6,3);
 }
 function monitorClock(){
  const date=new Date();monitorTime=String(date.getHours()).padStart(2,"0")+":"+String(date.getMinutes()).padStart(2,"0");
  const segments={0:"abcdef",1:"bc",2:"abdeg",3:"abcdg",4:"bcfg",5:"acdfg",6:"acdefg",7:"abc",8:"abcdefg",9:"abcdfg"};
  const w=.095,h=.18,t=.012,z=-.949,y=1.735;
  const quad=(x,y,w,h,fill)=>face([[x,y,z],[x+w,y,z],[x+w,y+h,z],[x,y+h,z]],fill,1,true);
  for(let i=0;i<5;i++){const x=-1.055+i*.122,digit=monitorTime[i];if(digit===":"){quad(x+.026,y+.047,t,t,"#d9e6bd");quad(x+.026,y+.126,t,t,"#d9e6bd");continue;}
   const bars={a:[0,h-t,w,t],b:[w-t,h/2,t,h/2],c:[w-t,0,t,h/2],d:[0,0,w,t],e:[0,0,t,h/2],f:[0,h/2,t,h/2],g:[0,h/2-t/2,w,t]};
   for(const letter of segments[digit]){const [dx,dy,bw,bh]=bars[letter];quad(x+dx,y+dy,bw,bh,"#d9e6bd");}
  }
  quad(-1.075,2.013,.18,.008,"#749b8a");quad(-.655,2.013,.16,.008,"#749b8a");
  for(let i=0;i<3;i++)quad(-.85+i*.052,1.608,.021,.013,i===0?"#c1d79b":"#647d71");
 }
 function roomWindow(sky,day){
  const x=-2.478;
  face([[x,1.13,-1.45],[x,1.13,.7],[x,3.12,.7],[x,3.12,-1.45]],"#665e51");
  face([[x+.01,1.25,-1.33],[x+.01,1.25,.58],[x+.01,3.0,.58],[x+.01,3.0,-1.33]],sky,1,true);
  const clear=["neutral","sunny"].includes(weather());
  if(clear)disc(x+.02,2.64+day*.13,-.81+day*.77,.16,mix(rgb("#f0dfb9"),rgb("#fff0b5"),day),"window");
  if(clear&&day<.65)for(const[y,z]of[[2.25,-1.03],[2.8,.35],[1.85,-.44]])disc(x+.02,y,z,.014,"#fff4d1","window",1-day);
  for(const z of[-1.43,-.375,.70])box(x+.045,1.13,z,.08,2.02,.07,"#dac9a6");
  for(const y of[1.14,2.15,3.12])box(x+.045,y,-.375,.08,.07,2.2,"#dac9a6");
  box(x+.16,1.07,-.375,.42,.07,2.34,"#d3bf99");
  for(const z of[-1.58,.88])box(-2.3,1.1,z,.10,2.13,.23,"#c3b99f");
  // Sunlight is a translucent patch on the floor, changing with the session.
  if(clear)face([[-2.35,.081,-1.36],[-2.35,.081,.65],[.37,.082,1.42],[.37,.082,-.58]],"#f8dfa0",day*.27,true);
 }
 function weatherDetails(roomScene){
  const kind=weather();if(kind!=="rain"&&kind!=="snow")return;
  const count=roomScene?24:32;
  for(let i=0;i<count;i++){const seed=(i*.6180339887)%1,phase=(animationTime*(kind==="snow"?.15:.61)+i*.317)%1;
   if(roomScene){if(Math.sin(yaw)<=-.08)continue;const x=-2.442,z=-1.28+seed*1.80,y=1.31+(1-phase)*1.54,len=kind==="snow"?.025:.10;
    face([[x,y,z],[x,y-len,z+.021],[x,y-len,z+.033],[x,y,z+.012]],"#d1e4e7",kind==="snow"?.8:.42,true);
   }else{const x=-2.25+seed*4.5,z=-1.85+((i*.4142)%1)*3.7,y=.08+(1-phase)*3.8,len=kind==="snow"?.035:.16;
    face([[x,y,z],[x-.045,y-len,z],[x-.027,y-len,z],[x+.018,y,z]],"#c8dfe0",kind==="snow"?.8:.34,true);
   }
  }
  if(!roomScene&&kind==="rain")for(let i=0;i<5;i++)disc(Math.cos(i*1.7)*1.6,.025,Math.sin(i*1.7)*1.6,.10+(animationTime*.12+i*.21)%1*.12,"#b1cdd0","floor",.16);
 }
 function wallArt(){
  box(1.22,1.92,-2.477,1.14,.89,.07,"#6e5a42");box(1.22,1.99,-2.423,.97,.75,.012,"#dfca9e");
  face([[.77,2.0,-2.41],[1.14,2.44,-2.41],[1.42,2.0,-2.41]],"#839879");
  face([[1.12,2.0,-2.405],[1.48,2.33,-2.405],[1.68,2.0,-2.405]],"#a9b38b");
  box(-.66,2.36,-2.25,1.02,.07,.40,"#bfa47b");
  for(let i=0;i<5;i++)box(-1.02+i*.14,2.43,-2.24,.10,.32+i%2*.17,.23,i%2?"#a8af8e":"#7f997c");
 }
 function project(p){
  const [x,y,z]=p,right=cameraCy*x-cameraSy*z,toward=cameraSy*x+cameraCy*z,vertical=cameraCp*(y-.85)-cameraSp*toward,depth=cameraCp*toward+cameraSp*(y-.85),perspective=11/(11-depth*.16);
  return [width/2+right*viewScale*perspective,viewOffsetY-vertical*viewScale*perspective,depth];
 }
 const renderDetail=()=>state.celebrating&&forestTotal>12?((reveal<1||drag) ? .60 : .88):1;
 function resize(){const r=canvas.getBoundingClientRect();width=Math.max(1,r.width);height=Math.max(1,r.height);renderer.resize(width,height,renderDetail());dirty=true;}
 function draw(){
  const started=performance.now();
  const progress=displayProgress,roomScene=state.scene==="room";
  // Camera-dependent cutaway walls must be rebuilt while dragging.
  const key=`${state.scene}:${weather()}:${progress.toFixed(5)}:${state.celebrating?reveal.toFixed(3)+":"+forestTotal:"work"}:${Math.sin(yaw)>-.08}:${Math.cos(yaw)>-.08}:${new Date().getHours()}:${new Date().getMinutes()}`;
  if(key!==lastBuild){sceneMeshes=[];if(roomScene)room(progress);else tree(progress);lastBuild=key;}
  const base=sceneMeshes;sceneMeshes=[];weatherDetails(roomScene);const animated=sceneMeshes;sceneMeshes=base;
  cameraSy=Math.sin(yaw);cameraCy=Math.cos(yaw);cameraSp=Math.sin(pitch);cameraCp=Math.cos(pitch);viewScale=Math.min(width/9.2,height/(roomScene?7.8:6.3))*zoom;
  const windX=Math.sin(animationTime*.86)*.014,windZ=Math.sin(animationTime*.63)*.006,flutter=Math.sin(animationTime*1.7)*.009;
  const eye=[Math.sin(yaw)*Math.cos(pitch),Math.sin(pitch),Math.cos(yaw)*Math.cos(pitch)];
  faces=base.concat(animated).filter(mesh=>{if(!mesh.normals)return true;const n=mesh.normals;let dot=0;for(const v of n)dot+=v[0]*eye[0]+v[1]*eye[1]+v[2]*eye[2];return dot/n.length>-.05;}).map((mesh,index)=>{const points=mesh.points.map(p=>{if(!roomScene&&p[1]>.2&&index<base.length){const height=Math.max(0,p[1]);return project([p[0]+windX*height*height,p[1]+flutter*smooth(.8,2,height),p[2]+windZ*height]);}return project(p);});return {mesh,points,depth:points.reduce((sum,p)=>sum+p[2],0)/points.length};});
  const ambient=roomScene?lerp(.79,1.05,progress):1;
  const beforeRaster=performance.now();geometryMs=beforeRaster-started;
  renderer.render(faces,ambient);
  renderMs=performance.now()-beforeRaster;
  frameCount++;
 }
 const reduceMotion=window.matchMedia("(prefers-reduced-motion: reduce)");
 function loop(now){requestAnimationFrame(loop);if(document.hidden){last=now;return;}if(state.scene==="room"){const date=new Date(),clock=String(date.getHours()).padStart(2,"0")+":"+String(date.getMinutes()).padStart(2,"0");if(clock!==monitorTime)dirty=true;}const growing=Math.abs(displayProgress-targetProgress)>.00001;if(state.celebrating&&reveal>=1&&!dirty&&!drag&&!growing)return;if((state.status==="paused"||reduceMotion.matches)&&!dirty&&!growing&&!(state.celebrating&&reveal<1))return;if(now-last<(renderer.mode==="software-depth"?40:20)&&!dirty)return;const dt=Math.min(.1,(now-last)/1000);last=now;
  unfoldForest(now);
  if(renderer.detail!==renderDetail())renderer.resize(width,height,renderDetail());
  if(state.celebrating&&reveal<.45)warmForest();
  if(state.status!=="paused"||!initialised){displayProgress=reduceMotion.matches?targetProgress:lerp(displayProgress,targetProgress,1-Math.exp(-dt/0.55));if(Math.abs(displayProgress-targetProgress)<.00001)displayProgress=targetProgress;}
  if(state.status!=="paused"&&!reduceMotion.matches)animationTime+=dt;
  draw();dirty=false;}
 function reset(){yaw=DEFAULT_YAW;pitch=DEFAULT_PITCH;dirty=true;}
 canvas.addEventListener("pointerdown",event=>{if(event.button!==0||(state.celebrating&&reveal<1))return;drag={x:event.clientX,y:event.clientY,yaw,pitch};canvas.setPointerCapture(event.pointerId);canvas.classList.add("dragging");});
 canvas.addEventListener("pointermove",event=>{if(!drag)return;yaw=drag.yaw+(event.clientX-drag.x)*.008;pitch=clamp(drag.pitch+(event.clientY-drag.y)*.004,.18,1.03);dirty=true;});
 function release(){drag=null;canvas.classList.remove("dragging");dirty=true;}
 canvas.addEventListener("pointerup",release);canvas.addEventListener("pointercancel",release);canvas.addEventListener("lostpointercapture",release);canvas.addEventListener("dblclick",reset);
 canvas.addEventListener("keydown",event=>{if(event.key==="ArrowLeft")yaw-=.14;else if(event.key==="ArrowRight")yaw+=.14;else if(event.key==="ArrowUp")pitch=clamp(pitch+.06,.18,1.03);else if(event.key==="ArrowDown")pitch=clamp(pitch-.06,.18,1.03);else if(event.key==="Home")reset();else return;event.preventDefault();dirty=true;});
 document.getElementById("reset-view").onclick=reset;
 new ResizeObserver(resize).observe(canvas);resize();requestAnimationFrame(loop);
 window.focusScene3D={
  update(next){const changedScene=state.scene!==next.scene;state={...next};const key=state.celebrating?String(state.sessionId):"";
   if(key&&key!==celebrationKey){celebrationStart=performance.now();celebrationScale=Math.min(width/9.2,height/6.3)*zoom;celebrationYaw=DEFAULT_YAW+((yaw-DEFAULT_YAW+Math.PI)%TAU+TAU)%TAU-Math.PI;celebrationPitch=pitch;reveal=0;drag=null;}
   celebrationKey=key;arrangeForest();lastBuild="";
   const nextProgress=clamp(Number(state.progress)||0,0,1);if(!initialised||changedScene||state.status==="paused"){displayProgress=nextProgress;initialised=true;}targetProgress=nextProgress;if(changedScene)reset();resize();dirty=true;},
  reset,
  diagnostics(){return {yaw,pitch,progress:Number(state.progress)||0,renderedProgress:displayProgress,growthAnimating:Math.abs(targetProgress-displayProgress)>.00001,animationTime,scene:state.scene,weather:weather(),flowerCount,plotFlowerCount,fruitCount,renderMs,geometryMs,cachedTrees:matureTrees.size,monitorTime,meshes:sceneMeshes.length,frames:frameCount,daylight:state.scene==="room"?displayProgress:0,celebrating:Boolean(state.celebrating),reveal,landSpread,forestGrowth,landX,landZ,zoom,forestTotal,clearTrees:state.celebrating?clearTrees:1,distantTrees:state.celebrating?distantTrees:0,forestRendered:state.celebrating?Math.min(1,forestTotal)+forestLayout.length:1,...renderer.diagnostics()};}
 };
})();
