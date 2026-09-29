"""Explicit, billable live checks against the running local app.

Run manually: .venv-runtime/bin/python -m retail_app.tests.live_smoke baseline
Other phases: followup, investigation, statistics, gaps. Requires the baseline
phase before followup. Does not read or print credentials. Results stay in the
ignored local state directory. These are smoke checks, not full semantic evals.
"""
import argparse
import json
import re
import time
from pathlib import Path

import httpx

STATE = Path(__file__).resolve().parents[1] / 'state' / 'live_smoke'
SCOPE = dict(start='2025-01-01', end='2025-01-31',
             compare_start='2024-01-01', compare_end='2024-01-31')
QUESTIONS = {
    'baseline': 'What were total net sales before returns, sold units, and order count across all channels in January 2025? Query the warehouse and cite evidence. Keep the answer brief.',
    'followup': 'For that same period and metric basis, break those metrics down by channel. Reconcile the channel totals to the previous answer and show a sales bar chart.',
    'investigation': 'Investigate January 2025 versus January 2024 net sales before returns across all channels. Retrieve retail-specific candidate explanations and falsifiers with search_hypothesis_bank. Inspect the division-level current/prior sales distribution. Save and test two small competing hypotheses with investigate_hypotheses. Quantify division contributions to the total sales change and call reconcile_breakdown to verify the partition. Query actual data, distinguish accounting drivers from causation, and finish with a short evidence-backed synthesis.',
    'statistics': 'For this tool validation, query daily all-channel net sales before returns for January 2025, then call statistical_analysis with operation describe on the measured daily sales column and evidence ID. Exercise that statistics tool explicitly; do not replace it with a SQL summary. You can handle this directly without delegating. Report the number of days, mean and range with evidence. Do not use inferential tests on this synthetic monthly census. Keep the response brief.',
    'gaps': 'How much incremental revenue did loyalty membership cause in January 2025? Check the available documentation and explain whether the data identifies causal impact. Do not substitute member versus nonmember differences as causal lift. Keep the answer brief.',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=list(QUESTIONS))
    args = parser.parse_args()
    STATE.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(base_url='http://127.0.0.1:8766',
                          headers={'X-Retail-App': 'local'}, timeout=30)
    status = client.get('/api/status').raise_for_status().json()
    assert status['agent_ready'], 'Model is not configured'
    payload = {**SCOPE, 'question': QUESTIONS[args.phase],
               'mode': 'deep' if args.phase == 'investigation' else 'auto'}
    if args.phase == 'followup':
        payload['conversation_id'] = json.loads((STATE / 'baseline.json').read_text())['conversation_id']
    started = time.monotonic()
    submitted = client.post('/api/chat', json=payload).raise_for_status().json()
    last = None
    while time.monotonic() - started < 720:
        job = client.get('/api/chat/jobs/' + submitted['job_id']).raise_for_status().json()
        current = (job['status'], job.get('message'))
        if current != last:
            print(args.phase + ': ' + str(current), flush=True)
            last = current
        if job['status'] != 'running':
            break
        time.sleep(2)
    else:
        raise RuntimeError('Timed out waiting for this live check; inspect the app job before retrying.')
    assert job['status'] == 'complete', job.get('error') or job
    conversation = client.get('/api/conversations/' + submitted['conversation_id']).raise_for_status().json()
    result = conversation['messages'][-1]['analysis']
    assert result['mode'] == 'agent' and result['answer']
    assert result['model'] == status['model']
    exported = client.get('/api/export/' + result['id']).raise_for_status().json()
    assert exported['answer'] == result['answer']
    if args.phase != 'gaps':
        assert result['outputs'], 'No measured evidence returned'
        assert '[E' in result['answer'], 'No evidence citations in answer'
        client.get('/api/export/' + result['id'], params={'format': 'csv'}).raise_for_status()
    summary = {'phase': args.phase, 'model': result['model'],
               'conversation_id': submitted['conversation_id'],
               'analysis_id': result['id'], 'seconds': round(time.monotonic()-started, 1),
               'tools': [t['tool'] for t in result['trace']],
               'specialists': [s['role'] for s in result['specialists']],
               'tool_errors': [t for t in result['trace'] if t['status'] == 'error'],
               'evidence_count': len(result['outputs']), 'chart_count': len(result['charts']),
               'result': result}
    (STATE / (args.phase + '.json')).write_text(json.dumps(summary, indent=2))
    evidence_ids={o['evidence_id'] for o in result['outputs']}
    for answer in [result['answer']]+[s['answer'] for s in result['specialists']]:
        cited=set(re.findall(r'\[(E\d+)\]',answer))
        assert cited <= evidence_ids, 'Answer cites evidence that was not saved: '+str(cited-evidence_ids)
    if args.phase == 'investigation':
        completed={item['tool'] for item in result['trace'] if item['status']=='complete'}
        assert {'search_hypothesis_bank','investigate_hypotheses','reconcile_breakdown'} <= completed, 'Some requested investigation capabilities were not exercised'
        assert not summary['specialists'], 'Investigation should use the single primary agent'
    if args.phase == 'statistics':
        all_traces=result['trace']+[t for s in result['specialists'] for t in s['trace']]
        assert any(t['tool'] == 'statistical_analysis' and t['status'] == 'complete'
                   for t in all_traces), 'Statistics tool not exercised'
    print(json.dumps({k: v for k, v in summary.items() if k != 'result'}, indent=2), flush=True)
    print(result['answer'], flush=True)


if __name__ == '__main__':
    main()
