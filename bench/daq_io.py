"""
SPiDR 재현 — PC측 DAQ 입출력 (daq_io.py)

ESP32-S3 펌웨어(spidr_bench.ino)와 시리얼로 통신. 'M'/'B' 명령을 보내고
BEGIN..F..END 프로토콜을 파싱해 (N_FREQ, WIN_SAMPLES) 배열로 반환.
→ 한 측정 = 픽셀/장면 하나의 수신 시계열(주파수 이어붙이면 H의 한 열 형식).

의존성: pyserial (pip install pyserial). 하드웨어 없으면 capture_sim()로 대체.
"""
from __future__ import annotations
import numpy as np


def open_port(port, baud=2_000_000, timeout=2.0):
    import serial  # pyserial
    return serial.Serial(port, baud, timeout=timeout)


def capture(ser, blank=False):
    """ESP32에서 1회 측정 → (N_FREQ, WIN_SAMPLES) float 배열(평균 제거 전 원시 ADC)."""
    ser.reset_input_buffer()
    ser.write(b'B' if blank else b'M')
    rows, cur = [], None
    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if not line:
            continue
        if line.startswith('BEGIN'):
            _, nf, nw, fs, _tag = line.split()[:5]
            nf, nw = int(nf), int(nw)
            continue
        if line.startswith('F'):
            cur = []
            continue
        if line == 'END':
            break
        if cur is not None and line[0].isdigit():
            cur.extend(int(v) for v in line.split(','))
            rows.append(cur); cur = None
    arr = np.array(rows, dtype=float)        # (N_FREQ, WIN_SAMPLES)
    return arr


def capture_avg(ser, n_avg=32, blank=False):
    """동기 평균(SNR 향상). 톤버스트 코히어런트 평균."""
    acc = None
    for _ in range(n_avg):
        a = capture(ser, blank=blank)
        acc = a if acc is None else acc + a
    return acc / n_avg


def to_column(arr):
    """ (N_FREQ, WIN) → H 열 형식(주파수 이어붙인 1D). 평균(DC) 제거."""
    a = arr - arr.mean(axis=1, keepdims=True)
    return a.reshape(-1)


# ── 하드웨어 없이 파이프라인 점검용 시뮬 캡처 ──────────────────
def capture_sim(pixel_idx, pixels, src, L, cfg, rng, blank=False):
    """forward_model로 가짜 측정 생성(하드웨어 전 측정 파이프라인 테스트용)."""
    from sys import path; path.insert(0, '../sim')
    from forward_model import received_signal
    if blank:
        sig = np.zeros_like(received_signal(pixels[0], src, L, cfg))
    else:
        sig = received_signal(pixels[pixel_idx], src, L, cfg)
    sig = sig + rng.normal(0, sig.std() * 0.02 + 1e-9, sig.shape)
    return sig
