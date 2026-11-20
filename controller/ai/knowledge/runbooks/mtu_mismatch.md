# Runbook: MTU Mismatch Remediation

**Fault domain:** MTU_MISMATCH
**Playbook:** remediate_mtu.yml
**Severity:** medium

## Symptoms
- `dmesg` contains "MTU mismatch detected" or "fragmentation needed".
- Interface `mtu` differs from the fabric standard (1500 for classic Ethernet,
  9000 for jumbo-frame RDMA fabrics).
- Intermittent TCP stalls, large-packet drops, RoCE throughput collapse while
  ping (small packets) still succeeds.

## Root cause
A NIC or bond interface is configured with an MTU that does not match its peers
or the switch fabric. On RoCE/RDMA fabrics an MTU mismatch silently drops large
RDMA segments, producing QP errors downstream.

## Remediation
1. Identify the expected fabric MTU from `infra/group_vars/all.yml`.
2. Apply `remediate_mtu.yml` with `target_mtu` set to the fabric standard.
3. Use a **canary** rollout: remediate one host, verify large-packet ping
   (`ping -M do -s 8972 <peer>`), then roll out to the rest.

## Rollback
Re-apply the previous MTU captured in the audit log. The playbook stores the
prior value in `logs/remediation_audit.log`.

## Validation
- Large-packet ping succeeds end to end.
- `errin`/`errout` counters stop incrementing.
- RDMA `qp_errors` return to zero within 60s.
