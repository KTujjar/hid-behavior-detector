#!/usr/bin/env bash
set -euo pipefail

# Emits JSONL HID provenance events based on udev add/remove actions.
# Optional trust list format (comma-separated): "046d:c31c,1d6b:0002"
TRUSTED_PAIRS="${TRUSTED_HID_PAIRS:-}"

contains_pair() {
  local haystack="$1"
  local needle="$2"
  [[ ",${haystack}," == *",${needle},"* ]]
}

emit_event() {
  local action="$1"
  local subsystem="$2"
  local devnode="$3"
  local devpath="$4"
  local vendor_id="$5"
  local product_id="$6"
  local serial="$7"
  local keyboard="$8"

  local trusted=false
  if [[ -n "$vendor_id" && -n "$product_id" ]]; then
    local pair
    pair="${vendor_id,,}:${product_id,,}"
    if contains_pair "${TRUSTED_PAIRS,,}" "$pair"; then
      trusted=true
    fi
  fi

  local ts_ns
  ts_ns="$(date +%s%N)"
  printf '{"ts_ns":%s,"type":"hid_attach","action":"%s","subsystem":"%s","devnode":"%s","devpath":"%s","vendor_id":"%s","product_id":"%s","serial":"%s","keyboard":%s,"trusted":%s}\n' \
    "$ts_ns" "$action" "$subsystem" "$devnode" "$devpath" "$vendor_id" "$product_id" "$serial" "$keyboard" "$trusted"
}

flush_block() {
  local action="${KV_ACTION:-}"
  local subsystem="${KV_SUBSYSTEM:-}"
  local devnode="${KV_DEVNAME:-}"
  local devpath="${KV_DEVPATH:-}"
  local vendor_id="${KV_ID_VENDOR_ID:-}"
  local product_id="${KV_ID_MODEL_ID:-}"
  local serial="${KV_ID_SERIAL_SHORT:-}"
  local keyboard=false

  if [[ "${KV_ID_INPUT_KEYBOARD:-0}" == "1" ]]; then
    keyboard=true
  fi

  if [[ -n "$action" && "$action" != "change" && "$action" != "bind" && "$action" != "unbind" ]]; then
    emit_event "$action" "$subsystem" "$devnode" "$devpath" "$vendor_id" "$product_id" "$serial" "$keyboard"
  fi

  unset KV_ACTION KV_SUBSYSTEM KV_DEVNAME KV_DEVPATH KV_ID_VENDOR_ID KV_ID_MODEL_ID KV_ID_SERIAL_SHORT KV_ID_INPUT_KEYBOARD
}

udevadm monitor --udev --property --subsystem-match=input |
while IFS= read -r line; do
  if [[ -z "$line" ]]; then
    flush_block
    continue
  fi

  if [[ "$line" == UDEV* ]]; then
    continue
  fi

  if [[ "$line" != *=* ]]; then
    continue
  fi

  key="${line%%=*}"
  value="${line#*=}"
  case "$key" in
    ACTION) KV_ACTION="$value" ;;
    SUBSYSTEM) KV_SUBSYSTEM="$value" ;;
    DEVNAME) KV_DEVNAME="$value" ;;
    DEVPATH) KV_DEVPATH="$value" ;;
    ID_VENDOR_ID) KV_ID_VENDOR_ID="$value" ;;
    ID_MODEL_ID) KV_ID_MODEL_ID="$value" ;;
    ID_SERIAL_SHORT) KV_ID_SERIAL_SHORT="$value" ;;
    ID_INPUT_KEYBOARD) KV_ID_INPUT_KEYBOARD="$value" ;;
  esac
done
