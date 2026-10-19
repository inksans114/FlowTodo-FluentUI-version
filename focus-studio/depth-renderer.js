"use strict";
// Depth is tested per pixel, including in the software fallback. Face-average
// painter sorting cannot correctly draw intersecting surfaces or rotated rooms.
(() => {
 const LIGHT=[-.37,.83,.40];
 const normalise=n=>{const length=Math.hypot(...n)||1;return n.map(v=>v/length);};
 const light=normalise(LIGHT);
 function faceNormal(points){
  const a=points[0];
  for(let i=1;i<points.length-1;i++){
   const u=points[i].map((v,k)=>v-a[k]),v=points[i+1].map((p,k)=>p-a[k]);
   const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
   if(Math.hypot(...n)>1e-8)return normalise(n);
  }
  return [0,1,0];
 }
 function shade(n,emissive){if(emissive)return 1;const d=Math.abs(n[0]*light[0]+n[1]*light[1]+n[2]*light[2]);return .76+.24*d;}
 function unpack(face,ambient){
  let c=face.mesh.fill;
  if(typeof c==="string")c=[parseInt(c.slice(1,3),16),parseInt(c.slice(3,5),16),parseInt(c.slice(5,7),16)];
  let normals=face.mesh.normals;
  if(!normals){const normal=faceNormal(face.mesh.points);normals=face.points.map(()=>normal);}
  return {color:c.map(v=>Math.min(255,v*(face.mesh.emissive?1:ambient))),normals};
 }
 class DepthRenderer {
  constructor(canvas){
   this.canvas=canvas;this.lost=false;this.triangles=0;this.frames=0;
   this.gl=location.hash==="#software"?null:canvas.getContext("webgl",{alpha:true,antialias:true,premultipliedAlpha:true,preserveDrawingBuffer:false,powerPreference:"low-power"});
   if(this.gl){this.mode="webgl-depth";this.initGL();canvas.addEventListener("webglcontextlost",event=>{event.preventDefault();this.lost=true;});canvas.addEventListener("webglcontextrestored",()=>{this.initGL();this.lost=false;});}
   else{this.mode="software-depth";this.ctx=canvas.getContext("2d",{alpha:true});this.work=document.createElement("canvas");this.workCtx=this.work.getContext("2d",{alpha:true});}
  }
  initGL(){
   const gl=this.gl;
   const compile=(type,source)=>{const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(shader));return shader;};
   const vs=compile(gl.VERTEX_SHADER,`attribute vec3 position;attribute vec3 normal;attribute vec4 color;attribute float lit;varying vec3 vNormal;varying vec4 vColor;varying float vLit;void main(){gl_Position=vec4(position,1.0);vNormal=normal;vColor=color;vLit=lit;}`);
   const fs=compile(gl.FRAGMENT_SHADER,`precision mediump float;varying vec3 vNormal;varying vec4 vColor;varying float vLit;void main(){float shade=mix(1.0,0.76+0.24*abs(dot(normalize(vNormal),normalize(vec3(-0.37,0.83,0.40)))),vLit);vec4 c=vec4(vColor.rgb*shade,vColor.a);gl_FragColor=vec4(c.rgb*c.a,c.a);}`);
   this.program=gl.createProgram();gl.attachShader(this.program,vs);gl.attachShader(this.program,fs);gl.linkProgram(this.program);
   if(!gl.getProgramParameter(this.program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(this.program));
   gl.deleteShader(vs);gl.deleteShader(fs);this.buffer=gl.createBuffer();
   this.attributes=[['position',3,0],['normal',3,12],['color',4,24],['lit',1,40]].map(([name,size,offset])=>({location:gl.getAttribLocation(this.program,name),size,offset}));
   gl.enable(gl.DEPTH_TEST);gl.depthFunc(gl.LEQUAL);gl.disable(gl.CULL_FACE);
  }
  resize(width,height,detail=1){
   this.width=width;this.height=height;this.detail=detail;
   const dpr=this.gl?Math.min(window.devicePixelRatio||1,2):Math.min(1.5,1400/width)*detail;
   const w=Math.max(1,Math.round(width*dpr)),h=Math.max(1,Math.round(height*dpr));
   if(this.canvas.width===w&&this.canvas.height===h&&(this.gl||this.image))return;
   this.canvas.width=w;this.canvas.height=h;
   if(this.gl)this.gl.viewport(0,0,w,h);
   else{this.work.width=w;this.work.height=h;this.image=this.workCtx.createImageData(w,h);this.depth=new Float32Array(w*h);this.scale=dpr;}
  }
  render(faces,ambient=1){
   if(this.lost)return;
   this.triangles=faces.reduce((n,f)=>n+Math.max(0,f.points.length-2),0);
   const opaque=faces.filter(f=>f.mesh.alpha===1),transparent=faces.filter(f=>f.mesh.alpha<1).sort((a,b)=>a.depth-b.depth);
   if(this.gl){
    const gl=this.gl;gl.clearColor(0,0,0,0);gl.clearDepth(1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(this.program);gl.bindBuffer(gl.ARRAY_BUFFER,this.buffer);
    for(const attr of this.attributes){gl.enableVertexAttribArray(attr.location);gl.vertexAttribPointer(attr.location,attr.size,gl.FLOAT,false,44,attr.offset);}
    const submit=group=>{
     let count=group.reduce((n,f)=>n+(f.points.length-2)*3,0),data=new Float32Array(count*11),at=0;
     for(const face of group){const {color,normals}=unpack(face,ambient);for(let i=1;i<face.points.length-1;i++)for(const index of[0,i,i+1]){
      const p=face.points[index],n=normals[index];
      data[at++]=p[0]/this.width*2-1;data[at++]=1-p[1]/this.height*2;data[at++]=-p[2]/20;
      data[at++]=n[0];data[at++]=n[1];data[at++]=n[2];
      data[at++]=color[0]/255;data[at++]=color[1]/255;data[at++]=color[2]/255;data[at++]=face.mesh.alpha;data[at++]=face.mesh.emissive?0:1;
     }}
     gl.bufferData(gl.ARRAY_BUFFER,data,gl.DYNAMIC_DRAW);gl.drawArrays(gl.TRIANGLES,0,count);
    };
    gl.disable(gl.BLEND);gl.depthMask(true);submit(opaque);
    gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);gl.depthMask(false);submit(transparent);gl.depthMask(true);
   }else{
    this.depth.fill(-Infinity);this.image.data.fill(0);
    for(const face of opaque.concat(transparent)){const {color,normals}=unpack(face,ambient);const points=face.points.map(p=>[p[0]*this.scale,p[1]*this.scale,p[2]]),colors=normals.map(n=>color.map(v=>v*shade(n,face.mesh.emissive)));for(let i=1;i<points.length-1;i++)this.triangle([points[0],points[i],points[i+1]],[colors[0],colors[i],colors[i+1]],face.mesh.alpha);}
    this.workCtx.putImageData(this.image,0,0);
    // Publish one completed frame; never clear the visible surface mid-draw.
    this.ctx.globalCompositeOperation="copy";this.ctx.drawImage(this.work,0,0,this.canvas.width,this.canvas.height);this.ctx.globalCompositeOperation="source-over";
   }
   this.frames++;
  }
  triangle(v,c,alpha){
   const [a,b,d]=v,w=this.work.width,h=this.work.height;
   const area=(b[1]-d[1])*(a[0]-d[0])+(d[0]-b[0])*(a[1]-d[1]);if(Math.abs(area)<1e-8)return;
   const x0=Math.max(0,Math.floor(Math.min(a[0],b[0],d[0]))),x1=Math.min(w-1,Math.ceil(Math.max(a[0],b[0],d[0]))),y0=Math.max(0,Math.floor(Math.min(a[1],b[1],d[1]))),y1=Math.min(h-1,Math.ceil(Math.max(a[1],b[1],d[1])));
   const ax=(b[1]-d[1])/area,ay=(d[0]-b[0])/area,bx=(d[1]-a[1])/area,by=(a[0]-d[0])/area,pixels=this.image.data,depth=this.depth;
   const ar=c[0][0]-c[2][0],br=c[1][0]-c[2][0],ag=c[0][1]-c[2][1],bg=c[1][1]-c[2][1],ab=c[0][2]-c[2][2],bb=c[1][2]-c[2][2],az=a[2]-d[2],bz=b[2]-d[2];
   const rx=ar*ax+br*bx,gx=ag*ax+bg*bx,blx=ab*ax+bb*bx,zx=az*ax+bz*bx,opaque=alpha===1;
   for(let y=y0;y<=y1;y++){
    let u=ax*(x0+.5-d[0])+ay*(y+.5-d[1]),t=bx*(x0+.5-d[0])+by*(y+.5-d[1]),r=c[2][0]+ar*u+br*t,g=c[2][1]+ag*u+bg*t,blue=c[2][2]+ab*u+bb*t,z=d[2]+az*u+bz*t,index=y*w+x0;
    for(let x=x0;x<=x1;x++,index++,u+=ax,t+=bx,r+=rx,g+=gx,blue+=blx,z+=zx){
     if(u<-.00001||t<-.00001||1-u-t<-.00001||z<depth[index]-1e-6)continue;
     const offset=index*4;
     if(opaque){depth[index]=z;pixels[offset]=r;pixels[offset+1]=g;pixels[offset+2]=blue;pixels[offset+3]=255;}
     else{const previousAlpha=pixels[offset+3]/255,behind=previousAlpha*(1-alpha),nextAlpha=alpha+behind,divide=1/Math.max(.00001,nextAlpha);pixels[offset]=(r*alpha+pixels[offset]*behind)*divide;pixels[offset+1]=(g*alpha+pixels[offset+1]*behind)*divide;pixels[offset+2]=(blue*alpha+pixels[offset+2]*behind)*divide;pixels[offset+3]=nextAlpha*255;}
    }
   }
  }
  diagnostics(){return {mode:this.mode,depthTest:true,contextLost:this.lost,triangles:this.triangles,frames:this.frames};}
 }
 DepthRenderer.occlusionProbe=()=>{
  const canvas=document.createElement("canvas"),r=new DepthRenderer(canvas);r.resize(32,32);
  const face=(fill,points)=>({points,depth:0,mesh:{points,fill,alpha:1,emissive:true}});
  const red=face("#ff0000",[[2,2,1],[30,2,-1],[2,30,1]]),green=face("#00ff00",[[2,2,-1],[30,2,1],[2,30,-1]]);
  const read=(x,y)=>{const sx=Math.floor(x*r.canvas.width/32),sy=Math.floor(y*r.canvas.height/32);if(r.gl){const p=new Uint8Array(4);r.gl.readPixels(sx,r.canvas.height-sy-1,1,1,r.gl.RGBA,r.gl.UNSIGNED_BYTE,p);return [...p];}return [...r.ctx.getImageData(sx,sy,1,1).data];};
  r.render([red,green]);const first=[read(5,5),read(24,4)];r.render([green,red]);const second=[read(5,5),read(24,4)];
  const result={mode:r.mode,orderIndependent:JSON.stringify(first)===JSON.stringify(second),nearRed:first[0][0]>240&&first[0][1]<10,nearGreen:first[1][1]>240&&first[1][0]<10};
  if(r.gl){r.gl.deleteBuffer(r.buffer);r.gl.deleteProgram(r.program);r.gl.getExtension("WEBGL_lose_context")?.loseContext();}
  return result;
 };
 window.FocusDepthRenderer=DepthRenderer;
})();
