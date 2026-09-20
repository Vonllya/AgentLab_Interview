import React,{useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Training} from './Training';
import {Generation} from './Generation';
import {api,navigate,usePath} from './router';
import './style.css';
function Shell(){
 const path=usePath(),[health,setHealth]=useState<any>(null);
 useEffect(()=>{void api('/health').then(setHealth).catch(()=>{});if(location.pathname==='/'){const old=localStorage.getItem('session');navigate(old?'/training/'+old:'/library',true)}},[]);
 const section=path.startsWith('/generate')?'generate':path==='/projects'?'projects':'library';
 const training=path.match(/^\/training\/([a-f0-9]{32})$/),task=path.match(/^\/library\/([a-z][a-z0-9_]+)$/),job=path.match(/^\/generate\/([a-f0-9]{32})$/);
 return <><header className="app-header"><button className="brand" onClick={()=>navigate('/library')}>◈ AgentLab <span>INTERVIEW / V0.2</span></button><nav aria-label="主导航">{[['generate','故障题目生成','/generate'],['library','题库','/library'],['projects','个人工程项目训练','/projects']].map(([key,title,to])=><a key={key} href={to} aria-current={section===key?'page':undefined} onClick={e=>{e.preventDefault();navigate(to)}}>{title}</a>)}</nav><b className={health?.agent_mode==='mock'?'badge mock':'badge'}>{health?.agent_mode==='mock'?'MOCK · 确定性辅导':health?'真实模型模式':'正在检查模式'}</b></header>
 {path==='/projects'?<main className="landing"><h1>个人工程项目训练</h1><h2>尚未开放</h2><p>未来将支持围绕用户自己的工程项目开展训练。本版不提供上传、仓库导入或真实项目训练。</p></main>:path==='/generate'||job?<Generation key={job?.[1]||'new'} id={job?.[1]}/>:path==='/library'||task||training?<Training key={training?.[1]||task?.[1]||'library'} sessionId={training?.[1]} taskId={task?.[1]}/>:path==='/'?<p>正在恢复入口…</p>:<main className="landing"><h1>页面不存在</h1><a href="/library">返回题库</a></main>}
 </>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><Shell/></React.StrictMode>);
