# Runbook: NIC Driver Fault / Firmware Reset

**Fault domain:** DRIVER_FAULT
**Playbook:** restart_driver.yml
**Severity:** high

## Symptoms
- `dmesg` shows "driver: kernel oops", "firmware bug detected", "mlx5_core ...
  reset", or repeated "Rx/Tx queue timeout".
- Rising `errin`/`errout` on the affected interface.
- Interface flaps or disappears from `ip link`.

## Root cause
The NIC driver or firmware has entered a wedged state — commonly after a
firmware assertion, DMA timeout, or a kernel oops in the driver's interrupt
path. Traffic on the affected queues stalls until the driver is reloaded.

## Remediation
1. Collect forensics first (`collect_forensics.yml`) so the crash context is
   preserved for the kernel team.
2. Apply `restart_driver.yml`, which unbinds and rebinds the driver module and
   re-initialises the NIC.
3. Prefer a canary rollout; a driver reload briefly drops the link.

## Rollback
Driver reload is self-contained. If the NIC does not return, escalate to
hardware replacement — there is no software rollback for firmware faults.

## Validation
- Interface returns to `UP` state.
- `errin`/`errout` stop incrementing.
- No new oops/assertion lines in `dmesg` for 5 minutes.
