import ReactMarkdown from 'react-markdown';

type Node={type:string;value?:string;url?:string;children?:Node[]};
export function Markdown({text,ids=[]}:{text:string;ids?:string[]}){
 const known=new Set(ids.filter(id=>/^[a-f0-9]{32}$/.test(id)));
 const link=(id:string):Node=>({type:'link',url:'#'+id,children:[{type:'text',value:'证据 '+id.slice(0,8)}]});
 // Work on parsed text nodes: never rewrite Markdown inside existing links/code.
 const evidenceLinks=()=> (tree:Node)=>{
  function visit(node:Node){
   if(['link','linkReference','code','html'].includes(node.type)||!node.children)return;
   node.children=node.children.flatMap(child=>{
    if(child.type==='inlineCode'&&known.has(child.value||''))return [link(child.value!)];
    if(child.type!=='text'){visit(child);return [child];}
    const value=child.value||'';const out:Node[]=[];let cursor=0;
    for(const match of value.matchAll(/\b[a-f0-9]{32}\b/g)){
     if(!known.has(match[0]))continue;
     const offset=match.index!;out.push({type:'text',value:value.slice(cursor,offset)},link(match[0]));cursor=offset+32;
    }
    out.push({type:'text',value:value.slice(cursor)});return out;
   });
  }
  visit(tree);
 };
 // No raw-HTML plugin; links must target known evidence, and remote images are omitted.
 return <div className="prose markdown"><ReactMarkdown skipHtml remarkPlugins={[evidenceLinks]} urlTransform={url=>/^#[a-f0-9]{32}(?:-[a-z0-9-]+)?$/.test(url)&&known.has(url.slice(1,33))?url:''} components={{
  a:({href,children})=>href?<a href={href} onClick={()=>{const target=document.getElementById(href.slice(1));if(target instanceof HTMLDetailsElement)target.open=true;target?.scrollIntoView({block:'center'});}}>{children}</a>:<span>{children}</span>,
  img:()=>null
 }}>{text}</ReactMarkdown></div>;
}
