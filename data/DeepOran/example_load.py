"""Load the DeepORAN genuine OAI dataset on Kaggle."""
from pathlib import Path

import pyarrow.dataset as ds


ROOT = Path("/kaggle/input/deeporan-agent-6g-o-ran-network-slice-dataset")
SPLIT_FILES = [
    ROOT / "deeporan_oai_train.parquet",
    ROOT / "deeporan_oai_validation.parquet",
    ROOT / "deeporan_oai_test.parquet",
]
DATA = ds.dataset(SPLIT_FILES, format="parquet")

print(f"rows={DATA.count_rows():,}")
urllc = DATA.to_table(
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
print(urllc.slice(0, 5).to_pandas())
