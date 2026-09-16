#!/usr/bin/env bash
set -euo pipefail
# 仅清理本项目标记的残留容器，保留训练记录。
ids=$(docker ps -aq --filter label=agentlab=true)
if [ -n "$ids" ]; then docker rm -f $ids; fi
