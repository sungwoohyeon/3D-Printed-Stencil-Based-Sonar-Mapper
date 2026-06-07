"""
SPiDR 재현 — 실측 채널행렬 H 측정 (measure_H.py)  ★이 재현의 심장★

프로토콜:
1. 물체를 모두 치우고 배경(blank) 측정 → 직접누설·고정에코 기록.
2. 작은 점반사체(예: Ø6mm 금속구/막대)를 픽셀 격자의 각 위치로 옮기며 측정.
3. 각 측정에서 배경을 빼고(클러터 제거) 동기 평균(SNR↑) → H의 그 열.
4. 모든 픽셀 완료 → H_measured.npz 저장. 이후 reconstruct로 실제 장면 복원.

처음엔 1D(가로 한 줄)로, 손+자+3D프린트 지그로 충분(모터 불필요).
실행: python measure_H.py --port COM5      (하드웨어)
      python measure_H.py --sim            (하드웨어 없이 파이프라인 점검)
"""
from __future__ import annotations
import argparse, sys, numpy as np
sys.path.insert(0, '../sim')
from forward_model import Config, make_stencil, scene_grid
import daq_io


def grid_1d(pitch_cm=2, depth_cm=10):
    x_cm = np.arange(-10, 10 + 1e-9, pitch_cm)
    pix, _ = scene_grid(x_cm, [depth_cm])
    return pix, x_cm


def measure_real(port, pix, x_cm, depth_cm, n_avg=32):
    ser = daq_io.open_port(port)
    input("물체를 모두 치우고 Enter (배경 측정)...")
    blank = daq_io.capture_avg(ser, n_avg, blank=False)   # 배경(빈 장면)
    cols = []
    for i, xc in enumerate(x_cm):
        input(f"[{i+1}/{len(x_cm)}] 점반사체를 (x={xc:+.0f}cm, depth={depth_cm}cm)에 놓고 Enter...")
        meas = daq_io.capture_avg(ser, n_avg)
        col = daq_io.to_column(meas - blank)              # ★배경차감★
        cols.append(col)
    H = np.stack(cols, axis=1)
    return H


def measure_sim(pix, x_cm):
    cfg = Config(); rng = np.random.default_rng(0)
    src, L = make_stencil(cfg)
    cols = [daq_io.capture_sim(i, pix, src, L, cfg, rng) for i in range(len(pix))]
    return np.stack(cols, axis=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port"); ap.add_argument("--sim", action="store_true")
    ap.add_argument("--pitch", type=float, default=2); ap.add_argument("--depth", type=float, default=10)
    ap.add_argument("--navg", type=int, default=32)
    a = ap.parse_args()
    pix, x_cm = grid_1d(a.pitch, a.depth)
    if a.sim:
        H = measure_sim(pix, x_cm)
        print(f"[SIM] H_measured shape={H.shape}")
    else:
        if not a.port: sys.exit("--port COMx 필요 (또는 --sim)")
        H = measure_real(a.port, pix, x_cm, a.depth, a.navg)
    np.savez("H_measured.npz", H=H, x_cm=x_cm, depth_cm=a.depth, pitch=a.pitch)
    # 품질 지표
    Hn = H / (np.linalg.norm(H, axis=0, keepdims=True) + 1e-12)
    G = np.abs(Hn.T @ Hn); np.fill_diagonal(G, 0)
    print(f"저장 H_measured.npz | 최대 열결맞음={G.max():.3f} 조건수={np.linalg.cond(H):.1f}")
    print("→ 이제 reconstruct로 실제 장면(여러 물체) 복원 가능 (06 가이드 G3).")
