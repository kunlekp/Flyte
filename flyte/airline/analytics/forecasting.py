"""Time-series forecasting for daily booking demand (NumPy only)."""

from abc import ABC, abstractmethod

import numpy as np


class Forecaster(ABC):
    """Interface every forecasting model implements."""

    @abstractmethod
    def fit(self, values, start_dow=0):
        ...

    @abstractmethod
    def predict(self, horizon):
        """Return (mean, lower, upper) arrays."""

    def backtest(self, values, start_dow=0, holdout=14):
        """Fit on all but the last `holdout` points and score them (MAPE / MAE)."""
        values = np.asarray(values, dtype=float)
        if len(values) < holdout * 2:
            return {"mape": None, "mae": None, "holdout": holdout}
        model = type(self)(**self.params())
        model.fit(values[:-holdout], start_dow)
        predicted, _, _ = model.predict(holdout)
        actual = values[-holdout:]
        mask = actual > 0
        mape = float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask]))) if mask.any() else None
        mae = float(np.mean(np.abs(actual - predicted)))
        return {"mape": mape, "mae": mae, "holdout": holdout,
                "actual": actual.round(1).tolist(), "predicted": predicted.round(1).tolist()}

    def params(self):
        return {}


class SeasonalTrendForecaster(Forecaster):
    """Linear trend + day-of-week seasonality, fit with ridge-regularised least
    squares. Prediction interval from residual spread (z=1.28 → ~80%)."""

    def __init__(self, ridge=1.0, z=1.28):
        self.ridge = ridge
        self.z = z
        self.coef_ = None
        self.sigma_ = 0.0
        self.n_ = 0
        self.start_dow_ = 0

    def params(self):
        return {"ridge": self.ridge, "z": self.z}

    def _design(self, t, start_dow):
        dow = (start_dow + t) % 7
        columns = [np.ones_like(t, dtype=float), t / max(self.n_, 1)]
        for day in range(1, 7):                      # Monday is the baseline
            columns.append((dow == day).astype(float))
        return np.column_stack(columns)

    def fit(self, values, start_dow=0):
        y = np.asarray(values, dtype=float)
        self.n_ = len(y)
        self.start_dow_ = start_dow
        t = np.arange(self.n_)
        X = self._design(t, start_dow)
        penalty = self.ridge * np.eye(X.shape[1])
        penalty[0, 0] = 0                            # don't shrink the intercept
        self.coef_ = np.linalg.solve(X.T @ X + penalty, X.T @ y)
        residuals = y - X @ self.coef_
        dof = max(self.n_ - X.shape[1], 1)
        self.sigma_ = float(np.sqrt((residuals ** 2).sum() / dof))
        return self

    def fitted(self):
        t = np.arange(self.n_)
        return self._design(t, self.start_dow_) @ self.coef_

    def predict(self, horizon):
        t = np.arange(self.n_, self.n_ + horizon)
        mean = np.clip(self._design(t, self.start_dow_) @ self.coef_, 0, None)
        # Uncertainty widens slowly with distance from the training window.
        spread = self.z * self.sigma_ * np.sqrt(1 + (np.arange(1, horizon + 1) / max(self.n_, 1)))
        return mean, np.clip(mean - spread, 0, None), mean + spread

    @property
    def weekly_pattern(self):
        """Effect of each weekday vs Monday, in bookings/day."""
        if self.coef_ is None:
            return []
        return [0.0] + [float(c) for c in self.coef_[2:]]

    @property
    def trend_per_day(self):
        return float(self.coef_[1] / max(self.n_, 1)) if self.coef_ is not None else 0.0
