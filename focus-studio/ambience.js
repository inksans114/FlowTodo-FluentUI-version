"use strict";
// Screen-wide weather; the persistent forest lives in scene3d.js.
// Frames are assembled offscreen and published once; no moving CSS blur layers.
(() => {
 const rainCanvas=document.getElementById("rain-curtain"),rainCtx=rainCanvas.getContext("2d");
 const rainFrame=document.createElement("canvas"),rc=rainFrame.getContext("2d");
 const reduced=matchMedia("(prefers-reduced-motion: reduce)");
 let state={},width=1,height=1,clock=0,last=0,lastRain=0,dirty=true,rainFrames=0;
 const random=(seed,salt)=>{let x=(Number(seed)^(salt*2654435761))>>>0;x=Math.imul(x^(x>>>16),2246822507);x=Math.imul(x^(x>>>13),3266489909);return ((x^(x>>>16))>>>0)/4294967296;};
 function resize(){width=innerWidth;height=innerHeight;for(const c of[rainCanvas,rainFrame]){c.width=width;c.height=height;}dirty=true;}
 function publish(ctx,source){ctx.globalCompositeOperation="copy";ctx.drawImage(source,0,0);ctx.globalCompositeOperation="source-over";}
 function drawRain(now){
  rc.clearRect(0,0,width,height);const rain=state.weather?.kind==="rain",snow=state.weather?.kind==="snow";
  if((rain||snow)&&!reduced.matches){
   const count=rain?Math.min(260,Math.max(100,Math.round(width*height/6500))):75;
   for(let i=0;i<count;i++){const depth=random(i+7,1),speed=snow?28+depth*22:270+depth*270,length=snow?2:9+depth*18;
    const y=(random(i+7,2)*(height+80)+clock*speed)%(height+80)-40,x=(random(i+7,3)*(width+120)-clock*(snow?10:25)+width*20)%(width+120)-60;
    rc.strokeStyle=`rgba(195,221,225,${snow?.26:.07+depth*.13})`;rc.lineWidth=snow?2:.6+depth*.55;rc.lineCap="round";
    rc.beginPath();rc.moveTo(x,y);rc.lineTo(x+(snow?0:-length*.22),y+length);rc.stroke();
   }
  }
  publish(rainCtx,rainFrame);rainFrames++;lastRain=now;
 }
 function loop(now){requestAnimationFrame(loop);if(document.hidden){last=now;return;}const dt=Math.min(.1,(now-last)/1000);last=now;clock+=dt;
  if(dirty||(["rain","snow"].includes(state.weather?.kind)&&now-lastRain>40))drawRain(now);
  dirty=false;
 }
 addEventListener("resize",resize);resize();requestAnimationFrame(loop);
 window.focusAmbience={
  update(next){const wasRain=state.weather?.kind;state=next;dirty=true;if(wasRain!==state.weather?.kind)lastRain=0;},
  diagnostics(){return {raining:state.weather?.kind==="rain",rainFrames,width,height,fullViewport:width===innerWidth&&height===innerHeight,rainCount:state.weather?.kind==="rain"&&!reduced.matches?Math.min(260,Math.max(100,Math.round(width*height/6500))):0};}
 };
})();
