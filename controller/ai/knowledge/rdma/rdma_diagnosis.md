# Reference: RDMA / RoCE Fault Diagnosis

**Fault domain:** RDMA_ERROR

## Key counters
- `qp_errors` — Queue Pair errors. Any non-zero value indicates an RDMA
  connection entered an error state and requires investigation.
- `rq_errors` — Receive Queue errors, often caused by receiver-not-ready or
  buffer exhaustion.
- `srq_errors` — Shared Receive Queue errors.

## Common causes
1. **MTU mismatch on the RoCE fabric** — large RDMA segments are dropped,
   surfacing as `qp_errors`. Fix the MTU first (see mtu_mismatch runbook).
2. **PFC / ECN misconfiguration** — priority flow control not enabled end to end
   causes pause-frame storms and QP timeouts.
3. **Driver/firmware fault on mlx5_core** — see driver_fault runbook.
4. **Cable / transceiver degradation** — rising symbol errors, intermittent QP
   resets isolated to a single host-port.

## Diagnosis order
1. Check `dmesg` for `mlx5_core` assertions or `RDMA QP reset`.
2. Correlate `qp_errors` across hosts sharing the same ToR switch. A fabric-wide
   pattern points to MTU/PFC; a single-host pattern points to driver/hardware.
3. Verify MTU consistency before restarting drivers — restarting a driver will
   not fix a fabric MTU mismatch.

## Remediation mapping
- Fabric-wide QP errors + MTU anomaly  -> remediate_mtu.yml
- Single-host QP errors + driver oops   -> restart_driver.yml
- Unexplained / hardware-suspected      -> collect_forensics.yml, escalate
