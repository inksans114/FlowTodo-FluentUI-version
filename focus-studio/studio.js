"use strict";
(() => {
 const $ = id => document.getElementById(id);
 let bridge = null, state = {}, english = false, toastTimer, volumeTimer;
 let lastReward = null, adjustResume = false, adjustSubmitted = false;
 let progressResume=false,progressSubmitted=false,progressContext=null,questionId="",seenQuestion="";
 let reminderSession="",reminderInterval=-1,nextProgressCheck=0;
 function syncSectionChoices(){document.querySelectorAll("[data-progress-section]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.progressSection===$("progress-section").value)));}
 function syncProgressChoices(interval){document.querySelectorAll("[data-progress-check]").forEach(button=>button.setAttribute("aria-pressed",String(Number(button.dataset.progressCheck)===interval)));}
 function resetProgressCheck(){nextProgressCheck=Number(state.elapsed||0)+Number(state.progressCheckMinutes||0)*60;}
 function openProgress(mode="report") {
  if(!bridge||state.guidedBusy||!state.guided||state.celebrating||document.querySelector("dialog[open]"))return false;
  const clarification=state.guidedClarification;
  if(mode==="questions"&&!clarification)return false;
  progressContext={sessionId:state.sessionId,guidedStep:state.guidedStep};
  progressResume=!state.guidedWaiting&&state.status!=="paused";progressSubmitted=false;
  if(progressResume)action("pause");
  $("progress-form").hidden=mode==="questions";$("progress-questions-form").hidden=mode!=="questions";
  $("progress-title").textContent=mode==="questions"?"再了解一点，就能按你现在的进度安排":mode==="reminder"?"轻轻问一句：现在做到哪里了？":"告诉 AI，你现在正在做什么";
  $("progress-intro").textContent=mode==="questions"?(clarification.intro||"只补充影响下一段安排的信息。"):(mode==="reminder"?"可以跳过这次询问，继续手头的事。":"换科目、换卷子，或到了大题，都可以告诉我。可以只说一句，下面的字段可留空。")+" 填写期间计时已暂停。";
  if(mode==="questions"){
   questionId=clarification.id;seenQuestion=questionId;$("progress-questions").replaceChildren();
   clarification.questions.forEach((question,index)=>{
    const card=document.createElement("section");card.className="progress-question";
    const label=document.createElement("p");label.textContent=question.question;card.append(label);
    const options=document.createElement("div");options.className="guided-options";
    const input=document.createElement("input");input.id="progress-answer-"+index;input.maxLength=500;input.placeholder="也可以直接说你的想法";input.setAttribute("aria-label",question.question);
    for(const choice of question.choices||[]){const button=document.createElement("button");button.type="button";button.textContent=choice;button.setAttribute("aria-pressed","false");button.onclick=()=>{input.value=choice;options.querySelectorAll("button").forEach(other=>other.setAttribute("aria-pressed",String(other===button)));};options.append(button);}
    input.oninput=()=>options.querySelectorAll("button").forEach(button=>button.setAttribute("aria-pressed",String(button.textContent===input.value)));
    card.append(options,input);$("progress-questions").append(card);
   });
  }else{
   // Avoid prefilled old subjects contradicting a new "I switched" message.
   const report=state.guidedError?(state.reportedProgress||{}):{};
   for(const field of ["subject","paper","section","position","note"])$("progress-"+field).value=report[field]||"";
   syncSectionChoices();
  }
  $("progress-dialog").showModal();(mode==="questions"?$("progress-answer-0"):$("progress-note")).focus();
  return true;
 }
 function checkProgress(guided,rest,paused,busy,waiting){
  const interval=Number(state.progressCheckMinutes)||0,elapsed=Number(state.elapsed)||0;
  syncProgressChoices(interval);
  if(reminderSession!==state.sessionId||reminderInterval!==interval){reminderSession=state.sessionId;reminderInterval=interval;resetProgressCheck();}
  if(!guided||!state.immersive)return;
  if(state.guidedClarification&&!busy){if(seenQuestion!==state.guidedClarification.id)openProgress("questions");return;}
  if(interval&&!rest&&!paused&&!busy&&!waiting&&!document.hidden&&elapsed>=nextProgressCheck){if(openProgress("reminder"))resetProgressCheck();}
 }
 function reward(text) {
  $("toast").textContent=text;$("toast").classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>$("toast").classList.remove("show"),3200);
  if(window.matchMedia("(prefers-reduced-motion: reduce)").matches)return;
  $("reward-confetti").replaceChildren();
  for(let i=0;i<32;i++){const bit=document.createElement("i");bit.style.left=(35+(i*37%31))+"%";bit.style.background=["#d7e9af","#f0c780","#ceabd9","#b4d8dc"][i%4];bit.style.setProperty("--dx",((i*73%500)-250)+"px");bit.style.setProperty("--dy",((i*47%260)+130)+"px");bit.style.setProperty("--spin",((i*137%720)-360)+"deg");$("reward-confetti").append(bit);}
  setTimeout(()=>$("reward-confetti").replaceChildren(),1800);
 }
 function adjust(prefill="") {
  adjustResume=!state.guidedWaiting && state.status!=="paused";adjustSubmitted=false;
  if(adjustResume)action("pause");
  $("guided-feedback").value=prefill;$("guided-dialog").showModal();$("guided-feedback").focus();
 }
 const labels = {space:"Quiet hours",forest:"Growing forest",room:"Focus room",exit:"Back to app",thought:"Park a thought",finish:"Finish session",leave:"Leave a return point ↗",thoughtHint:"Write it down. Your task can keep going.",save:"Save & keep focusing",drag:"Drag to orbit",reset:"Reset view"};
 const fmt = value => {const seconds = Math.max(0, Math.floor(Number(value) || 0));return String(Math.floor(seconds / 60)).padStart(2,"0") + ":" + String(seconds % 60).padStart(2,"0");};
 Object.assign(labels,{weatherTitle:"Weather outside",cityLabel:"City",autoCity:"Locate automatically",weatherOff:"Disable weather",useCity:"Use this city",weatherPrivacy:"City-level weather only. IP is not saved. The scene works offline."});
 labels.rainVolume="Rain volume";
 function action(name, value="",expected=state) { if(name.startsWith("guided-"))value=JSON.stringify({expectedStep:expected.guidedStep,expectedSession:expected.sessionId,feedback:value});if (bridge) bridge.action(name,value); }
 function scene(name) {document.body.dataset.scene = name === "room" ? "room" : "tree";document.querySelectorAll("[data-scene-button]").forEach(button=>{const selected=button.dataset.sceneButton===document.body.dataset.scene;button.classList.toggle("selected",selected);button.setAttribute("aria-pressed",String(selected));});}
 function update(raw) {
  let next;
  try {next = typeof raw === "string" ? JSON.parse(raw) : raw;} catch (_) {return;}
  if (!next) return;
  state = next;
  english = String(state.language || "").startsWith("en");
  const celebrating=Boolean(state.celebrating);
  document.body.classList.toggle("celebrating",celebrating);
  $("rain-sound").textContent=english?`Rain · ${state.rainSound?"On":"Off"}`:`雨声 · ${state.rainSound?"开":"关"}`;
  $("rain-sound").setAttribute("aria-pressed",String(Boolean(state.rainSound)));
  if(document.activeElement!==$("rain-volume")){$("rain-volume").value=Math.round((Number(state.rainVolume)||0)*100);$("rain-volume-value").value=$("rain-volume").value+"%";}
  const w=state.weather||{},names=english?{sunny:"Clear",cloudy:"Cloudy",rain:"Rain",snow:"Snow"}:{sunny:"晴",cloudy:"多云",rain:"雨",snow:"雪"},icons={sunny:"☀",cloudy:"☁",rain:"☂",snow:"❄"};
  document.body.dataset.weather=w.kind||"neutral";
  const weatherText=w.status==="off"?(english?"Weather off":"天气已关闭"):w.status==="loading"?(english?"Checking weather…":"查询天气…"):["ready","stale"].includes(w.status)?`${icons[w.kind]||""} ${w.city||""} · ${names[w.kind]||""} ${w.temperature??""}°${w.status==="stale"?(english?" · cached":" · 缓存"):""}`:(english?"Set weather":"设置天气");
  $("weather").textContent=weatherText;
  $("weather-detail").textContent=w.status==="unavailable"?(english?"Weather is unavailable. Retry auto location or enter a city.":"暂时查不到天气，可以重试自动定位或输入城市。"):w.status==="stale"?(english?"Showing the last available weather. You can retry below.":"当前显示上一次的天气，可以在下方重试。"):english?"Approximate network location. Enter a city if it differs from yours.":"按网络所在城市匹配；位置不对时，可以改成你所在的城市。";
  if(w.issue==="rate-limit")$("weather-detail").textContent=english?"The provider is rate-limiting requests. Try later, or enter a city to skip automatic location.":"服务暂时限流，请稍后重试；也可以手动输入城市，跳过自动定位。";
  document.documentElement.lang = english ? "en" : "zh-CN";
  document.querySelectorAll("[data-i18n]").forEach(node=>{if(!node.dataset.original)node.dataset.original=node.textContent;node.textContent=english?labels[node.dataset.i18n]:node.dataset.original;});
  const paused=state.status==="paused", rest=state.phase==="break", pomo=state.kind==="pomodoro";
  document.body.classList.toggle("paused",paused);document.body.classList.toggle("rest",rest);
  $("timer").textContent=fmt(state.remaining);$("goal").textContent=state.goal;$("goal").title=state.goal;
  $("phase").textContent=paused?(english?"Paused · take your time":"已暂停 · 按自己的节奏来"):rest?(english?"Time for a break":"休息一下，下一轮会自动开始"):pomo?(english?`Focus ${state.round} of ${state.rounds}`:`第 ${state.round} / ${state.rounds} 轮专注`):(english?"A little time, just for this":"这一刻，专心做一件事");
  $("pause-label").textContent=paused?(english?"Resume":"继续"):(english?"Pause":"暂停");
  $("pause-icon").innerHTML=paused?'<path d="m9 5 10 7-10 7Z"/>':'<path d="M9 6v12M15 6v12"/>';
  $("pause").disabled=!bridge;
  const progress=Math.max(0,Math.min(1,Number(state.progress)||0));document.documentElement.style.setProperty("--growth",String(progress));
  // Backend updates are small colour steps; avoid animating a full-screen
  // blurred/transparent gradient through the native compositor.
  const tint=(a,b)=>`rgb(${a.map((v,i)=>Math.round(v+(b[i]-v)*progress)).join(",")})`;
  document.documentElement.style.setProperty("--room-top",tint([40,46,58],[50,68,78]));
  document.documentElement.style.setProperty("--room-bottom",tint([28,36,48],[24,38,47]));
  document.documentElement.style.setProperty("--room-glow",tint([57,59,60],w.kind==="rain"?[67,86,89]:[82,102,84]));
  scene(state.scene);
  if(window.focusScene3D)window.focusScene3D.update(state);
  if(window.focusAmbience)window.focusAmbience.update(state);
  $("caption").textContent=paused?(english?"Your progress stays here. Come back when you are ready.":"已经走过的路会留下。准备好了，就接着做。"):rest?(english?"Look away from the screen. Breathe, stretch, rest.":"看看远处，伸个懒腰，让注意力慢慢恢复。"):state.scene==="room"?(english?"A little closer to morning, with every quiet moment.":progress<.35?"窗外还是夜色，留一盏灯，专心做眼前的事。":progress<.8?"安静的时光过去，窗外也开始慢慢亮起来。":"快到清晨了。这一段投入，已经走了很远。"):(english?"Small steps, steady growth.":progress<.35?"不必着急，眼前的小事正在慢慢长大。":progress<.8?"每一段安静的投入，都让它多长一点。":"快到这一轮的终点了。看看你已经走了多远。");
  const garden=Number(state.trees)||0, minutes=Number(state.minutes)||0;
  $("garden").textContent=minutes?(english?`${garden} sessions · ${minutes} minutes saved`:`已完成 ${garden} 轮 · 留下 ${minutes} 分钟投入`):(english?"Every little effort leaves a trace":"每一段投入，都会留下痕迹");
  if(celebrating){$("timer").textContent=fmt(state.elapsed);$("phase").textContent=english?"Session complete · your time made this grow":"专注完成 · 这一轮的投入";$("pause-label").textContent=english?"Record this session":"记录这轮";$("pause-icon").innerHTML='<path d="m6 12 4 4 8-8"/>';$("caption").textContent=english?`Your ${garden} trees are growing together. Every quiet moment stays.`:`${garden} 棵树，都是你认真投入过的时间。这一刻，让它们一起长大。`;$("garden").textContent=english?`Your forest · ${garden} trees`:`你的森林 · 累计 ${garden} 棵树`;}
  const signature=pomo?`${state.round}:${state.rounds}`:"";
  if($("rounds").dataset.signature!==signature){$("rounds").replaceChildren();$("rounds").dataset.signature=signature;if(pomo)for(let i=1;i<=state.rounds;i++){const dot=document.createElement("span");dot.className="round-dot"+(i<state.round?" done":i===state.round?" current":"");$("rounds").append(dot);}}
  const guided=Boolean(state.guided&&!celebrating),waiting=Boolean(state.guidedWaiting),busy=Boolean(state.guidedBusy),clarifying=Boolean(state.guidedClarification);
  document.body.classList.toggle("guided",guided);
  $("guided-panel").hidden=!guided;$("guided-detail").hidden=!guided;$("reward-sound").hidden=!guided;
  $("guided-detail").textContent=state.guidedDetail||"";
  $("reward-sound").textContent=english?`Reward sound · ${state.rewardSound?"On":"Off"}`:`庆祝音 · ${state.rewardSound?"开":"关"}`;
  $("reward-sound").setAttribute("aria-pressed",String(Boolean(state.rewardSound)));
  if(guided){
   $("phase").textContent=busy?(english?"Preparing the next part…":"正在按你的反馈准备下一段…"):waiting?(english?"This time is yours. You choose what comes next.":"这一段时间到了，接下来由你定"):paused?(english?"Paused · no rush":"已暂停，不用赶"):(english?"Just this part, at your pace":"按你的节奏，只做眼前这一段");
   $("guided-hint").textContent=busy?"计时已停，等待时也可以休息。":waiting?"计时结束不代表作业做完了。完成了就继续，没做完也可以调整。":"不用同时想着后面的安排。累了，或想换一种做法，都可以调整。";
   if(state.guidedError&&!busy)$("guided-hint").textContent=state.guidedError+" 进展仍保留，可以调整想法后再试，或先休息。";
   $("finish").querySelector("span").textContent=rest?(english?"Ready to continue":"休息好了，继续"):(english?"This part is done":"这步完成了，继续");
   if(waiting){$("pause-label").textContent=rest?"继续":"休息一下";$("pause-icon").innerHTML='<path d="m9 5 10 7-10 7Z"/>';}
   $("pause").disabled=!bridge||busy;$("finish").disabled=!bridge||busy;
   $("guided-unfinished").disabled=busy||rest;$("guided-adjust").disabled=busy;
   $("guided-rest").disabled=rest&&!waiting;
   $("guided-progress").disabled=busy;
   if(clarifying&&!busy){$("guided-hint").textContent="补充当前进度，就能按你现在的材料继续。也可以先休息。";$("finish").querySelector("span").textContent="继续回答进度";$("pause").disabled=!waiting||rest;$("guided-rest").disabled=rest&&!waiting;}
   if(!waiting&&!busy&&Number(state.elapsed)<60)$("caption").textContent=state.guidedIntro||$("caption").textContent;
  }else{$("finish").disabled=!bridge;}
  const sequence=Number(state.guidedRewardSeq)||0;
  if(guided&&lastReward!==null&&sequence>lastReward)reward(state.guidedRewardText||"这一小段，你确实做到了。");
  lastReward=sequence;
  checkProgress(guided,rest,paused,busy,waiting);
 }
 function toggleThought(){if($("thought-dialog").open){$("thought-dialog").close();return;}$("thought-dialog").showModal();$("thought-input").focus();}
 function saveThought(event){event.preventDefault();const value=$("thought-input").value.trim();if(!value||!bridge)return;action("thought",value);$("thought-input").value="";$("thought-dialog").close();$("toast").textContent=english?"Saved. Back to what matters now.":"已存好，回到眼前这一件事。";$("toast").classList.add("show");clearTimeout(toastTimer);toastTimer=setTimeout(()=>$("toast").classList.remove("show"),2400);}
 $("exit").onclick=()=>action("exit");$("pause").onclick=()=>action(state.celebrating?"review":state.guided&&state.guidedWaiting?(state.phase==="break"?"guided-next":"guided-rest"):state.status==="paused"?"resume":"pause");$("finish").onclick=()=>state.guidedClarification?openProgress("questions"):action(state.guided?"guided-next":"finish");$("leave").onclick=()=>action("leave");$("thought").onclick=toggleThought;$("dismiss").onclick=()=>$("thought-dialog").close();$("thought-form").onsubmit=saveThought;
 $("reward-sound").onclick=()=>action("reward-sound",state.rewardSound?"off":"on");
 $("guided-unfinished").onclick=()=>adjust("刚才这段还没有做完，请保留未完成的部分，帮我换一种更容易推进的做法。");
 $("guided-adjust").onclick=()=>adjust();$("guided-end").onclick=()=>action("guided-end");
 $("guided-rest").onclick=()=>action("guided-rest");
 $("guided-dismiss").onclick=()=>$("guided-dialog").close();
 $("guided-dialog").addEventListener("close",()=>{if(adjustResume&&!adjustSubmitted)action("resume");adjustResume=false;});
 document.querySelectorAll("[data-feedback]").forEach(button=>button.onclick=()=>{$("guided-feedback").value=button.dataset.feedback;$("guided-feedback").focus();});
 $("guided-form").onsubmit=event=>{event.preventDefault();const feedback=$("guided-feedback").value.trim();if(!feedback||!bridge)return;adjustSubmitted=true;$("guided-dialog").close();action("guided-adjust",feedback);};
 $("guided-progress").onclick=()=>openProgress(state.guidedClarification?"questions":"report");
 $("progress-dismiss").onclick=()=>$("progress-dialog").close();
 $("progress-dialog").addEventListener("close",()=>{resetProgressCheck();if(progressResume&&!progressSubmitted&&progressContext?.sessionId===state.sessionId&&progressContext?.guidedStep===state.guidedStep)action("resume");progressResume=false;});
 document.querySelectorAll("[data-progress-check]").forEach(button=>button.onclick=()=>{if(!bridge)return;syncProgressChoices(Number(button.dataset.progressCheck));action("progress-check",button.dataset.progressCheck);});
 document.querySelectorAll("[data-progress-section]").forEach(button=>button.onclick=()=>{$("progress-section").value=button.dataset.progressSection;syncSectionChoices();$("progress-section").focus();});
 $("progress-section").addEventListener("input",syncSectionChoices);
 $("progress-form").onsubmit=event=>{
  event.preventDefault();if(!bridge||state.guidedBusy)return;
  const report={};for(const field of ["subject","paper","section","position","note"])report[field]=$("progress-"+field).value.trim();
  if(!Object.values(report).some(Boolean)){$("progress-note").focus();return;}
  progressSubmitted=true;$("progress-dialog").close();action("guided-progress",JSON.stringify(report),progressContext);
 };
 function sendProgressAnswers(skip=false){
  const clarification=state.guidedClarification;
  if(!bridge||state.guidedBusy||!clarification||clarification.id!==questionId)return;
  const answers=clarification.questions.map((_,index)=>skip?"":$("progress-answer-"+index).value.trim());
  if(!skip&&!answers.some(Boolean)){$("progress-answer-0").focus();return;}
  progressSubmitted=true;$("progress-dialog").close();action("guided-answers",JSON.stringify({questionId,answers}),progressContext);
 }
 $("progress-questions-form").onsubmit=event=>{event.preventDefault();sendProgressAnswers();};
 $("progress-skip").onclick=()=>sendProgressAnswers(true);
 $("rain-sound").onclick=()=>action("rain-sound",state.rainSound?"off":"on");
 $("rain-volume").oninput=()=>{const volume=Number($("rain-volume").value)/100;$("rain-volume-value").value=Math.round(volume*100)+"%";clearTimeout(volumeTimer);volumeTimer=setTimeout(()=>action("rain-volume",String(volume)),250);};
 $("weather").onclick=()=>{$("weather-city").value=state.weatherCity||state.weather?.city||"";$("weather-dialog").showModal();};
 $("weather-dismiss").onclick=()=>$("weather-dialog").close();
 const configureWeather=(mode,city="")=>{action("weather",JSON.stringify({mode,city}));$("weather-dialog").close();};
 $("weather-auto").onclick=()=>configureWeather("auto");$("weather-off").onclick=()=>configureWeather("off");
 $("weather-form").onsubmit=event=>{event.preventDefault();const city=$("weather-city").value.trim();if(city)configureWeather("city",city);else $("weather-city").focus();};
 document.querySelectorAll("[data-scene-button]").forEach(button=>button.onclick=()=>{scene(button.dataset.sceneButton);action("scene",button.dataset.sceneButton);});
 document.addEventListener("keydown",event=>{const editing=event.target.matches("textarea,input,select"),dialog=document.querySelector("dialog[open]");if(event.ctrlKey&&event.shiftKey&&event.code==="Space"&&!dialog&&!state.celebrating){event.preventDefault();toggleThought();}else if(event.target.id==="thought-input"&&event.ctrlKey&&event.key==="Enter"){saveThought(event);}else if(event.key==="Escape"){event.preventDefault();if(dialog)dialog.close();else action("exit");}else if(event.code==="Space"&&!editing&&!dialog&&!state.celebrating){event.preventDefault();action(state.guidedClarification?"guided-noop":state.status==="paused"?"resume":"pause");}});
 // Deterministic fireflies; their movement never changes the authoritative clock.
 for(let i=0;i<18;i++){const dot=document.createElement("i");dot.className="firefly firefly-"+i;$("fireflies").append(dot);}
 window.flowFocus={update,scene,showProgressQuestions:()=>openProgress("questions")};
 if(typeof QWebChannel!=="undefined"&&typeof qt!=="undefined")new QWebChannel(qt.webChannelTransport,channel=>{bridge=channel.objects.studio;window.flowFocus.connected=true;update(bridge.state);bridge.stateChanged.connect(()=>update(bridge.state));});
 else {update({status:"work",phase:"focus",remaining:1499,goal:"阅读一篇文献，记下三个观点",progress:.42,round:1,rounds:4,kind:"pomodoro",scene:"tree",trees:3,minutes:75});}
})();
