#!/usr/bin/env python3
"""
Model training/serving consistency tests.

Run:  python -m unittest tests.test_models -v
"""

import os
import tempfile
import unittest
from unittest import mock

import joblib

from tests.support import event

from controller.features import HOST_FEATURES, extract_host_features
from controller.log_anomaly import MODEL_PATH as LOG_MODEL_PATH, LogAnomalyModel, normalize
from controller.triage_model import FALLBACK_SCORE, TriageModel


class HostFeatureTests(unittest.TestCase):
    def test_fixed_length_for_any_event_shape(self):
        for ev in ({"host": "h"}, event("node1"), {"host": "h", "ifaces": {"a": {}, "b": {"mtu": 9000}, "c": {}}}):
            self.assertEqual(extract_host_features(ev).shape, (len(HOST_FEATURES),))

    def test_incompatible_artifact_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "old.joblib")
            joblib.dump({"booster": object(), "features": ["something_else"]}, path)
            m = TriageModel(model_path=path)
            self.assertEqual(m.status, "incompatible")
            self.assertEqual(m.predict(event("node1"))["priority_score"], FALLBACK_SCORE)

    def test_train_then_serve_same_features(self):
        import controller.model.common as common
        import controller.model.triage_model_training as tmt

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(common, "MODELS_DIR", d), \
                mock.patch.object(tmt, "MODELS_DIR", d), \
                mock.patch.object(tmt, "MODEL_PATH", os.path.join(d, "xgb_model.joblib")):
            summary = tmt.train_model()
            self.assertIn("synthetic", summary)
            m = TriageModel(model_path=os.path.join(d, "xgb_model.joblib"))
            self.assertEqual(m.status, "loaded")
            fault = m.predict(event("node1", errout=200, dmesg="eth0: TX errors detected"))["priority_score"]
            normal = m.predict(event("node1", dmesg="Normal boot messages"))["priority_score"]
            self.assertGreater(fault, 0.5)
            self.assertLess(normal, 0.5)
            self.assertTrue(os.path.exists(os.path.join(d, "xgb_model.card.json")))


class LogAnomalyTests(unittest.TestCase):
    def test_normalize_masks_numbers_and_hex(self):
        self.assertEqual(normalize("CE sym 23, at 0x0b85eee0, mask 0x05"), "ce sym <num> , at <hex> , mask <hex>")

    def test_disabled_or_missing_model_returns_none(self):
        self.assertIsNone(LogAnomalyModel(path="none").score("kernel panic"))
        self.assertIsNone(LogAnomalyModel(path=os.path.join(tempfile.gettempdir(), "nope.joblib")).score("x"))

    @unittest.skipUnless(os.path.exists(LOG_MODEL_PATH), "BGL model not trained")
    def test_trained_bgl_model_ranks_alert_above_benign(self):
        m = LogAnomalyModel(path=LOG_MODEL_PATH)
        self.assertEqual(m.status, "loaded")
        alert = m.score("data TLB error interrupt")["max_score"]
        benign = m.score("instruction cache parity error corrected")["max_score"]
        self.assertGreater(alert, benign)
        out = m.score("line one\nline two")
        self.assertEqual(out["label"], "model-generated")
        self.assertEqual(len(out["lines"]), 2)


class ModelsEndpointTests(unittest.TestCase):
    def test_models_endpoint(self):
        from fastapi.testclient import TestClient

        import main

        body = TestClient(main.app).get("/api/models").json()
        self.assertEqual(set(body), {"host_triage", "log_anomaly", "oran_fault"})
        self.assertFalse(body["oran_fault"]["used_at_runtime"])


if __name__ == "__main__":
    unittest.main()
