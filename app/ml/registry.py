"""Хранилище ML-моделей: загрузка pkl с диска, приём новой модели, прогноз."""

import io
from pathlib import Path

import joblib
import pandas as pd

from app.core.errors import AppError

MODELS_DIR = Path("models")
MODEL_NAMES = ("hit", "press")


class ModelNotLoadedError(AppError):
    status_code = 503
    code = "model_not_loaded"


class ModelRegistry:
    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = models_dir
        self._models: dict[str, object] = {}

    def get(self, name: str):
        if name not in self._models:
            path = self.models_dir / f"{name}.pkl"
            if not path.exists():
                raise ModelNotLoadedError(
                    f"Модель {name} не загружена: загрузите её через POST /ml/upload-model", {"model": name}
                )
            self._models[name] = joblib.load(path)
        return self._models[name]

    def upload(self, name: str, content: bytes) -> object:
        """Проверить, что файл — обученный классификатор с predict_proba, и сохранить его.

        Внимание: pkl исполняет код при загрузке, поэтому принимайте модели только из доверенного источника.
        """
        try:
            model = joblib.load(io.BytesIO(content))
        except Exception as exc:
            raise AppError("Файл не читается как модель pkl", str(exc)) from exc
        if not hasattr(model, "predict_proba"):
            raise AppError("В файле нет классификатора с методом predict_proba")
        self.models_dir.mkdir(exist_ok=True)
        (self.models_dir / f"{name}.pkl").write_bytes(content)
        self._models[name] = model
        return model

    def predict(self, name: str, frame: pd.DataFrame) -> pd.DataFrame:
        model = self.get(name)
        try:
            probability = model.predict_proba(frame)[:, 1]
        except (ValueError, KeyError) as exc:
            raise AppError(
                "Данные не подходят модели: нужны сырые колонки steam_games.csv или признаки", str(exc)
            ) from exc
        result = frame.copy()
        result[f"{name}_probability"] = probability.round(4)
        result[f"{name}_predicted"] = (probability >= 0.5).astype(int)
        return result


registry = ModelRegistry()
