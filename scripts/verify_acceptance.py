"""Check executed evidence, not just the exit status of pytest/Playwright."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ORIGINAL_DOCKER_TESTS = {
    f'test_task_versions[{version}-{task}]'
    for version in ['initial/solution.py', 'private/normal.py', 'private/reference.py']
    for task in ['rag', 'retry', 'resume']
} | {'test_evasion[rag]', 'test_evasion[retry]', 'test_actual_infinite_loop', 'test_e2e_real_execution'}

REQUIRED_DOCKER_TESTS = ORIGINAL_DOCKER_TESTS | {
    'test_evasion[resume]',
    'test_container_abnormal_exit',
    r'test_run_failure_terminal_and_cleanup[while True: pass\n-timeout]',
    r'test_run_failure_terminal_and_cleanup[import os\nos._exit(7)\n-error]',
    'test_real_backend_restart_interrupts_running_container',
}


def verify_pytest(path):
    cases = list(ET.parse(path).iter('testcase'))
    docker = [c for c in cases if c.get('classname', '').endswith('test_docker_acceptance')]
    executed = {c.get('name') for c in docker if not any(c.find(tag) is not None for tag in ['skipped', 'failure', 'error'])}
    missing = sorted(REQUIRED_DOCKER_TESTS - executed)
    nonpassing = [c.get('name') for c in cases if any(c.find(tag) is not None for tag in ['skipped', 'failure', 'error'])]
    result = {'original_docker_required': 13, 'original_docker_passed': len(ORIGINAL_DOCKER_TESTS & executed),
              'docker_required': len(REQUIRED_DOCKER_TESTS), 'docker_passed': len(REQUIRED_DOCKER_TESTS & executed),
              'missing_or_not_passed': missing, 'all_tests': len(cases), 'nonpassing': nonpassing}
    result['passed'] = not missing and not nonpassing and len(cases) >= len(REQUIRED_DOCKER_TESTS)
    return result


def verify_browser(path):
    report = json.loads(Path(path).read_text())
    def walk(suite):
        yield from suite.get('specs', [])
        for child in suite.get('suites', []): yield from walk(child)
    specs = [spec for suite in report.get('suites', []) for spec in walk(suite)]
    required = '真实 Docker 提交报告闭环'
    def passed(spec):
        return bool(spec.get('tests')) and all(t.get('expectedStatus') == 'passed' and t.get('results') and
             all(r.get('status') == 'passed' for r in t['results']) for t in spec['tests'])
    stats = report.get('stats', {})
    return {'passed': bool(specs) and any(spec['title'] == required and passed(spec) for spec in specs) and
            all(passed(spec) for spec in specs) and not report.get('errors') and not stats.get('skipped') and not stats.get('unexpected'),
            'stats': stats, 'required_flow': required}


if __name__ == '__main__':
    stage, path = sys.argv[1:]
    result = verify_pytest(path) if stage == 'pytest' else verify_browser(path)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    Path(path).with_suffix('.verified.json').write_text(text)
    print(text)
    raise SystemExit(0 if result['passed'] else 1)
