import React, { useState } from 'react';
import { api } from './api.js';
import { ChevronDown, Pencil, Plus, RotateCcw, X, Check, GitBranch } from 'lucide-react';

const readable = value => String(value || 'planned').replaceAll('_', ' ');
export function InvestigationPanel({ snapshot, busy, onUpdate, onContinue }) {
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState({statement:'',test:'',falsifier:''});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(true);
  if (!snapshot) return null;
  const nodes = snapshot.hypotheses || [];
  const tested = nodes.filter(n=>n.status==='tested').length;
  function edit(node) {
    setEditing(node?.id || 'new');
    setDraft({statement:node?.statement || '',test:node?.test || '',falsifier:node?.falsifier || ''});
    setError(''); setOpen(true);
  }
  async function change(node, patch) {
    setSaving(true);setError('');
    try {
      const base='/investigations/'+snapshot.id+'/hypotheses';
      const updated=await api(base+(node ? '/'+node : ''),{expected_revision:snapshot.revision,...patch},node ? {method:'PATCH'} : {});
      onUpdate?.(updated);setEditing(null);
    } catch(e) {setError(e.message)} finally {setSaving(false)}
  }
  return <section className="investigation-panel" aria-label="Editable investigation">
    <button className="investigation-toggle" aria-expanded={open} onClick={()=>setOpen(!open)}>
      <GitBranch size={18}/><span><strong>Investigation</strong><small>{tested} of {nodes.filter(n=>n.status!=='excluded').length} hypotheses tested · {readable(snapshot.status)}</small></span><ChevronDown size={17}/>
    </button>
    {open && <div className="investigation-content">
      <p className="investigation-question">{snapshot.question}</p>
      <p className="caption">Edit an idea here or correct it in the conversation. Changes preserve history and require affected tests to be rerun.</p>
      {nodes.length===0 && <p role="status">Verifying the baseline and preparing testable hypotheses…</p>}
      {nodes.map(n=><article key={n.id} className={'hypothesis-node '+(n.parent_id?'hypothesis-child ':'')+(n.status==='excluded'?'hypothesis-excluded':'')}>
        <div className="hypothesis-node-top"><span>{n.id}{n.parent_id ? ' · under '+n.parent_id : ''}</span><span className={'hypothesis-status status-'+n.status}>{readable(n.status==='tested'?n.verdict:n.status)}</span></div>
        <strong>{n.statement}</strong>
        <p><b>Test:</b> {n.test}</p><p><b>Would challenge it:</b> {n.falsifier}</p>
        {n.interpretation && <p className="hypothesis-finding">{n.interpretation}</p>}
        {!!n.evidence && <details><summary>Measured evidence</summary><pre>{JSON.stringify(n.evidence,null,2)}</pre></details>}
        <div className="hypothesis-node-actions"><button disabled={saving} onClick={()=>edit(n)}><Pencil size={13}/> Edit</button><button disabled={saving} onClick={()=>change(n.id,{excluded:n.status!=='excluded'})}>{n.status==='excluded'?<RotateCcw size={13}/>:<X size={13}/>} {n.status==='excluded'?'Restore':'Exclude'}</button></div>
      </article>)}
      {editing && <form className="hypothesis-edit" onSubmit={e=>{e.preventDefault();change(editing==='new'?null:editing,draft)}}>
        <strong>{editing==='new'?'Add hypothesis':'Edit '+editing}</strong>
        {[['statement','Hypothesis'],['test','How should it be tested?'],['falsifier','What result would challenge it?']].map(([key,label])=><label key={key}>{label}<textarea required maxLength={key==='test'?4000:2000} value={draft[key]} onChange={e=>setDraft({...draft,[key]:e.target.value})}/></label>)}
        <div className="hypothesis-node-actions"><button type="submit" disabled={saving}><Check size={14}/> {saving?'Saving…':'Save changes'}</button><button type="button" onClick={()=>setEditing(null)}>Cancel</button></div>
      </form>}
      {error && <p className="chat-error" role="alert">{error}</p>}
      <div className="investigation-actions"><button disabled={saving} onClick={()=>edit(null)}><Plus size={14}/> Add hypothesis</button><button className="continue-investigation" disabled={busy||saving} onClick={()=>onContinue?.(snapshot.id)}><RotateCcw size={14}/> Continue / retest</button></div>
      {busy && <p className="caption">You can edit while work runs. An edit stops the old run; continue when it has stopped.</p>}
      {snapshot.summary && <p className="investigation-summary">{snapshot.summary}</p>}
    </div>}
  </section>
}
