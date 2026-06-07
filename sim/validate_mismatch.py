"""
SPiDR 재현 — G0 검증: 모델 불일치 스윕 (validate_mismatch.py)

★인버스 크라임 금지★ — 데이터는 '섭동 물리'로 만들고 복원은 '공칭 H'로만 한다.
여기서는 불일치 정도를 단계적으로 키우며(스윕) 정확도가 어떻게 무너지는지 본다.

핵심 메시지(Codex 리뷰):
- 작은 불일치(튜브 전달을 잘 보정한 경우) → 복원기·접근법이 동작함을 검증(게이트).
- 큰 불일치(튜브 음향 미보정) → 정확도 붕괴 → ∴ 실제론 'H를 측정'해야 함을 증명.
"""
from __future__ import annotations
import numpy as np
from forward_model import Config, scene_grid, received_signal, build_H
from reconstruct import reconstruct_nnls, localize_error_cm, image_corr, detect_recall
from design_stencil import optimize, coherence


def add_noise(y, snr_db, rng):
    p = np.mean(y ** 2)
    return y + rng.normal(0, np.sqrt(p / 10 ** (snr_db / 10)), size=y.shape)


def perturbed_data(pixels, x_true, pos, L, cfg, rng, amp, phase, c_rel, pos_jit):
    N = len(pos)
    tube_gain = (1 + rng.uniform(-amp, amp, N)) * np.exp(1j * rng.uniform(-phase, phase, N))
    c_true = cfg.c * (1 + rng.uniform(-c_rel, c_rel))
    pos_j = pos + rng.normal(0, pos_jit, pos.shape)
    y = None
    for p_idx in np.nonzero(x_true)[0]:
        s = x_true[p_idx] * received_signal(pixels[p_idx], pos_j, L, cfg,
                                            tube_gain=tube_gain, c=c_true)
        y = s if y is None else y + s
    return y


LEVELS = [   # (이름, 진폭지터, 위상지터, 음속상대오차, 위치지터 m)
    ("잡음만(0)",        0.00, np.deg2rad(0),   0.000, 0.0),
    ("작음(보정됨,~10°)", 0.10, np.deg2rad(10),  0.001, 0.3e-3),
    ("중간(~30°)",       0.20, np.deg2rad(30),  0.003, 0.7e-3),
    ("큼(미보정,180°)",  0.30, np.deg2rad(180), 0.005, 1.5e-3),
]


def run(n_trials=60, n_targets=1, snr_db=30, pitch_cm=2, n_tubes=20, seed=7):
    cfg = Config(n_tubes=n_tubes)
    rng = np.random.default_rng(seed)
    x_cm = np.arange(-10, 10 + 1e-9, pitch_cm)
    pix, _ = scene_grid(x_cm, [10])
    N = len(pix)

    pos, L, mx, mn = optimize(cfg, pix, n_iter=300, seed=1)   # 스텐실 최적화
    H_nom = build_H(pix, pos, L, cfg)                          # 공칭 H(복원 전용)
    print(f"[설정] tubes={n_tubes} freqs={len(cfg.freqs)} N={N} H={H_nom.shape} "
          f"pitch={pitch_cm}cm SNR={snr_db}dB targets={n_targets}")
    print(f"[H 품질] 최적화 후 최대결맞음={mx:.3f} 평균={mn:.3f} 조건수={np.linalg.cond(H_nom):.1f}\n")

    print(f"{'불일치 수준':<18}{'타깃검출 recall':>15}{'상관중앙':>10}")
    results = {}
    for name, amp, phase, c_rel, pjit in LEVELS:
        recs, corrs = [], []
        for _ in range(n_trials):
            x_true = np.zeros(N)
            x_true[rng.choice(N, n_targets, replace=False)] = 1.0
            y = perturbed_data(pix, x_true, pos, L, cfg, rng, amp, phase, c_rel, pjit)
            y = add_noise(y, snr_db, rng)
            x_hat = reconstruct_nnls(H_nom, y)
            recs.append(detect_recall(x_hat, x_true))
            corrs.append(image_corr(x_hat, x_true))
        recall = np.nanmean(recs)
        results[name] = recall
        print(f"{name:<18}{recall*100:>13.0f}% {np.nanmedian(corrs):>10.2f}")

    # 인버스 크라임 참고
    ic = []
    for _ in range(n_trials):
        x_true = np.zeros(N); x_true[rng.choice(N, n_targets, replace=False)] = 1.0
        x_ic = reconstruct_nnls(H_nom, add_noise(H_nom @ x_true, snr_db, rng))
        ic.append(detect_recall(x_ic, x_true))
    print(f"{'인버스크라임(참고)':<18}{np.nanmean(ic)*100:>13.0f}% {'~1.0':>10}  (자기복원=무의미)")

    small = results["작음(보정됨,~10°)"]
    gate = "PASS" if small >= 0.8 else "FAIL"
    print(f"\nG0 게이트(작은 불일치 타깃검출 recall ≥80%): {gate} ({small*100:.0f}%)")
    print("결론: 큰 불일치에서 정확도 붕괴 → 실제 재현은 '실측 H'가 필수(05 가이드).")
    return results


if __name__ == "__main__":
    print("══════ 단일 타깃 ══════")
    run(n_targets=1)
    print("\n══════ 이중 타깃(2cm 분해) ══════")
    run(n_targets=2)
