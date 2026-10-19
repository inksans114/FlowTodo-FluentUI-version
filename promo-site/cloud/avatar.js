export function validateAvatar(data){
 if(data==='')return true;
 if(typeof data!=='string'||data.length>175000||!/^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(data))return false;
 try{const bytes=Uint8Array.from(atob(data.split(',')[1]),c=>c.charCodeAt(0));if(bytes.length>131072||bytes.length<33)return false;
  const sig=[137,80,78,71,13,10,26,10];if(!sig.every((b,i)=>bytes[i]===b)||String.fromCharCode(...bytes.slice(12,16))!=='IHDR')return false;
  const view=new DataView(bytes.buffer);return view.getUint32(16)===256&&view.getUint32(20)===256;
 }catch{return false;}
}
export async function avatarApi({path,method,body,q,session,json,fail,now}){
 if(path!=='/api/account/avatar')return null;
 const prior=await q('SELECT * FROM avatars WHERE user_id=?',session.id).first();
 if(method==='GET')return json({data:prior?.data||'',revision:prior?.revision||0});
 if(method!=='PUT')fail(405,'不支持该操作。');
 if(!validateAvatar(body.data))fail(400,'请选择 256×256 的 PNG 头像，最多 128 KB。');
 if(body.revision!==(prior?.revision||0))fail(409,'头像已在另一端修改，请刷新后重试。');
 const date=new Date(now).toISOString();
 const row=await q('INSERT INTO avatars VALUES(?,?,1,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data,revision=avatars.revision+1,updated_at=excluded.updated_at WHERE avatars.revision=? RETURNING revision',session.id,body.data,date,body.revision).first();
 if(!row)fail(409,'头像已更新，请刷新后重试。');return json({revision:row.revision,data:body.data});
}
