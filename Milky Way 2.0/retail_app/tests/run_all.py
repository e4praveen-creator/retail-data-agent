"""Run offline regressions and save the app's quality report and UI fixtures.

Run from the project root: .venv-runtime/bin/python -m retail_app.tests.run_all
No real model calls. Application state is isolated before importing the server.
"""
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import unittest


def main():
    app = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='retail-tests-') as isolated:
        os.environ['RETAIL_STATE_DIR'] = isolated
        suite = unittest.defaultTestLoader.discover(str(app / 'tests'), top_level_dir=str(app.parent))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        from retail_app.tests.test_app import ReportTests
        if hasattr(ReportTests, 'results'):
            (app / 'tmp').mkdir(exist_ok=True)
            (app / 'tmp/frontend-fixtures.json').write_text(json.dumps(list(ReportTests.results.values()), default=str))
            from retail_app.backend.presentation import finish_presentation
            report=ReportTests.results['cohorts']
            structured=finish_presentation({'report':report,'outputs':report['outputs'],'period':report['period'],'answer':report['summary']})
            (app / 'tmp/structured-answer-fixture.json').write_text(json.dumps(structured,default=str))
    report = {
        'total': result.testsRun,
        'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        'failures': [str(test) for test, _ in result.failures + result.errors],
        'skipped': len(result.skipped),
        'run_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'live_agent_tested': False,
        'coverage': 'Full warehouse recipes and hypotheses; independent metric reconciliations; API, persistence, cancellation and fault recovery; bounded SQL and model context; provenance and specialist reuse; evaluation grading. Model calls are mocked; browser interactions are not tested.',
    }
    (app / 'state').mkdir(exist_ok=True)
    (app / 'state/eval_report.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
