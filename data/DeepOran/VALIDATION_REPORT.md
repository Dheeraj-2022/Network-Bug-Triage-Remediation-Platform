# Real OAI Dataset Validation

- Validated: `2026-09-02T16:37:36.235684+00:00`
- Rows: `13,000,000`
- Distinct IDs: `13,000,000`
- Result: `PASS`

## Rows by scenario

- `backhaul_delay`: 986,384
- `backhaul_loss`: 926,323
- `embb_heavy`: 1,343,532
- `mixed`: 1,328,206
- `mmtc_burst`: 1,911,211
- `normal`: 1,272,288
- `off_peak`: 1,136,477
- `peak`: 1,318,649
- `prb_contention`: 1,302,861
- `urllc_heavy`: 1,474,069

## Missing values

- `throughput_mbps`: 0
- `latency_ms`: 0
- `ul_nprb`: 0
- `control_acknowledged`: 0

## Required-field missingness

- `throughput_mbps`: 0
- `latency_ms`: 0
- `packet_loss_ratio`: 0
- `ul_nprb`: 0
- `prb_utilization`: 0
- `sla_violation`: 0
- `control_acknowledged`: 0
- `control_active`: 0
- `control_effect_observed`: 0
- `control_service_model_id`: 0
- `control_e2_node_count`: 0
- `control_data_source`: 0

## Signal statistics

- `positive_throughput_rows`: 12,999,956
- `positive_prb_rows`: 13,000,000
- `distinct_throughput_values`: 9,112,416
- `distinct_latency_values`: 13,028
- `distinct_ul_nprb_values`: 84
- `distinct_source_timestamps`: 8,048,914
