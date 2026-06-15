#!/usr/bin/env bash

set -euo pipefail

# Скрипт принимает готовые артефакты Windows-сборки и отправляет их на rdgen/api.
# Выносим это в отдельный модуль, чтобы одинаковая логика повторных попыток
# и сетевых таймаутов не дублировалась по нескольким workflow-файлам.
target_url="${1:?target url is required}"
uuid_value="${2:-}"
filename_value="${3:?filename is required}"
output_dir="${4:-./SignOutput}"
auth_token="${5:-}"

# EXE обязателен для любой Windows-сборки, поэтому если его нет,
# workflow должен завершиться явной ошибкой еще до запроса на сервер.
exe_path="${output_dir}/${filename_value}.exe"
if [[ ! -f "${exe_path}" ]]; then
  echo "Missing required artifact: ${exe_path}" >&2
  exit 1
fi

# MSI может отсутствовать в некоторых сценариях, поэтому ниже он отправляется
# только если реально был собран и лежит рядом с EXE.
msi_path="${output_dir}/${filename_value}.msi"

auth_header=()
if [[ -n "${auth_token}" ]]; then
  auth_header=(-H "Authorization: Bearer ${auth_token}")
fi

upload_file() {
  local file_path="$1"

  # Для Windows runner используем HTTP/1.1 и длинные сетевые таймауты:
  # это заметно устойчивее для медленной передачи крупных EXE/MSI через schannel.
  curl \
    --fail \
    --show-error \
    --location \
    --http1.1 \
    --connect-timeout 30 \
    --max-time 1800 \
    --retry 5 \
    --retry-delay 10 \
    --retry-all-errors \
    -X POST \
    "${auth_header[@]}" \
    -F "file=@${file_path}" \
    -F "uuid=${uuid_value}" \
    "${target_url}"
}

upload_file "${exe_path}"

if [[ -f "${msi_path}" ]]; then
  upload_file "${msi_path}"
fi
