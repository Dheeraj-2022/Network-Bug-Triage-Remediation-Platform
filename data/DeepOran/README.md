# DeepORAN Genuine OAI RFsim Closed-Loop Telemetry

## Dataset summary

This dataset contains **13,000,000 accepted step-level observations** from a
verified OpenAirInterface (OAI) RFsim deployment running on six private Google
Cloud VMs. Three OAI nrUE processes generated packet traffic through an OAI gNB,
OAI 5G Core user plane, and external data network while a FlexRIC Near-RT RIC
provided E2 Slice Service Model control evidence.

The release is designed for network-telemetry modelling, SLA analysis, anomaly
detection, digital-twin training, and closed-loop controller research. All rows
are directly available in three previewable Parquet tables with an explicit
64-column Arrow schema. A complete verified source archive is also included for
one-file download. Train, validation, and test views are split by complete
scenario run, not by individual rows, to reduce direct temporal leakage.

> **Scientific boundary:** these are genuine measurements from running OAI
> software and real packets traversing its software user plane. The radio channel
> uses OAI RFsim. This is **not** physical over-the-air RF data and should not be
> presented as a field trial.

## Key facts

| Item | Value |
|---|---:|
| Accepted observations | 13,000,000 |
| Distinct observation IDs | 13,000,000 |
| Source snapshots retained by the original run | 27,873,317 |
| Rejected incomplete traffic observations | 773,078 |
| Collection period | 2026-09-01 19:49:06 to 2026-09-02 12:09:06 UTC |
| Measured duration | 58,799.8 seconds (16 h 20 min) |
| OAI nrUEs / slices | 3 / 3 |
| Traffic and fault scenarios | 10 |
| Distinct scenario runs represented | 185 |
| Columns | 64 |
| OAI RAN commit | `707aab3af1e072c6747e598a0b88beaabae1d903` |
| Dataset run ID | `real-oai-20260901T194849Z-64c30592` |
| Validation | PASS |

## What one row means

One row is one accepted **fresh source-counter change window x OAI nrUE x
configured S-NSSAI slice**. It is not a copied epoch and not a synthetic KPI
sample.

The collector requested up to 128 fresh snapshots per cross-VM transport batch
and waited at least 5 ms between source reads. Batching reduced HTTP round trips;
it did not duplicate observations. A row was accepted only when source sequence,
source time, tunnel counters, traffic measurements, MAC values, and required E2
controller evidence satisfied freshness and provenance gates.

The primary identity tuple is:

```text
run_id + exporter_boot_id + exporter_sequence + ue_id + slice_id
```

`observation_id` is the SHA-256 digest of that tuple. Duplicate source sequences
were blocked transactionally.

## Experimental topology

```text
3 OAI nrUE namespaces
  |  eMBB / URLLC / mMTC packet traffic
  v
OAI gNB (nr-softmodem, RFsim) <---- E2 ----> FlexRIC Near-RT RIC
  | N2/N3                                      | Slice SM evidence
  v                                            v
OAI 5G Core (AMF -> SMF -> UPF) -> ext-DN   agent-server collector
                                                  |
OAI journal + tunnel counters + ping/iperf3 + E2 evidence
                                                  |
                              raw snapshots -> aligned Parquet -> run splits

Prometheus and Grafana on the monitoring VM observed the deployment.
```

All experiment VMs used private VPC addresses in `us-central1-a` and were
accessed through Google Cloud IAP.

| VM | Machine type | Role in this experiment |
|---|---|---|
| `oai-core` | `n2-standard-4` | OAI 5G Core, UPF, subscriber and external-DN path |
| `oai-gnb` | `n2-standard-8` | OAI gNB, three isolated nrUEs, exporter and traffic probes |
| `ric-nearrt` | `n2-standard-4` | FlexRIC Near-RT RIC and E2 Slice SM control evidence |
| `agent-server` | `n2-standard-8` | Fail-closed collector, alignment, validation and Parquet writer |
| `twin-server` | `n2-standard-4` | Digital-twin service available to the wider DeepORAN pipeline |
| `monitoring` | `n2-standard-2` | Prometheus and Grafana monitoring |

## End-to-end collection path

1. Three OAI nrUE instances registered through the OAI gNB and 5G Core.
2. Each UE obtained a PDU session for its configured S-NSSAI/DNN.
3. TCP/UDP traffic and ping probes traversed `nrUE -> gNB -> UPF -> ext-DN`.
4. The gNB exporter read OAI process journals, MAC statistics, process identity,
   and Linux tunnel counters without generating KPI replacements.
5. The traffic agent measured RTT, throughput, jitter, and loss with `ping` and
   `iperf3` bound to the UE PDU-session interface.
6. The controller evidence service reported FlexRIC E2 association, Slice SM
   action acknowledgement, indicated state change, and restoration evidence.
7. The collector rejected stale, missing, unchanged, unhealthy, synthetic, or
   provenance-inconsistent observations.
8. Accepted windows were normalized to a fixed Arrow schema and committed to
   partitioned Parquet by run, scenario run, scenario, and slice.
