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


ADVANCED_DOCKER_TESTS={f'test_versioning_versions[{v}]' for v in ['initial','normal','reference']} | {f'test_versioning_evasions[{v}]' for v in ['clear_all','unconditional','rank_only','memory_only']} | {'test_multifile_submission_docker'}

def verify_pytest(path):
    cases = list(ET.parse(path).iter('testcase'))
    docker = [c for c in cases if c.get('classname', '').endswith('test_docker_acceptance')]
    executed = {c.get('name') for c in docker if not any(c.find(tag) is not None for tag in ['skipped', 'failure', 'error'])}
    advanced={c.get('name') for c in cases if c.get('classname','').endswith('test_versioning_docker') and not any(c.find(tag) is not None for tag in ['skipped','failure','error'])}
    generated=any(c.get('classname','').endswith('test_generation') and c.get('name')=='test_generated_docker_publish_train_freeze' and not any(c.find(tag) is not None for tag in ['skipped','failure','error']) for c in cases)
    missing = sorted((REQUIRED_DOCKER_TESTS - executed) | (ADVANCED_DOCKER_TESTS - advanced))
    if not generated:missing.append('test_generated_docker_publish_train_freeze')
    roles=any(c.get('name')=='test_generated_docker_automatic_scoped_repair' and not any(c.find(tag) is not None for tag in ['skipped','failure','error']) for c in cases)
    if not roles:missing.append('test_generated_docker_automatic_scoped_repair')
    contract=any(c.get('name')=='test_generated_docker_contract_local_correction_revalidates' and not any(c.find(tag) is not None for tag in ['skipped','failure','error']) for c in cases)
    if not contract:missing.append('test_generated_docker_contract_local_correction_revalidates')
    reliability=any(c.get('name')=='test_generated_docker_rollback_runs_fresh_without_extra_gates' and not any(c.find(tag) is not None for tag in ['skipped','failure','error']) for c in cases)
    if not reliability:missing.append('test_generated_docker_rollback_runs_fresh_without_extra_gates')
    protocol=any(c.get('name')=='test_generated_docker_v2_classification_repair_and_binding' and not any(c.find(tag) is not None for tag in ['skipped','failure','error']) for c in cases)
    if not protocol:missing.append('test_generated_docker_v2_classification_repair_and_binding')
    direct=any(c.get('name')=='test_direct_docker_build_review_repair_publish_train' and not any(c.find(tag) is not None for tag in ['skipped','failure','error']) for c in cases)
    if not direct:missing.append('test_direct_docker_build_review_repair_publish_train')
    nonpassing = [c.get('name') for c in cases if any(c.find(tag) is not None for tag in ['skipped', 'failure', 'error'])]
    result = {'direct_build_docker_passed':direct,'protocol_v2_docker_passed':protocol,'rollback_docker_passed':reliability,'contract_revision_docker_passed':contract,'roles_docker_repair_passed':roles,'generated_docker_flow_passed':generated,'original_docker_required': 13, 'original_docker_passed': len(ORIGINAL_DOCKER_TESTS & executed),
              'advanced_docker_required':len(ADVANCED_DOCKER_TESTS),'advanced_docker_passed':len(ADVANCED_DOCKER_TESTS & advanced),
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
    required = ['回退后成本展示与作者摘要（MOCK，实际Docker）','真实 Docker 提交报告闭环','进阶多文件 Docker 提交与快照恢复闭环','生成审核发布及 Docker 训练报告闭环（明确 MOCK）','自动诊断修复、预算耗尽和明确授权新批次（MOCK，实际Docker）','需求澄清、局部契约版本、重新验证和刷新（MOCK，实际Docker）']
    def passed(spec):
        return bool(spec.get('tests')) and all(t.get('expectedStatus') == 'passed' and t.get('results') and
             all(r.get('status') == 'passed' for r in t['results']) for t in spec['tests'])
    stats = report.get('stats', {})
    return {'passed': bool(specs) and all(any(spec['title']==title and passed(spec) for spec in specs) for title in required) and
            all(passed(spec) for spec in specs) and not report.get('errors') and not stats.get('skipped') and not stats.get('unexpected'),
            'stats': stats, 'required_flow': required}


if __name__ == '__main__':
    stage, path = sys.argv[1:]
    result = verify_pytest(path) if stage == 'pytest' else verify_browser(path)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    Path(path).with_suffix('.verified.json').write_text(text)
    print(text)
    raise SystemExit(0 if result['passed'] else 1)
