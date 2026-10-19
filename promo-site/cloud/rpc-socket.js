// Fixed-destination transport for the ciphertext RPC; never an open proxy.
export async function socketRpc(connect, url, options) {
 const target=new URL(url);
 if(target.protocol!=='http:'||target.hostname!=='ai.cheemsdoge.xyz'||target.port!=='24336'||target.pathname!=='/api/storage/rpc'||target.search||options.method!=='POST')throw new Error('rpc_destination');
 const payload=new TextEncoder().encode(options.body);
 if(payload.length>300000)throw new Error('rpc_size');
 const socket=connect({hostname:'103.236.91.136',port:24336},{secureTransport:'off',allowHalfOpen:false});
 const abort=()=>{socket.close().catch(()=>{});};
 if(options.signal?.aborted){abort();throw new Error('rpc_timeout');}
 options.signal?.addEventListener('abort',abort,{once:true});
 try{
  await socket.opened;
  const writer=socket.writable.getWriter();
  const header=new TextEncoder().encode(`POST /api/storage/rpc HTTP/1.0\r\nHost: 103.236.91.136:24336\r\nContent-Type: application/json\r\nUser-Agent: FlowTodo/1.0\r\nContent-Length: ${payload.length}\r\nConnection: close\r\n\r\n`);
  await writer.write(header);await writer.write(payload);writer.releaseLock();
  const reader=socket.readable.getReader();let text='',length=0;const decoder=new TextDecoder();
  while(true){const {done,value}=await reader.read();if(done)break;length+=value.length;if(length>400000)throw new Error('rpc_response_size');text+=decoder.decode(value,{stream:true});}
  text+=decoder.decode();return parseRpcResponse(text);
 }finally{options.signal?.removeEventListener('abort',abort);abort();}
}
export function parseRpcResponse(text){
 const boundary=text.indexOf('\r\n\r\n');if(boundary<0||boundary>16384)throw new Error('rpc_headers');
 const headers=text.slice(0,boundary),body=text.slice(boundary+4),status=/^HTTP\/1\.[01] (\d{3})\b/.exec(headers);
 if(!status||/\r\ntransfer-encoding:/i.test(headers))throw new Error('rpc_protocol');
 const size=/\r\ncontent-length:\s*(\d+)/i.exec(headers);if(size&&Number(size[1])!==new TextEncoder().encode(body).length)throw new Error('rpc_incomplete');
 return new Response(body,{status:Number(status[1]),headers:{'Content-Type':'application/json'}});
}
