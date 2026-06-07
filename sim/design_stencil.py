"""
SPiDR 재현 — 스텐실 설계(선택 트랙) (design_stencil.py)

Owlet 공개코드(ref_optimizeStencil.m)와 같은 정신: 무작위 후보를 다수 생성해
'코드 다양성'이 가장 좋은 것을 고른다. 여기선 목적함수를 채널행렬 H의
열 상호결맞음(coherence) 최소화로 둔다(압축센싱 복원에 유리).

출력 {pos, lengths} 는 3D 모델(04 문서)의 튜브 출구 좌표·길이 파라미터가 된다.
※ 한계(Codex): 다수의 (길이, 게인) 조합이 비슷한 H를 줄 수 있어(λ-모듈로 비식별성),
   coherence 단독 최적화는 근사다. 실제론 실측 H가 본체.
"""
from __future__ import annotations
import numpy as np
from forward_model import Config, scene_grid, build_H


def coherence(H):
    Hn = H / (np.linalg.norm(H, axis=0, keepdims=True) + 1e-12)
    G = np.abs(Hn.T @ Hn)
    np.fill_diagonal(G, 0.0)
    return G.max(), G.mean()


def random_stencil(cfg: Config, rng):
    ang = rng.uniform(0, 2 * np.pi, cfg.n_tubes)
    h = rng.uniform(0.1, 0.9, cfg.n_tubes) * cfg.stencil_height
    pos = np.stack([cfg.stencil_radius * np.cos(ang),
                    cfg.stencil_radius * np.sin(ang), h], axis=1)
    lengths = rng.uniform(cfg.l_min, cfg.l_max, cfg.n_tubes)
    return pos, lengths


def optimize(cfg: Config, pixels, n_iter=300, seed=0, verbose=False):
    rng = np.random.default_rng(seed)
    best = None
    best_score = np.inf
    for i in range(n_iter):
        pos, L = random_stencil(cfg, rng)
        mx, mn = coherence(build_H(pixels, pos, L, cfg))
        score = mx + 0.5 * mn          # 최악 + 평균 결맞음
        if score < best_score:
            best_score, best = score, (pos, L, mx, mn)
            if verbose:
                print(f"  iter {i:4d}  max-coh={mx:.3f} mean-coh={mn:.3f}")
    return best  # (pos, lengths, max_coh, mean_coh)


if __name__ == "__main__":
    cfg = Config(n_tubes=20)
    pix, _ = scene_grid(np.arange(-10, 11, 2), [10])
    pos, L, mx, mn = optimize(cfg, pix, n_iter=300, verbose=True)
    print(f"\n최적 스텐실: max-coh={mx:.3f} mean-coh={mn:.3f}")
    print("튜브 길이(mm):", np.round(L * 1000, 1))
    np.savez("stencil_design.npz", pos=pos, lengths=L,
             n_tubes=cfg.n_tubes, radius=cfg.stencil_radius, height=cfg.stencil_height)
    print("→ stencil_design.npz 저장 (04 3D설계가 이 파라미터를 사용)")
