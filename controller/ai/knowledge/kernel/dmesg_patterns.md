# Reference: Kernel Log (dmesg) Fault Patterns

**Fault domains:** KERNEL_PANIC, DRIVER_FAULT

## High-signal log patterns
| Pattern (case-insensitive)        | Fault domain   | Action                     |
|-----------------------------------|----------------|----------------------------|
| `kernel panic`, `oops`, `BUG:`    | KERNEL_PANIC   | collect_forensics + escalate |
| `call trace`, `RIP:`              | KERNEL_PANIC   | collect_forensics          |
| `mlx5_core ... reset`             | DRIVER_FAULT   | restart_driver             |
| `firmware bug detected`           | DRIVER_FAULT   | restart_driver + escalate  |
| `MTU mismatch`, `fragmentation`   | MTU_MISMATCH   | remediate_mtu              |
| `NETDEV WATCHDOG`, `queue timeout`| DRIVER_FAULT   | restart_driver             |
| `link down` / `link up` (flapping)| LINK_FLAP      | inspect cabling / SFP      |

## Triage guidance
- A kernel panic or oops is **not** auto-remediable. Always collect forensics
  and route to a human; a driver restart will not clear a panicked kernel.
- Repeated driver resets within a short window indicate a firmware defect —
  collect forensics before the next restart so the vendor has a core dump.
- Correlate the timestamp of the log line with the interface counter deltas to
  confirm cause vs. coincidence.
