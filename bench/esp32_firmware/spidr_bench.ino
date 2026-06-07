/*
 * SPiDR 재현 — ESP32-S3 벤치 펌웨어 (spidr_bench.ino)
 * ---------------------------------------------------------------
 * 역할: PC에서 'M' 명령을 받으면, 5개 주파수(38~42kHz) 각각에 대해
 *       10주기 톤버스트를 송출(LEDC PWM)하고, 그 직후 마이크 신호를
 *       ADC 연속(DMA) 모드로 캡처해 시리얼로 스트림한다.
 *       → PC측 daq_io.py 가 이 데이터를 받아 H 측정/복원에 쓴다.
 *
 * 보드: ESP32-S3 (Arduino-ESP32 core 3.x 필요 — analogContinuous API).
 * 배선: TX_PIN → [SN74LVC2G04 버퍼] → 40kHz 스피커
 *       마이크 → [OPA344 프리앰프 + 1.65V 바이어스] → RX_ADC_PIN
 *
 * ⚠️ G1 실측 튜닝 항목(코드 내 TODO):
 *   - SAMPLE_HZ 가 실제로 연속 유지되는지(드롭/지터) 검증. 안 되면 낮추거나 Pico로.
 *   - 버스트-캡처 동기 지연(START_DELAY_US) 보정.
 *   - ADC 채널/감쇠(11dB=0~3.3V) 및 프리앰프 게인으로 클리핑 없이 풀스케일 근접.
 */

#include "Arduino.h"
#include "esp_adc/adc_continuous.h"   // core 3.x

// ---------------- 사용자 설정 ----------------
const int   TX_PIN       = 4;          // 스피커 구동(버퍼 입력)
const int   RX_ADC_CH    = ADC_CHANNEL_3; // GPIO4=CH3 등 보드별 확인. 마이크 입력.
const int   LEDC_CH      = 0;
const float FREQS[]      = {38000, 39000, 40000, 41000, 42000};
const int   N_FREQ       = 5;
const int   BURST_CYCLES = 10;
const int   WIN_SAMPLES  = 240;        // 주파수당 캡처 샘플수(≈1.2ms @200kHz)
const uint32_t SAMPLE_HZ = 200000;     // 목표 샘플레이트 (>80kHz 필수)
const uint32_t START_DELAY_US = 30;    // 버스트 송출~캡처 시작 보정

// ---------------- ADC 연속 핸들 ----------------
adc_continuous_handle_t adc_handle = NULL;
uint8_t adc_buf[1024];

void adc_init() {
  adc_continuous_handle_cfg_t hcfg = { .max_store_buf_size = 2048, .conv_frame_size = 256 };
  adc_continuous_new_handle(&hcfg, &adc_handle);
  adc_digi_pattern_config_t pat = {
    .atten = ADC_ATTEN_DB_12, .channel = RX_ADC_CH, .unit = ADC_UNIT_1, .bit_width = ADC_BITWIDTH_12 };
  adc_continuous_config_t ccfg = {
    .pattern_num = 1, .adc_pattern = &pat,
    .sample_freq_hz = SAMPLE_HZ, .conv_mode = ADC_CONV_SINGLE_UNIT_1,
    .format = ADC_DIGI_OUTPUT_FORMAT_TYPE2 };
  adc_continuous_config(adc_handle, &ccfg);
}

void emit_and_capture(float freq, uint16_t* out, int n) {
  // 1) 톤버스트 송출 (LEDC, 50% 듀티)
  ledcChangeFrequency(LEDC_CH, (uint32_t)freq, 8);
  ledcWrite(LEDC_CH, 128);                       // on
  delayMicroseconds((uint32_t)(1e6 * BURST_CYCLES / freq));
  ledcWrite(LEDC_CH, 0);                          // off
  delayMicroseconds(START_DELAY_US);

  // 2) ADC 연속 캡처
  adc_continuous_start(adc_handle);
  int got = 0; uint32_t rd;
  while (got < n) {
    if (adc_continuous_read(adc_handle, adc_buf, sizeof(adc_buf), &rd, 50) == ESP_OK) {
      for (int i = 0; i < rd && got < n; i += SOC_ADC_DIGI_RESULT_BYTES) {
        adc_digi_output_data_t* p = (adc_digi_output_data_t*)&adc_buf[i];
        out[got++] = p->type2.data;
      }
    }
  }
  adc_continuous_stop(adc_handle);
}

uint16_t window[WIN_SAMPLES];

void setup() {
  Serial.begin(2000000);
  ledcSetup(LEDC_CH, 40000, 8);
  ledcAttachPin(TX_PIN, LEDC_CH);
  ledcWrite(LEDC_CH, 0);
  adc_init();
  Serial.println("# SPiDR bench ready. Send 'M' to measure, 'B' for blank.");
}

void measure(bool blank) {
  Serial.printf("BEGIN %d %d %lu %s\n", N_FREQ, WIN_SAMPLES, SAMPLE_HZ, blank ? "BLANK" : "MEAS");
  for (int f = 0; f < N_FREQ; f++) {
    if (blank) {                    // 빈 장면(배경) — 송출 없이 캡처만? → 동일 송출, 물체 없음
      emit_and_capture(FREQS[f], window, WIN_SAMPLES);
    } else {
      emit_and_capture(FREQS[f], window, WIN_SAMPLES);
    }
    Serial.printf("F %.0f\n", FREQS[f]);
    for (int i = 0; i < WIN_SAMPLES; i++) { Serial.print(window[i]); Serial.print(i==WIN_SAMPLES-1?'\n':','); }
    delay(2);
  }
  Serial.println("END");
}

void loop() {
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == 'M') measure(false);
    else if (cmd == 'B') measure(true);  // 배경(물체 제거 상태에서 호출)
  }
}
