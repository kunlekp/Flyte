"""Customer segmentation with a from-scratch K-Means (NumPy)."""

import numpy as np


class KMeans:
    """K-Means with k-means++ initialisation and several restarts."""

    def __init__(self, k=4, n_init=6, max_iter=100, tol=1e-5, seed=7):
        self.k = k
        self.n_init = n_init
        self.max_iter = max_iter
        self.tol = tol
        self.rng = np.random.default_rng(seed)
        self.centroids_ = None
        self.labels_ = None
        self.inertia_ = None

    def _init_centroids(self, X):
        centroids = [X[self.rng.integers(len(X))]]
        for _ in range(1, self.k):
            d2 = np.min(((X[:, None, :] - np.array(centroids)[None]) ** 2).sum(-1), axis=1)
            probs = d2 / d2.sum() if d2.sum() > 0 else np.full(len(X), 1 / len(X))
            centroids.append(X[self.rng.choice(len(X), p=probs)])
        return np.array(centroids)

    def _run_once(self, X):
        centroids = self._init_centroids(X)
        for _ in range(self.max_iter):
            distances = ((X[:, None, :] - centroids[None]) ** 2).sum(-1)
            labels = distances.argmin(1)
            new = np.array([X[labels == j].mean(0) if (labels == j).any() else centroids[j] for j in range(self.k)])
            shift = np.abs(new - centroids).max()
            centroids = new
            if shift < self.tol:
                break
        inertia = float(((X - centroids[labels]) ** 2).sum())
        return centroids, labels, inertia

    def fit(self, X):
        X = np.asarray(X, dtype=float)
        if len(X) < self.k:
            raise ValueError("Need at least k samples to cluster.")
        best = None
        for _ in range(self.n_init):
            result = self._run_once(X)
            if best is None or result[2] < best[2]:
                best = result
        self.centroids_, self.labels_, self.inertia_ = best
        return self

    def silhouette(self, X, sample=600):
        """Mean silhouette score on a sample (−1..1, higher = better separated)."""
        X = np.asarray(X, dtype=float)
        idx = self.rng.choice(len(X), size=min(sample, len(X)), replace=False)
        Xs, ls = X[idx], self.labels_[idx]
        d = np.sqrt(((Xs[:, None] - Xs[None]) ** 2).sum(-1))
        scores = []
        for i in range(len(Xs)):
            same = ls == ls[i]
            if same.sum() <= 1:
                continue
            a = d[i, same].sum() / (same.sum() - 1)
            b = min(d[i, ls == j].mean() for j in set(ls) if j != ls[i] and (ls == j).any())
            scores.append((b - a) / max(a, b))
        return float(np.mean(scores)) if scores else 0.0


class PassengerSegmenter:
    """Builds per-passenger features, clusters them and names the clusters."""

    FEATURES = ["trips", "spend", "lead_days", "premium_share"]

    def __init__(self, k=4, seed=7):
        self.k = k
        self.seed = seed

    def segment(self, features_df):
        """`features_df` index=passport, columns=FEATURES (+ 'age')."""
        df = features_df.dropna(subset=self.FEATURES).copy()
        if len(df) < self.k * 3:
            return {"segments": [], "silhouette": None, "n": int(len(df))}
        raw = df[self.FEATURES].to_numpy(dtype=float)
        raw[:, 1] = np.log1p(raw[:, 1])                    # spend is heavy-tailed
        mu, sd = raw.mean(0), raw.std(0)
        sd[sd == 0] = 1
        X = (raw - mu) / sd
        model = KMeans(self.k, seed=self.seed).fit(X)
        df["segment"] = model.labels_

        names = self._name_clusters(df)
        total_spend = df["spend"].sum() or 1
        segments = []
        for label, group in df.groupby("segment"):
            name, description = names[label]
            segments.append({
                "id": int(label),
                "name": name,
                "description": description,
                "size": int(len(group)),
                "share_of_passengers": round(len(group) / len(df), 4),
                "share_of_revenue": round(group["spend"].sum() / total_spend, 4),
                "avg_trips": round(float(group["trips"].mean()), 2),
                "avg_spend": round(float(group["spend"].mean()), 0),
                "avg_lead_days": round(float(group["lead_days"].mean()), 1),
                "premium_share": round(float(group["premium_share"].mean()), 3),
                "avg_age": round(float(group["age"].mean()), 1) if "age" in group else None,
            })
        segments.sort(key=lambda s: s["share_of_revenue"], reverse=True)
        return {"segments": segments, "silhouette": round(model.silhouette(X), 3), "n": int(len(df)),
                "labels": dict(zip(df.index, df["segment"].map(lambda l: names[l][0])))}

    @staticmethod
    def _name_clusters(df):
        """Name clusters by their most distinctive centroid feature."""
        centroids = df.groupby("segment")[PassengerSegmenter.FEATURES].mean()
        names, remaining = {}, list(centroids.index)

        def take(column, name, description, highest=True):
            if not remaining:
                return
            pool = centroids.loc[remaining, column]
            label = pool.idxmax() if highest else pool.idxmin()
            names[label] = (name, description)
            remaining.remove(label)

        take("premium_share", "Premium jet-setters", "Mostly Business and First. Highest spend per trip.")
        take("trips", "Frequent commuters", "Fly often on the same routes, usually booked a week or less out.")
        take("lead_days", "Early planners", "Book weeks ahead and catch the lowest fares.")
        for label in remaining:
            names[label] = ("Occasional flyers", "One or two trips. The biggest group to grow.")
        return names
