# Data Dictionary

Each row is one accepted source-counter change window for one OAI nrUE and its configured S-NSSAI slice.
The collector requests up to `128` fresh local OAI snapshots per transport batch, then waits at least `5 ms` before the next request; rows are omitted when no packet counter changes.
A null means the named source did not expose that optional value in the aligned freshness window. Fields configured as required cannot be null in an accepted run.

| Column | Arrow type | Unit | Category | Source or calculation |
|---|---|---|---|---|
| `observation_id` | `string` | - | `DERIVED` | SHA-256 of the primary key |
| `run_id` | `string` | - | `EXPERIMENT_METADATA` | Durable pipeline run identifier |
| `scenario_run_id` | `string` | - | `EXPERIMENT_METADATA` | One isolated scenario repetition |
| `scenario_id` | `string` | - | `EXPERIMENT_METADATA` | Scenario definition name |
| `timestamp_utc` | `timestamp_us` | UTC | `DERIVED` | Collector alignment timestamp |
| `source_timestamp_utc` | `timestamp_us` | UTC | `MEASURED_OAI` | Exporter source timestamp |
| `source_monotonic_ns` | `int64` | ns | `MEASURED_OAI` | CLOCK_MONOTONIC at source |
| `gnb_id` | `string` | - | `EXPERIMENT_METADATA` | Configured OAI gNB identifier |
| `ue_id` | `string` | - | `MEASURED_OAI` | UE tunnel/OAI UE identifier |
| `slice_id` | `int32` | - | `EXPERIMENT_METADATA` | Configured S-NSSAI SST mapping |
| `slice_type` | `string` | - | `EXPERIMENT_METADATA` | eMBB, URLLC, or mMTC |
| `ue_interface` | `string` | - | `MEASURED_OAI` | Linux interface created by OAI nrUE |
| `data_source` | `string` | - | `MEASURED_OAI` | Explicit measured source identifier |
| `collector_version` | `string` | - | `EXPERIMENT_METADATA` | Real-data collector version |
| `git_commit` | `string` | - | `EXPERIMENT_METADATA` | DeepORAN repository commit or tree digest |
| `oai_commit` | `string` | - | `MEASURED_OAI` | OAI RAN git commit |
| `exporter_boot_id` | `string` | - | `MEASURED_OAI` | Host boot identifier |
| `exporter_sequence` | `int64` | - | `MEASURED_OAI` | Monotonic exporter snapshot sequence |
| `gnb_pid` | `int64` | - | `MEASURED_OAI` | nr-softmodem process ID |
| `ue_pid` | `int64` | - | `MEASURED_OAI` | nr-uesoftmodem process ID, if mapped |
| `rx_bytes_total` | `int64` | bytes | `MEASURED_OAI` | UE tunnel RX byte counter |
| `tx_bytes_total` | `int64` | bytes | `MEASURED_OAI` | UE tunnel TX byte counter |
| `rx_packets_total` | `int64` | packets | `MEASURED_OAI` | UE tunnel RX packet counter |
| `tx_packets_total` | `int64` | packets | `MEASURED_OAI` | UE tunnel TX packet counter |
| `rx_dropped_total` | `int64` | packets | `MEASURED_OAI` | UE tunnel RX drops |
| `tx_dropped_total` | `int64` | packets | `MEASURED_OAI` | UE tunnel TX drops |
| `rx_mbps` | `float64` | Mbit/s | `DERIVED` | Counter delta divided by elapsed source time |
| `tx_mbps` | `float64` | Mbit/s | `DERIVED` | Counter delta divided by elapsed source time |
| `packet_loss_ratio` | `float64` | fraction | `DERIVED` | Drop delta divided by packet delta plus drops |
| `rtt_avg_ms` | `float64` | ms | `MEASURED_TRAFFIC` | ping average RTT through UE interface |
| `rtt_p95_ms` | `float64` | ms | `MEASURED_TRAFFIC` | ping RTT p95 through UE interface |
| `jitter_ms` | `float64` | ms | `MEASURED_TRAFFIC` | iperf UDP jitter |
| `iperf_mbps` | `float64` | Mbit/s | `MEASURED_TRAFFIC` | iperf receiver throughput |
| `traffic_loss_ratio` | `float64` | fraction | `MEASURED_TRAFFIC` | iperf/ping measured loss |
| `traffic_source_timestamp_utc` | `timestamp_us` | UTC | `MEASURED_TRAFFIC` | Traffic probe completion time |
| `rnti` | `string` | - | `MEASURED_OAI` | OAI MAC RNTI |
| `cu_ue_id` | `int64` | - | `MEASURED_OAI` | OAI CU UE identifier |
| `in_sync` | `bool` | - | `MEASURED_OAI` | OAI MAC synchronization state |
| `rsrp_dbm` | `float64` | dBm | `MEASURED_OAI` | OAI average RSRP |
| `dl_bler` | `float64` | fraction | `MEASURED_OAI` | OAI downlink BLER |
| `ul_bler` | `float64` | fraction | `MEASURED_OAI` | OAI uplink BLER |
| `dl_mcs` | `int64` | index | `MEASURED_OAI` | OAI downlink MCS |
| `ul_mcs` | `int64` | index | `MEASURED_OAI` | OAI uplink MCS |
| `ul_nprb` | `int64` | PRB | `MEASURED_OAI` | OAI uplink scheduled NPRB |
| `mac_tx_bytes_total` | `int64` | bytes | `MEASURED_OAI` | OAI MAC TX bytes |
| `mac_rx_bytes_total` | `int64` | bytes | `MEASURED_OAI` | OAI MAC RX bytes |
| `mac_source_timestamp_utc` | `timestamp_us` | UTC | `MEASURED_OAI` | Latest parsed OAI MAC stats time |
| `prb_utilization` | `float64` | fraction | `DERIVED` | Measured UL NPRB divided by configured total PRBs |
| `throughput_mbps` | `float64` | Mbit/s | `DERIVED` | Preferred fresh iperf value, otherwise counter rate |
| `latency_ms` | `float64` | ms | `DERIVED` | Fresh measured RTT |
| `sla_violation` | `bool` | - | `DERIVED` | Configured SLA predicate evaluated on measured KPIs |
| `fault_active` | `bool` | - | `EXPERIMENT_METADATA` | Controlled fault is active |
| `fault_type` | `string` | - | `EXPERIMENT_METADATA` | Controlled fault type, if any |
| `control_epoch` | `int64` | - | `MEASURED_CONTROLLER` | Latest acknowledged closed-loop epoch |
| `control_action_id` | `string` | - | `MEASURED_CONTROLLER` | Latest acknowledged action identifier |
| `control_acknowledged` | `bool` | - | `MEASURED_CONTROLLER` | RIC/E2 acknowledgement was observed |
| `control_active` | `bool` | - | `MEASURED_CONTROLLER` | Acknowledged E2 action is currently applied |
| `control_effect_observed` | `bool` | - | `MEASURED_CONTROLLER` | Applied state was returned by an E2 indication |
| `control_restored` | `bool` | - | `MEASURED_CONTROLLER` | Baseline restoration was returned by an E2 indication |
| `control_service_model` | `string` | - | `MEASURED_CONTROLLER` | Controller service-model name |
| `control_service_model_id` | `int64` | - | `MEASURED_CONTROLLER` | Controller RAN function/service-model ID |
| `control_e2_node_count` | `int64` | nodes | `MEASURED_CONTROLLER` | E2 nodes visible to the control xApp |
| `control_data_source` | `string` | - | `MEASURED_CONTROLLER` | Explicit real controller evidence source |
| `control_source_timestamp_utc` | `timestamp_us` | UTC | `MEASURED_CONTROLLER` | Controller evidence timestamp |
