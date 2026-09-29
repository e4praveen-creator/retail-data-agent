// Build a portable, offline HTML reading copy of the Markdown handbook.
// Bundle with the app's existing esbuild, then run with Node. No network assets.
import fs from 'node:fs';
import path from 'node:path';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const dir=path.resolve(process.argv[2] || 'docs/developer');
const chapters=[
  ['README.md','start','Start here'],
  ['USER_ADMIN_GUIDE.md','user-guide','User and admin guide'],
  ['IMPROVEMENT_WORKSPACE_DESIGN.md','workspace-design','Improvement workspace design'],
  ['ARCHITECTURE.md','architecture','Architecture'],
  ['LOW_LEVEL_DESIGN.md','design','Low-level design'],
  ['API_AND_TOOLS.md','contracts','API and tools'],
  ['FEATURES.md','features','Features and gaps'],
  ['SYNTHETIC_DATA.md','data','Synthetic data'],
  ['EXTENDING.md','extend','Extension guide'],
  ['ANSWER_EXAMPLES.md','examples','Answer examples'],
  ['TESTING.md','tests','Tests and evaluation'],
  ['PRODUCTION_READINESS.md','readiness','Local production readiness'],
  ['REPOSITORY_MAINTENANCE.md','maintenance','Repository maintenance'],
  ['RELEASE.md','release','Release and operations'],
  ['UI_IMPROVEMENT_PLAN.md','proposal','Implementation status']
];
const chapterIds=Object.fromEntries(chapters.map(([file,id])=>[file,id]));
const components={
  a:({href='',children,...rest})=>{
    const target=chapterIds[href.split('#')[0]];
    return <a {...rest} href={target?'#'+target:href}>{children}</a>;
  },
  img:({src='',alt=''})=>{
    const file=path.resolve(dir,src);
    const local=src && !/^[a-z]+:/i.test(src) && file.startsWith(dir+path.sep) && fs.existsSync(file);
    const embedded=local?'data:image/'+(file.endsWith('.svg')?'svg+xml':'png')+';base64,'+fs.readFileSync(file).toString('base64'):src;
    return <img src={embedded} alt={alt}/>;
  },
  pre:({children})=>{
    const mermaid=React.isValidElement(children) && children.props.className==='language-mermaid';
    return mermaid?<details className="diagram-source"><summary>Editable Mermaid diagram source</summary><pre>{children}</pre></details>:<pre>{children}</pre>;
  }
};
const body=chapters.map(([file,id])=>`<article id="${id}">${renderToStaticMarkup(<ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{fs.readFileSync(path.join(dir,file),'utf8')}</ReactMarkdown>)}</article>`).join('\n');
const nav=chapters.map(([,id,label])=>`<a href="#${id}">${label}</a>`).join('');
const html=`<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Milky Way 2.0 · Developer handbook</title><style>
:root{color-scheme:light;--ink:#192d40;--muted:#607187;--line:#dce4ed;--blue:#235a91}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f7fa;color:var(--ink);font:16px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}aside{position:fixed;inset:0 auto 0 0;width:255px;background:#142a40;color:#fff;padding:30px 20px;overflow:auto}aside strong{display:block;font-size:22px;line-height:1.3}aside small{display:block;color:#b5c8dc;margin:12px 0 25px}aside a{display:block;color:#dbe7f4;text-decoration:none;padding:8px 10px;border-radius:5px;font-size:14px}aside a:hover,aside a:focus{background:#284966;color:#fff}main{margin-left:255px;max-width:1440px;padding:30px 42px 80px}article{background:#fff;border:1px solid var(--line);border-radius:14px;padding:35px 40px;margin-bottom:30px;scroll-margin-top:20px}h1{font-size:32px;line-height:1.25;margin-top:0}h2{font-size:24px;line-height:1.35;border-top:1px solid var(--line);padding-top:24px;margin-top:35px}h3{font-size:19px;margin-top:26px}p,li{max-width:105ch}a{color:var(--blue);text-underline-offset:3px}img{max-width:100%;height:auto;border-radius:8px}table{border-collapse:collapse;width:100%;display:block;overflow:auto;font-size:14px;line-height:1.5;margin:20px 0}th,td{border:1px solid var(--line);padding:10px 12px;vertical-align:top;text-align:left}th{background:#edf3f9}tbody tr:nth-child(even){background:#f8fafc}pre{background:#142a40;color:#eef4fc;padding:20px;border-radius:8px;overflow:auto;font-size:13px;line-height:1.6}code{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:.88em}p code,li code,td code{background:#edf3f8;padding:2px 4px;border-radius:3px;overflow-wrap:anywhere}blockquote{border-left:4px solid #91b3d1;margin-left:0;padding:8px 20px;background:#f5f9fd}.diagram-source{border:1px solid var(--line);border-radius:8px;padding:12px 16px;margin:18px 0}.diagram-source summary{cursor:pointer;font-weight:600}.note{color:var(--muted);font-size:13px}.print{background:#fff;color:#173851;border:0;padding:10px 14px;border-radius:6px;cursor:pointer;margin-top:25px}@media(max-width:900px){aside{position:static;width:auto}aside nav{display:flex;flex-wrap:wrap}aside a{padding:6px 10px}main{margin:0;padding:18px}article{padding:24px 20px}h1{font-size:27px}}@media print{aside{display:none}main{margin:0;padding:0;max-width:none}article{border:0;border-radius:0;break-before:page;padding:0}article:first-child{break-before:auto}pre{white-space:pre-wrap;background:#f4f7fa;color:#172b40}table{display:table;font-size:10px}a{color:inherit}h1,h2,h3{break-after:avoid}tr,img{break-inside:avoid}.diagram-source{display:none}}
</style></head><body><aside><strong>Milky Way 2.0</strong><small>Developer handbook<br>Application 2.1.1 · September 2026</small><nav>${nav}</nav><p class="note" style="color:#b5c8dc">Use your browser’s Print command to save a PDF.</p><p class="note" style="color:#b5c8dc">Offline reading copy. Markdown files are the editable source. Includes the implemented admin workflow and acceptance record.</p></aside><main>${body}</main></body></html>`;
fs.writeFileSync(path.join(dir,'HANDBOOK.html'),html);
console.log(`Built offline handbook: ${chapters.length} chapters.`);
