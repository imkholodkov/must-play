import io

import joblib
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.api import ml as ml_api
from app.main import app
from app.ml.features import SteamFeatures
from app.ml.registry import ModelRegistry
from tests.conftest import SAMPLE_CSV


@pytest.fixture
def sample():
    frame = pd.read_csv(SAMPLE_CSV, dtype=str, keep_default_na=False)
    frame["target"] = (pd.to_numeric(frame["positive"]) > 100).astype(int)
    return frame


@pytest.fixture
def model_bytes(sample):
    pipe = Pipeline([("features", SteamFeatures(top_tags=10)), ("model", LogisticRegression(max_iter=500))])
    pipe.fit(sample.drop(columns="target"), sample["target"])
    buf = io.BytesIO()
    joblib.dump(pipe, buf)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ml_api, "registry", ModelRegistry(tmp_path))
    return TestClient(app)


def upload(client, content, filename="hit.pkl"):
    return client.post("/ml/upload-model", data={"model": "hit"}, files={"file": (filename, content)})


def csv_file(frame):
    return {"file": ("games.csv", io.BytesIO(frame.to_csv(index=False).encode()), "text/csv")}


def test_predict_without_model_returns_503(client):
    response = client.post("/ml/predict", json={"model": "hit", "records": [{"price": "1"}]})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_not_loaded"


def test_upload_rejects_garbage(client):
    assert upload(client, b"not a pickle").status_code == 400
    assert upload(client, b"x", filename="model.txt").status_code == 400


def test_upload_and_predict_records(client, model_bytes, sample):
    response = upload(client, model_bytes)
    assert response.json() == {"status": "success", "model": "hit", "estimator": "Pipeline"}

    records = sample.drop(columns="target").head(3).to_dict(orient="records")
    body = client.post("/ml/predict", json={"model": "hit", "records": records}).json()

    assert len(body) == 3
    assert all(0 <= r["hit_probability"] <= 1 and r["hit_predicted"] in (0, 1) for r in body)


def test_predict_from_csv_with_target_returns_roc_auc(client, model_bytes, sample):
    upload(client, model_bytes)

    body = client.post("/ml/predict-from-csv", data={"model": "hit"}, files=csv_file(sample)).json()

    assert body["rows"] == len(sample)
    assert 0.5 < body["roc_auc"] <= 1
    assert {"hit_probability", "hit_predicted", "target", "name"} <= set(body["data"][0])


def test_predict_from_preprocessed_csv(client, model_bytes, sample):
    upload(client, model_bytes)
    features = joblib.load(io.BytesIO(model_bytes)).named_steps["features"].transform(sample)

    body = client.post("/ml/predict-from-csv", data={"model": "hit"}, files=csv_file(features)).json()

    assert body["roc_auc"] is None
    assert body["rows"] == len(sample)


def test_bad_target_column(client, model_bytes, sample):
    upload(client, model_bytes)
    sample["target"] = "yes"

    response = client.post("/ml/predict-from-csv", data={"model": "hit"}, files=csv_file(sample))

    assert response.status_code == 400
