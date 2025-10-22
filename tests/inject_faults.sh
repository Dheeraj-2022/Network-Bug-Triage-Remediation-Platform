#!/usr/bin/env bash
#
# tests/inject_faults.sh
#
# Fault injection helper for the network-bug-triage testbed.
#
# Supports:
#   - mtu: set MTU on an interface (useful to create MTU mismatch faults)
#   - loss: add packet loss to an interface with `tc netem`
#   - driver_crash: remove a kernel module (simulate driver oops/crash)
#   - restore: restore previous state for mtu/loss/driver
#
# This script prefers using Ansible ad-hoc commands (uses infra/inventory.ini).
# If Ansible is not available or inventory not provided, you can pass SSH details:
#   -h <host_ip> -u <user> -k <ssh_key>
#
# Usage:
#   ./inject_faults.sh --action mtu --target node1 --iface eth0 --mtu 1400
#   ./inject_faults.sh --action loss --target node2 --iface eth0 --loss 10
#   ./inject_faults.sh --action driver_crash --target node3 --driver mlx5_core
#   ./inject_faults.sh --action restore --target node3 --iface eth0
#
# NOTE: Use with caution. Actions are destructive (driver unload, netem).
# Always test on non-production isolated testbed only.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INVENTORY="${SCRIPT_DIR}/../infra/inventory.ini"

usage() {
  cat <<EOF
Usage: $0 --action <mtu|loss|driver_crash|restore> [options]

Options:
  --action        Fault action (mtu | loss | driver_crash | restore)
  --target        Inventory hostname (e.g. node1) or host IP (if using ssh)
  --iface         Interface name (eth0, ens2, etc.)
  --mtu           Desired MTU when action=mtu (e.g. 1400)
  --loss          Packet loss percent when action=loss (e.g. 10)
  --driver        Kernel module name when action=driver_crash (e.g. mlx5_core)
  --ansible       Use ansible ad-hoc (default if infra/inventory.ini exists)
  --ssh-user      SSH user for direct SSH execution (fallback)
  --ssh-key       SSH private key file for direct SSH execution (fallback)
  --help

Examples:
  $0 --action mtu --target node1 --iface eth0 --mtu 1400 --ansible
  $0 --action loss --target node2 --iface eth0 --loss 10 --ansible
  $0 --action driver_crash --target node3 --driver mlx5_core --ansible
  $0 --action restore --target node1 --iface eth0 --ansible
EOF
  exit 1
}

# parse args
ACTION=""
TARGET=""
IFACE=""
MTU=""
LOSS=""
DRIVER=""
USE_ANSIBLE=false
SSH_USER=""
SSH_KEY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --action) ACTION="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --iface) IFACE="$2"; shift 2 ;;
    --mtu) MTU="$2"; shift 2 ;;
    --loss) LOSS="$2"; shift 2 ;;
    --driver) DRIVER="$2"; shift 2 ;;
    --ansible) USE_ANSIBLE=true; shift ;;
    --ssh-user) SSH_USER="$2"; shift 2 ;;
    --ssh-key) SSH_KEY="$2"; shift 2 ;;
    --help) usage ;;
    *) echo "Unknown arg: $1"; usage ;;
  esac
done

if [[ -z "$ACTION" || -z "$TARGET" ]]; then
  echo "Error: --action and --target are required"
  usage
fi

# If inventory exists and ansible requested or inventory present, prefer ansible
if [[ -f "${INVENTORY}" && "${USE_ANSIBLE}" = false ]]; then
  echo "Found infra/inventory.ini — defaulting to Ansible unless --ssh-user provided"
  USE_ANSIBLE=true
fi
