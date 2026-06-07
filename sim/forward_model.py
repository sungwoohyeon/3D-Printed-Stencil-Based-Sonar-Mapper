"""
SPiDR 재현 — 시간영역 포워드 모델 (forward_model.py)

핵심(Codex 리뷰 반영):
- H는 단일주파수 위상이 아니라 **시간영역 신호**다. 10주기 톤버스트를 쏘고 ToF로 거리를 안다.
- 신호 경로는 **왕복**: 스피커→스텐실 출구(n)→픽셀(p)→반사→마이크. 진폭 ∝ 1/(r_np·r_pm).
- 근거리 구면 전파 + 마이크 좌표 포함.
- H의 한 열 = "픽셀 p에 단위 반사체가 있을 때 마이크가 받는, 게이트·샘플된 시계열"을
  5개 주파수에 대해 이어붙인 것. → M = (게이트 샘플수) × (주파수수).

이 모델은 '공칭(nominal)' 물리다. 실제와는 다르므로(튜브 음향·지향성 등) G0 검증은
반드시 validate_mismatch.py 로 '모델 불일치' 하에서 한다(인버스 크라임 금지).
"""
from __future__ import annotations
import numpy as np
from dataclasses import dataclass

C_AIR = 343.0  # 음속 m/s @ ~20°C


@dataclass
class Config:
    c: float = C_AIR
    fs: float = 200_000.0                       # ADC 샘플레이트 (Hz)
    freqs: tuple = (38e3, 39e3, 40e3, 41e3, 42e3)
    cycles: int = 10                            # 톤버스트 주기수
    n_tubes: int = 16                           # 스텐실 튜브(이차음원) 수
    stencil_radius: float = 0.014               # 출구 링 반경 14mm (Ø28 스텐실)
    stencil_height: float = 0.02
    l_min: float = 0.0
    l_max: float = 0.08                         # 튜브 길이 범위(위상 다양성)
    mic: tuple = (0.02, 0.0, 0.0)               # 마이크 좌표 (스텐실 중심서 +x 2cm)
    t_win: float = 1.2e-3                       # 레인지게이트 윈도우 길이 (s)
    seed: int = 1234


def tone_burst(t, f, cycles):
    """Hann 윈도우 톤버스트. t<0 또는 t>T 구간은 0."""
    T = cycles / f
    inb = (t >= 0) & (t <= T)
    tt = np.clip(t, 0.0, T)
    w = np.where(inb, 0.5 * (1 - np.cos(2 * np.pi * tt / T)), 0.0)
    return w * np.sin(2 * np.pi * f * t)


def make_stencil(cfg: Config, rng=None):
    """튜브 출구 위치(N,3)와 길이(N,)를 만든다. 길이는 위상 코드의 원천."""
    rng = np.random.default_rng(cfg.seed) if rng is None else rng
    ang = np.linspace(0, 2 * np.pi, cfg.n_tubes, endpoint=False)
    pos = np.stack([cfg.stencil_radius * np.cos(ang),
                    cfg.stencil_radius * np.sin(ang),
                    np.full(cfg.n_tubes, cfg.stencil_height)], axis=1)
    lengths = rng.uniform(cfg.l_min, cfg.l_max, cfg.n_tubes)
    return pos, lengths


def scene_grid(x_cm, z_cm):
    """장면 픽셀 격자(가로 x, 깊이 z; y=0 평면). 반환: pix(P,3) m, shape."""
    X, Z = np.meshgrid(np.asarray(x_cm) / 100.0, np.asarray(z_cm) / 100.0, indexing='xy')
    pix = np.stack([X.ravel(), np.zeros(X.size), Z.ravel()], axis=1)
    return pix, X.shape


def received_signal(pixel, src_pos, lengths, cfg: Config,
                    freqs=None, tube_gain=None, c=None, mic=None):
    """단위 반사체가 pixel(3,)에 있을 때 마이크 수신 시계열(주파수 이어붙임).
    tube_gain: 각 튜브의 복소 전달(진폭+위상). None이면 1(공칭).
    """
    c = cfg.c if c is None else c
    mic = np.asarray(cfg.mic) if mic is None else np.asarray(mic)
    freqs = cfg.freqs if freqs is None else freqs
    src_pos = np.asarray(src_pos)
    N = len(src_pos)
    if tube_gain is None:
        tube_gain = np.ones(N, dtype=complex)
    nsamp = int(round(cfg.t_win * cfg.fs))
    tvec = np.arange(nsamp) / cfg.fs
    r_np = np.linalg.norm(src_pos - pixel, axis=1)     # 출구→픽셀
    r_pm = float(np.linalg.norm(pixel - mic))          # 픽셀→마이크
    amp = np.abs(tube_gain) / (r_np * r_pm)            # 왕복 1/(r_np·r_pm)
    base_tau = (lengths + r_np + r_pm) / c             # (N,)
    out = []
    for f in freqs:
        T = cfg.cycles / f
        ph_delay = np.angle(tube_gain) / (2 * np.pi * f)     # 복소위상→협대역 지연
        targ = tvec[None, :] - (base_tau + ph_delay)[:, None]  # (N, nsamp)
        inb = (targ >= 0) & (targ <= T)
        tt = np.clip(targ, 0.0, T)
        w = np.where(inb, 0.5 * (1 - np.cos(2 * np.pi * tt / T)), 0.0)
        burst = w * np.sin(2 * np.pi * f * targ)
        out.append((amp[:, None] * burst).sum(axis=0))
    return np.concatenate(out)


def build_H(pixels, src_pos, lengths, cfg: Config, **kw):
    """채널행렬 H (M×N). 열 = 픽셀별 수신 시계열."""
    cols = [received_signal(p, src_pos, lengths, cfg, **kw) for p in pixels]
    return np.stack(cols, axis=1)


if __name__ == "__main__":
    cfg = Config()
    src, L = make_stencil(cfg)
    pix, shape = scene_grid(range(-10, 11, 2), [10])
    H = build_H(pix, src, L, cfg)
    print(f"tubes={cfg.n_tubes} freqs={len(cfg.freqs)} pixels={len(pix)}")
    print(f"H shape = {H.shape}  (M rows = {int(cfg.t_win*cfg.fs)} samp x {len(cfg.freqs)} freq)")
    # 열 상호결맞음(coherence): 낮을수록 좋은 코드
    Hn = H / (np.linalg.norm(H, axis=0, keepdims=True) + 1e-12)
    G = np.abs(Hn.T @ Hn)
    np.fill_diagonal(G, 0)
    print(f"max column coherence = {G.max():.3f}  (낮을수록 분해 잘 됨)")
