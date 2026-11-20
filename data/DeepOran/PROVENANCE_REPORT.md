# Provenance Report

Generated: `2026-09-02T12:10:19.713748+00:00`

## Identity

- Run ID: `real-oai-20260901T194849Z-64c30592`
- Repository: `tree-sha256:ab64d11e7b9689eaaaa06cc51230e7295b6909bc32ea1d91910a1d80de85b7cc`
- Configuration: `f0ad63bfafb14eb1ae8c03919bed01fcbce6b2b7ad209b53bec32a44c7891edc`
- OAI commit(s): `["707aab3af1e072c6747e598a0b88beaabae1d903"]`

## Counts

- Raw snapshots: `27,873,317`
- Aligned/final observations: `13,000,000`
- Rows by source: `{"OAI_GNB_JOURNAL_AND_NRUE_TUNNEL_COUNTERS": 13000000}`
- Rows by scenario: `{"backhaul_delay": 986384, "backhaul_loss": 926323, "embb_heavy": 1343532, "mixed": 1328206, "mmtc_burst": 1911211, "normal": 1272288, "off_peak": 1136477, "peak": 1318649, "prb_contention": 1302861, "urllc_heavy": 1474069}`
- Rows by slice: `{"1": 3445417, "2": 4427844, "3": 5126739}`

## Transformation

Raw exporter snapshots are retained as JSONL. Counter deltas are aligned with fresh traffic and controller evidence, normalized to the explicit Arrow schema, and written transactionally to partitioned Parquet. No interpolation or generated-value substitution is permitted.
