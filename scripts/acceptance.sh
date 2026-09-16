#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/acceptance
acceptance_dir=$(mktemp -d "$PWD/data/acceptance/run-XXXXXX")
export AGENTLAB_ACCEPTANCE_DIR="$acceptance_dir"
export PLAYWRIGHT_JSON_OUTPUT_FILE="$acceptance_dir/browser.json"
echo "验收证据目录：$acceptance_dir"
.venv/bin/python scripts/docker_check.py > "$acceptance_dir/docker.json" || {
  cat "$acceptance_dir/docker.json"
  echo '验收阻塞：未执行 Docker 测试，不得报告验收通过。'
  exit 2
}
cat "$acceptance_dir/docker.json"
pytest_status=0
.venv/bin/python -m pytest tests -v -o junit_family=xunit1 --junitxml="$acceptance_dir/pytest.xml" || pytest_status=$?
.venv/bin/python scripts/verify_acceptance.py pytest "$acceptance_dir/pytest.xml"
if [ "$pytest_status" -ne 0 ]; then exit "$pytest_status"; fi
npm --prefix frontend run build
browser_status=0
npm --prefix frontend run test:e2e -- --reporter=list,json || browser_status=$?
.venv/bin/python scripts/verify_acceptance.py browser "$acceptance_dir/browser.json"
if [ "$browser_status" -ne 0 ]; then exit "$browser_status"; fi
echo '验收通过：全部 18 项 Docker 测试及浏览器提交闭环均已实际执行且通过，无跳过。'