9. Complete scenario runs were assigned to train, validation, or test sets.
10. Final validation checked row identity, required-field completeness, source
    labels, changing signals, control evidence, and exact target count.

No interpolation, generated KPI substitution, or real-to-synthetic fallback was
permitted in this collection path.

## Slice configuration and SLA labels

The three slice labels are experiment mappings based on S-NSSAI SST values.
They describe the configured traffic and QoS profiles; they are not claims of
standards certification.

| Slice | SST | DNN | UE subnet | 5QI | Session AMBR UL/DL | SLA predicate used for `sla_violation` |
|---|---:|---|---|---:|---|---|
| eMBB | 1 | `oai` | `12.1.1.0/24` | 9 | 200/400 Mbit/s | throughput >= 50 Mbit/s, latency <= 100 ms, loss <= 1% |
| URLLC | 2 | `oai_urllc` | `12.2.1.0/24` | 80 | 50/100 Mbit/s | throughput >= 5 Mbit/s, latency <= 1 ms, loss <= 0.1% |
| mMTC | 3 | `oai_mtc` | `12.3.1.0/24` | 9 | 20/40 Mbit/s | throughput >= 0.1 Mbit/s, latency <= 500 ms, loss <= 5% |

The SLA flag is derived from fresh measured KPIs. It is true when any predicate
for that row's slice is violated.

## Traffic and fault scenarios

| Scenario | Workload or intervention | Nominal duration |
|---|---|---:|
| `normal` | One reverse TCP flow; no injected fault | 300 s |
| `off_peak` | 1 Mbit/s UDP, 512-byte datagrams, long pauses | 300 s |
| `peak` | Two parallel TCP flows | 300 s |
| `embb_heavy` | Three sustained parallel TCP flows | 300 s |
| `urllc_heavy` | 10 Mbit/s UDP with 64-byte datagrams | 300 s |
| `mmtc_burst` | Bursty 2 Mbit/s UDP with 128-byte datagrams | 300 s |
| `mixed` | Concurrent measured traffic across all UEs | 300 s |
| `prb_contention` | Four parallel TCP flows with no programmed pause | 300 s |
| `backhaul_delay` | TCP plus Linux netem delay of 20 ms and 3 ms jitter | 180 s |
| `backhaul_loss` | 5 Mbit/s UDP plus Linux netem loss of 2% | 180 s |

## Dataset composition

### Rows by slice

| Slice | Rows | Share | SLA violations | Violation rate |
|---|---:|---:|---:|---:|
| eMBB (SST 1) | 3,445,417 | 26.50% | 3,441,668 | 99.89% |
| URLLC (SST 2) | 4,427,844 | 34.06% | 4,427,844 | 100.00% |
| mMTC (SST 3) | 5,126,739 | 39.44% | 4,486,565 | 87.51% |
| **All** | **13,000,000** | **100.00%** | **12,356,077** | **95.05%** |

The high rates are measured outcomes under strict thresholds, especially the
1 ms URLLC target in a VM-based RFsim topology. They make the release useful for
violation prediction and recovery research, but they do not demonstrate strong
SLA compliance.

### Rows by scenario

| Scenario | Rows |
|---|---:|
| `backhaul_delay` | 986,384 |
| `backhaul_loss` | 926,323 |
| `embb_heavy` | 1,343,532 |
| `mixed` | 1,328,206 |
| `mmtc_burst` | 1,911,211 |
| `normal` | 1,272,288 |
| `off_peak` | 1,136,477 |
| `peak` | 1,318,649 |
| `prb_contention` | 1,302,861 |
| `urllc_heavy` | 1,474,069 |

### Leakage-aware splits

| Split | Rows | Share |
|---|---:|---:|
| Train | 9,426,486 | 72.51% |
| Validation | 1,939,184 | 14.92% |
| Test | 1,634,330 | 12.57% |

The split unit is `scenario_run_id`. Rows from one scenario run do not appear in
more than one split. Adjacent rows within a run remain temporally correlated.

## Files in the Kaggle release

| Path | Description |
|---|---|
| `deeporan_oai_train.parquet` | Previewable training table: 9,426,486 rows |
| `deeporan_oai_validation.parquet` | Previewable validation table: 1,939,184 rows |
| `deeporan_oai_test.parquet` | Previewable test table: 1,634,330 rows |
| `split_manifest.json` | Scenario-run assignment for every split |
| `deeporan_oai_13m_real.tar.zst` | Complete verified one-file source archive |
| `deeporan_oai_13m_real.tar.zst.sha256` | Published checksum for the source archive |
| `DATA_DICTIONARY.md` | All 64 columns, Arrow types, units, categories and lineage |
| `schema.json` | Machine-readable Arrow schema summary |
| `summary_statistics.json` | Machine-readable counts, evidence and measured outcomes |
| `dataset_manifest.json` | Run identity, configuration digest, provenance and validation |
| `PROVENANCE_REPORT.md` | Source identity and transformation boundary |
| `VALIDATION_REPORT.md` | Final strict validation report |
| `EXPERIMENT_MANIFEST.md` | Run timing, VM roles and collection parameters |
| `deeporan_oai_sample.csv` | Small human-readable sample |
| `example_load.py` | Minimal PyArrow loading example |
| `SHA256SUMS` | SHA-256 digest for every uploaded data/document file |

