"""
SPiDR 재현 — 장면 복원 (reconstruct.py)

y = H x 의 역문제. x는 픽셀 점유(반사율) ≥ 0.
- 기본: 비음(nonnegative) 최소제곱 (scipy.optimize.nnls) — 추가 의존성 없음.
- 희소 장면: LASSO(positive) — sklearn 있으면.
- Tikhonov(L2): lsqr damp — 빠르고 안정.
열 정규화로 조건수를 개선하고 복원 후 스케일을 되돌린다.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import nnls


def _normalize_cols(H):
    norm = np.linalg.norm(H, axis=0)
    norm = np.where(norm < 1e-12, 1.0, norm)
    return H / norm, norm


def reconstruct_nnls(H, y):
    Hn, norm = _normalize_cols(H)
    x, _ = nnls(Hn, y)
    return x / norm


def reconstruct_tikhonov(H, y, lam=1e-2):
    from scipy.sparse.linalg import lsqr
    Hn, norm = _normalize_cols(H)
    x = lsqr(Hn, y, damp=lam)[0]
    return np.clip(x, 0, None) / norm


def reconstruct_lasso(H, y, alpha=1e-3):
    from sklearn.linear_model import Lasso  # 선택 의존성
    Hn, norm = _normalize_cols(H)
    m = Lasso(alpha=alpha, positive=True, max_iter=50000).fit(Hn, y)
    return m.coef_ / norm


def localize_error_cm(x_hat, x_true, x_positions_cm):
    """단일/다중 타깃: 추정 피크 위치와 참 위치의 거리(cm)."""
    if x_true.sum() == 0 or x_hat.sum() == 0:
        return np.nan
    i_hat = int(np.argmax(x_hat))
    i_true = int(np.argmax(x_true))
    return abs(x_positions_cm[i_hat] - x_positions_cm[i_true])


def image_corr(x_hat, x_true):
    """복원-정답 정규화 상관(SSIM 대용, 의존성 회피). 1에 가까울수록 좋음."""
    a = x_hat - x_hat.mean()
    b = x_true - x_true.mean()
    d = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / d) if d > 1e-12 else 0.0


def detect_recall(x_hat, x_true, tol=1):
    """다중 타깃 검출 recall: x_hat 상위 k개 피크가 참 타깃을 ±tol픽셀 내로 잡은 비율.
    (단일/다중 타깃 모두에 일관적. 단일이면 '톱-1이 참 위치 근처인가'.)"""
    true_idx = np.nonzero(x_true)[0]
    k = len(true_idx)
    if k == 0 or x_hat.sum() == 0:
        return np.nan
    top = np.argsort(x_hat)[-k:]
    matched = sum(any(abs(int(t) - int(h)) <= tol for h in top) for t in true_idx)
    return matched / k
