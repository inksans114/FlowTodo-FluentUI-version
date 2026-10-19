import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseRpcResponse,socketRpc} from './rpc-socket.js';
test('RPC transport enforces its fixed destination and bounded response framing',async()=>{
 assert.throws(()=>parseRpcResponse('HTTP/1.0 200 OK\r\nContent-Length: 30\r\n\r\n{}'),/incomplete/);
 assert.throws(()=>parseRpcResponse('HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n'),/protocol/);
 assert.equal(await parseRpcResponse('HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\n{}').text(),'{}');
 await assert.rejects(socketRpc(()=>assert.fail('must not connect'),'http://attacker.example:24336/api/storage/rpc',{method:'POST',body:'{}'}),/destination/);
 let destination,request='';
 const connect=(target)=>{destination=target;return {opened:Promise.resolve(),close:async()=>{},writable:new WritableStream({write:b=>{request+=new TextDecoder().decode(b);}}),readable:new ReadableStream({start(c){c.enqueue(new TextEncoder().encode('HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\n{}'));c.close();}})};};
 assert.equal((await socketRpc(connect,'http://ai.cheemsdoge.xyz:24336/api/storage/rpc',{method:'POST',body:'{}'})).status,200);
 assert.deepEqual(destination,{hostname:'103.236.91.136',port:24336});assert.match(request,/HTTP\/1.0/);assert.match(request,/Content-Length: 2/);
});
