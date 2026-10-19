import React,{useEffect,useState} from 'react';
const safeNext=value=>/^\/dashboard(?:\/|$)/.test(value||'')||/^\/connect\?code=[A-F0-9]{10}$/.test(value||'')?value:'/dashboard';
export function IdentityRedirect({config,route,api}){
 const [error,setError]=useState('');
 useEffect(()=>{let alive=true;async function start(){try{
  const next=safeNext(new URLSearchParams(route.split('?')[1]).get('next'));sessionStorage.setItem('flowtodo-login-next',next);
  const result=await api('/api/identity/start',{});if(!alive)return;
  const url=new URL('/login',result.issuer);url.searchParams.set('state',result.state);location.replace(url.href);
 }catch(e){if(alive)setError(e.message);}}start();return()=>{alive=false;};},[]);
 return <main className="wrap" id="main-content"><h1>正在连接邮箱登录</h1><p role={error?'alert':'status'}>{error||'验证邮箱后，将返回你的工作台。'}</p></main>;
}
export function IdentityCallback({api,setUser,navigate}){
 const [error,setError]=useState('');
 useEffect(()=>{const ticket=new URLSearchParams(location.hash.slice(1)).get('ticket');history.replaceState({},'',location.pathname);
  if(!ticket){setError('登录凭证已失效，请重新登录。');return;}
  api('/api/identity/exchange',{ticket}).then(data=>{setUser(data.user);const next=safeNext(sessionStorage.getItem('flowtodo-login-next'));sessionStorage.removeItem('flowtodo-login-next');navigate(next);}).catch(e=>setError(e.message));
 },[]);
 return <main className="wrap" id="main-content"><h1>{error?'登录未完成':'正在进入工作台'}</h1><p role={error?'alert':'status'}>{error||'正在安全验证你的账号…'}</p>{error&&<a className="button" href="/login">重新登录</a>}</main>;
}
