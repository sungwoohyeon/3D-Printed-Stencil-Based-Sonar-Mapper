# 3D-Printed Stencil-Based Sonar Mapper

> An **independent, in-progress reproduction** of the core idea behind **SPiDR** —
> generating a 2D cross-sectional depth map from a *single* 40 kHz speaker + a *single*
> microphone + a passive 3D-printed acoustic "stencil", by solving the linear inverse
> problem `y = H·x`.
>
> 단일 40 kHz 스피커 1개 + 마이크 1개 + 3D프린팅 패시브 "스텐실"로 2D 단면 깊이맵을
> 만드는 SPiDR 논문의 **독립 재현 프로젝트**(진행 중).

> ⚠️ **Not affiliated with the original SPiDR authors.** This repository contains only
> *our own* analysis, simulation code, bench/firmware code, and *original* 3D cap
> designs. The original paper, its figures, and the authors' published STL / MATLAB /
> datasets are **not** redistributed here — see
> [Reference material (not included)](#reference-material-not-included).

---

## What is SPiDR? (원리)

A single omnidirectional speaker emits the same signal everywhere, so it carries no
spatial information. SPiDR caps the speaker with a 3D-printed **stencil** containing
internal tubes of *different lengths*; each tube exit behaves like a secondary source
with a unique delay and attenuation. Their interference projects a **unique signal code
at every point in space**, so the scene can be recovered by solving `y = H·x`
(`H` = channel matrix, `x` = per-pixel occupancy, `y` = received mic signal).

Original paper: Yang Bai, Nakul Garg, Nirupam Roy, *SPiDR: Microstructure-Assisted
Vision for Ubiquitous Tiny Robots*, MobiSys 2022
([DOI 10.1145/3498361.3539775](https://dl.acm.org/doi/10.1145/3498361.3539775)) ·
CACM 69(3), 2026 ([DOI 10.1145/3772712](https://dl.acm.org/doi/10.1145/3772712)).
The paper is licensed CC BY-NC-SA 4.0.

## ★ Key insight of this reproduction (재현의 핵심)

The usable channel matrix **`H` must be measured empirically** — by scanning a point
reflector across a grid — rather than computed from a closed-form model. The analytic
`H` mismatches reality (time-domain round trip, near-field geometry, tube acoustics).
Our **G0** simulation demonstrates exactly this: reconstruction stays robust under small
model mismatch but collapses under large mismatch, so an empirically measured `H` is the
heart of the project.

## Repository layout

| Path | Contents |
|------|----------|
| `00–07_*.md` | Korean project docs: overview, paper analysis, parts/BOM, simulation design, stencil 3D-print guide, bench + empirical-`H` guide, staged build guide, references |
| `sim/` | Time-domain forward model (`forward_model.py`), reconstruction (`reconstruct.py` — NNLS / Tikhonov / LASSO), stencil design search (`design_stencil.py`), and the **G0** model-mismatch gate (`validate_mismatch.py`) |
| `bench/` | ESP32-S3 firmware (`esp32_firmware/spidr_bench.ino`), DAQ I/O (`daq_io.py`), and the empirical-`H` scanning protocol (`measure_H.py`) |
| `models/` | Our **original** Fusion 360 build scripts and exported caps: `SPiDR_phasecap_v2` (variable path-length phase cap) and `SPiDR_stencil_parametric` (equal-length radial control cap) |

## Status

- ✅ **G0 — Simulation**: PASS. Time-domain `H`, reconstruction, and model-mismatch
  validation (inverse crime avoided).
- ⏳ **G1–G3 — Hardware**: electronics bring-up → 1D empirical-`H` → coarse 2D map.
  Pending parts assembly.

Honest expectation: 1D / coarse-2D results are realistic; paper-grade 1 cm resolution
and SSIM > 80% is a stretch goal.

## Quick start (simulation)

```bash
pip install numpy scipy        # scikit-learn optional (for LASSO)
cd sim
python design_stencil.py       # stencil optimization -> stencil_design.npz
python validate_mismatch.py    # the G0 gate
```

## Reference material (not included)

To respect copyright, the following are **not** stored in this repository. Please obtain
them from their original sources:

- **Stencil STL files** (helical; authored in *meters* — scale ×1000 for millimeters):
  [Nakul22/Spidr_Mobisys22](https://github.com/Nakul22/Spidr_Mobisys22)
- **Stencil-optimization MATLAB and `cardoid_used.mat`**:
  [Nakul22/Owlet_Mobisys21](https://github.com/Nakul22/Owlet_Mobisys21)
- **Paper text and figures**: via the DOIs above (CC BY-NC-SA 4.0).

## License

- **Our code, documentation, and original 3D designs** are released under the
  [MIT License](LICENSE) © 2026 sungwoohyeon.
- The reproduced *concept* derives from the SPiDR paper (CC BY-NC-SA 4.0); please cite
  the original authors. This project is non-commercial and unaffiliated.

## Acknowledgements

Original SPiDR and Owlet research by Yang Bai, Nakul Garg, and Nirupam Roy
(University of Maryland, iCoSMoS Lab).
