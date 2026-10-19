import {connect} from 'cloudflare:sockets';

// Authenticated ciphertext only. The origin URL comes from server configuration.
export async function tcpFetch(url,options){
 const target=new URL(url);
 if(target.protocol!=='http:'||target.username||target.password)throw new Error('storage_target');
 const socket=connect({hostname:target.hostname,port:Number(target.port||80)},{secureTransport:'off'});
 const encoder=new TextEncoder(),body=encoder.encode(options.body||'');
 const writer=socket.writable.getWriter(),reader=socket.readable.getReader();
 const abort=()=>{socket.close().catch(()=>{});};options.signal?.addEventListener('abort',abort,{once:true});
 try{
  await socket.opened;
  await writer.write(encoder.encode(`POST ${target.pathname}${target.search} HTTP/1.1\r\nHost: ${target.host}\r\nContent-Type: application/json\r\nContent-Length: ${body.length}\r\nConnection: close\r\n\r\n`));
  await writer.write(body);
  const chunks=[];let size=0;
  while(true){const part=await reader.read();if(part.done)break;size+=part.value.length;if(size>4000000)throw new Error('storage_response_size');chunks.push(part.value);}
  const output=new Uint8Array(size);let offset=0;for(const part of chunks){output.set(part,offset);offset+=part.length;}
  const text=new TextDecoder().decode(output),boundary=text.indexOf('\r\n\r\n');
  if(boundary<0)throw new Error('storage_http_format');
  const headers=text.slice(0,boundary),status=Number(/^HTTP\/1\.[01] (\d{3})/.exec(headers)?.[1]);let payload=text.slice(boundary+4);
  if(/transfer-encoding:\s*chunked/i.test(headers)){
   let rest=payload;payload='';
   while(rest){const at=rest.indexOf('\r\n'),n=parseInt(rest.slice(0,at).split(';')[0],16);if(at<0||!Number.isFinite(n))throw new Error('storage_chunk_format');if(!n)break;payload+=rest.slice(at+2,at+2+n);rest=rest.slice(at+2+n+2);}
  }
  return new Response(payload,{status:status||502,headers:{'Content-Type':'application/json'}});
 }finally{
  options.signal?.removeEventListener('abort',abort);reader.releaseLock();writer.releaseLock();await socket.close().catch(()=>{});
 }
}
