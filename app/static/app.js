"use strict";
const $ = (id) => document.getElementById(id);
const ui = {messages:$('messages'),form:$('composer'),input:$('message'),send:$('send'),mode:$('mode'),reset:$('reset'),status:$('status'),dot:$('status-dot'),note:$('model-note')};
const sessionId = crypto.randomUUID();
let busy = false;

function escapeHtml(value){return value.replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function markdown(value){
  let safe=escapeHtml(value);
  const blocks=[];
  safe=safe.replace(/```([^\n]*)\n([\s\S]*?)```/g,(_,lang,code)=>{blocks.push(`<pre><code data-language="${lang.trim()}">${code}</code></pre>`);return `\u0000${blocks.length-1}\u0000`;});
  safe=safe.replace(/`([^`\n]+)`/g,'<code>$1</code>').replace(/\*\*([^*]+)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
  return safe.replace(/\u0000(\d+)\u0000/g,(_,i)=>blocks[Number(i)]);
}
function addMessage(role,text,temporary=false){
  document.querySelector('.welcome')?.remove();
  const row=document.createElement('div');row.className=`message ${role}${temporary?' thinking':''}`;
  const bubble=document.createElement('div');bubble.className='bubble';bubble.innerHTML=markdown(text);row.appendChild(bubble);ui.messages.appendChild(row);
  ui.messages.scrollTop=ui.messages.scrollHeight;return row;
}
function setStatus(state){
  ui.status.textContent=state;ui.dot.className='';
  const key=state.toLowerCase();if(key==='ready')ui.dot.classList.add('ready');else if(key==='generating')ui.dot.classList.add('generating');else if(key==='error')ui.dot.classList.add('error');
  const ready=state==='Ready'&&!busy;ui.input.disabled=!ready;ui.send.disabled=!ready;
}
async function poll(){
  try{const response=await fetch('/api/status',{cache:'no-store'});const data=await response.json();setStatus(data.state);if(data.model)ui.note.textContent=`${data.adapter} · ${data.gpu_memory_allocated_mib} MiB`;}
  catch{setStatus('Error');ui.note.textContent='Local server unavailable';}
}
async function send(event){
  event.preventDefault();const message=ui.input.value.trim();if(!message||busy)return;
  busy=true;ui.input.value='';ui.input.style.height='auto';addMessage('user',message);const waiting=addMessage('assistant','応答を生成しています…',true);setStatus('Generating');
  try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sessionId,mode:ui.mode.value,message})});const data=await response.json();waiting.remove();if(!response.ok)throw new Error(data.error||'応答に失敗しました。');addMessage('assistant',data.response);}
  catch(error){waiting.remove();addMessage('assistant',error.message||'モデルの応答生成に失敗しました。');}
  finally{busy=false;await poll();ui.input.focus();}
}
ui.form.addEventListener('submit',send);
ui.input.addEventListener('keydown',(event)=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();ui.form.requestSubmit();}});
ui.input.addEventListener('input',()=>{ui.input.style.height='auto';ui.input.style.height=`${Math.min(ui.input.scrollHeight,180)}px`;});
async function newChat(){
  if(busy)return;await fetch('/api/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sessionId})});
  ui.messages.innerHTML='<div class="welcome"><p class="eyebrow">NEW CONVERSATION</p><h2>新しい対話を始めましょう。</h2><p>以前の会話履歴はメモリから削除されました。</p></div>';
}
ui.reset.addEventListener('click',newChat);
ui.mode.addEventListener('change',async()=>{await newChat();ui.note.textContent=`${ui.mode.value} mode`;});
poll();setInterval(poll,1500);
