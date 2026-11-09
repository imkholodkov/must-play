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
    """Выборка Steam с простой целью: больше 100 положительных отзывов."""
    frame = pd.read_csv(SAMPLE_CSV, dtype=str, keep_default_na=False)
    frame["target"] = (pd.to_numeric(frame["positive"]) > 100).astype(int)
    return frame


@pytest.fixture
def model_bytes(sample):
    """Маленькая обученная модель в виде pkl-байтов — как файл, который загружают в API."""
    pipe = Pipeline([("features", SteamFeatures(top_tags=10)), ("model", LogisticRegression(max_iter=500))])
    pipe.fit(sample.drop(columns="target"), sample["target"])
    buf = io.BytesIO()
    joblib.dump(pipe, buf)
    return buf.getvalue()


@pytest.fixture
def ml_client(tmp_path, monkeypatch):
    """Клиент без БД: модели хранятся во временной папке теста."""
    monkeypatch.setattr(ml_api, "registry", ModelRegistry(tmp_path))
    return TestClient(app)


@pytest.fixture
def loaded_client(ml_client, model_bytes):
    """Клиент с уже загруженной моделью hit."""
    upload(ml_client, model_bytes)
    return ml_client


def upload(client, content, filename="hit.pkl"):
    return client.post("/ml/upload-model", data={"model": "hit"}, files={"file": (filename, content)})


def csv_file(frame):
    return {"file": ("games.csv", io.BytesIO(frame.to_csv(index=False).encode()), "text/csv")}


class TestUploadModel:
    def test_predict_without_model_returns_503(self, ml_client):
        response = ml_client.post("/ml/predict", json={"model": "hit", "records": [{"price": "1"}]})

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "model_not_loaded"

    def test_rejects_garbage(self, ml_client):
        assert upload(ml_client, b"not a pickle").status_code == 400
        assert upload(ml_client, b"x", filename="model.txt").status_code == 400

    def test_accepts_pipeline(self, ml_client, model_bytes):
        response = upload(ml_client, model_bytes)

        assert response.json() == {"status": "success", "model": "hit", "estimator": "Pipeline"}


class TestPredict:
    def test_records(self, loaded_client, sample):
        records = sample.drop(columns="target").head(3).to_dict(orient="records")

        body = loaded_client.post("/ml/predict", json={"model": "hit", "records": records}).json()

        assert len(body) == 3
        assert all(0 <= r["hit_probability"] <= 1 and r["hit_predicted"] in (0, 1) for r in body)


class TestPredictFromCsv:
    def test_with_target_returns_roc_auc(self, loaded_client, sample):
        body = loaded_client.post("/ml/predict-from-csv", data={"model": "hit"}, files=csv_file(sample)).json()

        assert body["rows"] == len(sample)
        assert 0.5 < body["roc_auc"] <= 1
        assert {"hit_probability", "hit_predicted", "target", "name"} <= set(body["data"][0])

    def test_preprocessed_features(self, loaded_client, model_bytes, sample):
        features = joblib.load(io.BytesIO(model_bytes)).named_steps["features"].transform(sample)

        body = loaded_client.post("/ml/predict-from-csv", data={"model": "hit"}, files=csv_file(features)).json()

        assert body["roc_auc"] is None
        assert body["rows"] == len(sample)

    def test_bad_target_column(self, loaded_client, sample):
        sample["target"] = "yes"

        response = loaded_client.post("/ml/predict-from-csv", data={"model": "hit"}, files=csv_file(sample))

        assert response.status_code == 400