The three top-level Parquet files are the convenient extracted dataset and sum
to exactly 13,000,000 rows. Kaggle can preview their schemas and values directly.
The `.tar.zst` file is the complete preservation bundle: it contains the retained
raw JSONL evidence, compact partitioned Parquet, split tables, reports, and
manifests. Extracting that archive requires substantially more free disk space
than its compressed download size.

## Column groups

The complete field-level reference is in `DATA_DICTIONARY.md`. The 64 columns
fall into these provenance groups:

- **Identity and experiment metadata:** observation/run/scenario IDs, slice,
  timestamps, repository/config identity, fault labels.
- **Measured OAI and host counters:** UE interface, process IDs, RNTI, CU UE ID,
  synchronization state, RSRP, BLER, MCS, UL NPRB, byte/packet/drop counters.
- **Measured traffic:** ping RTT, p95 RTT, iperf throughput, jitter, loss and
  traffic measurement timestamp.
- **Derived features:** counter-rate throughput, packet-loss ratio, PRB
  utilization, aligned latency/throughput and SLA predicate.
- **Measured controller evidence:** E2 control epoch/action, acknowledgement,
  active/effect/restoration flags, service model, RAN-function ID and E2-node
  count.

For this run, all accepted rows report one E2 node, `FlexRIC Slice SM`, service
model ID 145, and controller evidence source
`FLEXRIC_E2_SLICE_CONTROL_AND_INDICATION`. All 13M accepted rows have true
acknowledgement, active-control, and observed-effect flags.

## Quick start

```python
from pathlib import Path
import pyarrow.dataset as ds

root = Path("/kaggle/input/deeporan-agent-6g-o-ran-network-slice-dataset")
split_files = [
    root / "deeporan_oai_train.parquet",
    root / "deeporan_oai_validation.parquet",
    root / "deeporan_oai_test.parquet",
]
data = ds.dataset(split_files, format="parquet")

print(data.count_rows())  # 13_000_000
print(data.schema)

# Filter without loading all rows into memory.
urllc = data.to_table(
    columns=[
        "timestamp_utc",
        "scenario_id",
        "throughput_mbps",
        "latency_ms",
        "packet_loss_ratio",
        "prb_utilization",
        "sla_violation",
    ],
    filter=ds.field("slice_id") == 2,
)
```

For model evaluation, load one provided split file rather than randomly
splitting individual rows.

## Validation evidence

- Exact row target reached: 13,000,000.
- Distinct IDs: 13,000,000.
- Required-field missing values: zero.
- Positive PRB rows: 13,000,000.
- Positive throughput rows: 12,999,956.
- Distinct throughput values: 9,112,416.
- Distinct latency values: 13,028.
- Distinct source timestamps: 8,048,914.
- Accepted source label:
  `OAI_GNB_JOURNAL_AND_NRUE_TUNNEL_COUNTERS` only.
- Compact-release file checksums are provided in `SHA256SUMS`.

## Intended uses

- KPI forecasting and multivariate sequence modelling.
- SLA-violation classification and early warning.
- Fault, congestion and traffic-profile classification.
- Digital-twin model development.
- Closed-loop policy evaluation with leakage-aware splits.
- Data-quality and provenance research for O-RAN experiments.

## Uses requiring caution

- Do not treat adjacent rows as independent samples.
- Do not claim physical-radio or over-the-air performance.
- Do not infer broad 5G deployment performance from one RFsim topology.
- Do not use the dataset alone to claim one controller is superior to another;
  it records one deployment/run and contains no randomized controller baseline.
- Do not treat configured eMBB/URLLC/mMTC labels as service certification.
- Do not conceal the high SLA-violation prevalence when reporting model scores;
  use class-aware metrics and per-slice evaluation.

## Reproducibility identifiers

```text
run_id: real-oai-20260901T194849Z-64c30592
repository: tree-sha256:ab64d11e7b9689eaaaa06cc51230e7295b6909bc32ea1d91910a1d80de85b7cc
configuration_sha256: f0ad63bfafb14eb1ae8c03919bed01fcbce6b2b7ad209b53bec32a44c7891edc
oai_ran_commit: 707aab3af1e072c6747e598a0b88beaabae1d903
```

## License and citation

The Kaggle metadata uses **GPL-3.0**, matching the author's existing DeepORAN
Kaggle release. Review the selected license and dataset contents before changing
the private draft to public visibility.

Suggested citation:

```text
Qayyum, R. (2026). DeepORAN Genuine OAI RFsim Closed-Loop Telemetry
(13 Million Observations), dataset run real-oai-20260901T194849Z-64c30592.
```
