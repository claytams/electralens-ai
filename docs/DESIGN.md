# 설계 노트 & 변경 내역 (Design notes & changelog)

이 문서는 ElectraLens AI를 단일 파일 프로토타입에서 GitHub 배포용 패키지로 정비하면서
수행한 종합 코드 리뷰 결과와 그에 따른 보완 내용을 정리한다.

## 아키텍처

단일 책임을 가진 모듈로 분리해 UI 없이도 분석 로직을 import·테스트할 수 있다.

```
입력(파일/클립보드/샘플/드래그) 
  → features.image_features   색·에지·밝기 특징
  → analyzer.classify         파일명 키워드 → 특징 임계값으로 모드 결정
  → analyzer._safety/_circuit/_scope/_label/_general
       · 데모 샘플(sample_*)  → 큐레이트된 정합 수치
       · 실제 사진            → 측정 가능한 값만 측정, 나머지는 체크리스트
  → AnalysisResult(통일 스키마) → app.render_result / report 스크린샷
```

핵심 원칙: **측정할 수 없는 값은 지어내지 않는다.** `AnalysisResult.measured` 플래그와
`confidence` 텍스트로 측정/추정/체크리스트를 구분한다. `score`는 모든 모드에서
"주의 점수(0 안심 ~ 100 즉시 점검)"로 의미를 통일했다.

## 종합 리뷰에서 고친 항목

### 버그 / 정확성
- **[Critical] NumPy 미설치 폴백이 NameError로 크래시.** `image_features`의 폴백 경로가
  import되지 않은 `ImageStat`을 호출했다. `features.py`에서 `ImageStat`을 명시 import하고,
  밝기/명암 비율을 히스토그램으로 실제 계산하도록 폴백을 재작성. 폴백도 정상 경로와
  **동일한 키 집합**을 반환하게 통일(이전엔 3개 키만 반환해 분류가 항상 'safety'로 붕괴).
- **[정직성] 실제 사진이 샘플로 오판되던 문제.** `_is_sample`이 토큰 부분 매칭이라
  파일명에 'circuit'/'scope'가 든 실제 사진이 하드코딩된 샘플 수치(21.2 mA, 280 Hz)로
  표시됐다. 앱이 생성하는 `sample_*` 접두사를 요구하도록 수정.
- **[정직성] 주파수 폴백.** 추정 실패 시 임의 상수(2.2 div→약 455 Hz)를 측정값처럼
  표시하던 로직 제거. 실제 사진은 화면 대비 상대값을 제시하고, 격자가 확실히 검출될
  때만 div/주파수를 보너스로 추가.

### 전기전자 도메인
- **멀티탭 "여유 -0.1 A" 부호 오류.** 16 − 3500/220 = **+0.1 A**(정격 이내, 한계 근접).
  `margin = STRIP_RATING_A - current`로 계산해 `+0.1 A`로 표기하고 severity를 danger→warning으로
  조정(과경고 대신 정확한 "한계 근접").
- **스코프 매직넘버(64.0/36.0) 제거.** 격자선을 검출(`waveform.detect_grid`)해 실제
  px/div를 구하거나, 검출 실패 시 div 표기를 쓰지 않고 화면 대비 상대값만 제시.
- **샘플 스코프 라벨 360 Hz → 280 Hz.** 그려진 파형(10 div 위 2.8주기, 1 ms/div)과 정합.
- **LED 회로 그림/해석 불일치.** 해석이 'LED 1개 기준'이므로 샘플 그림도 LED 1개로 맞춤.

### 보안 / 견고성
- 신뢰 불가 이미지 디코딩 폭탄 방어: `Image.MAX_IMAGE_PIXELS = 50 MP` 설정 + 로드 시
  `DecompressionBombError` 처리.
- 예외 메시지에서 전체 경로 노출 제거(파일명만 표시).
- `build_exe.ps1`의 하드코딩된 개발자 절대경로 제거(`ELECTRALENS_PYTHON` 환경변수로
  재정의, 기본 `python`). 빌드 의존성 명시(PyInstaller/Pillow/NumPy).
- 런타임 폴더 최종 폴백을 임의 cwd → 사용자 홈(`~/.electralens`)으로 변경.

### 코드 품질
- 1209줄 단일 파일을 모듈 패키지로 분리(`models/features/waveform/analyzer/ocr/samples/probe/report/app/cli`).
- 죽은 코드 제거: 점-기반 `smart_probe`, 미사용 `self.probe_point`, `wrap_text`,
  게이지의 의미 없는 `create_rounded_rectangle` 별칭 할당.
- 중복 제거: severity→color 매핑(3곳) → `models.severity_color`, mode 라벨(2곳) →
  `models.MODE_LABELS`, 스크린샷 우측 패널/폰트 로딩 → `report._draw_result_panel`/`_load_fonts`.
- 매직넘버를 `models.py`의 명명 상수로 추출.
- pytest 단위 테스트 추가(특징/폴백/분류/샘플 불변식/격자/OCR 파서) + GitHub Actions CI.

## 새 기능: 정직한 실이미지 분석
- **격자 검출 기반 스코프 측정**: 화면 ROI를 찾고 격자선 피크 간격으로 px/div를 구해
  주기/Vpp를 div 단위로 산출(임의 상수 없음). 신뢰도 낮으면 상대값으로 후퇴.
- **선택적 OCR**: Tesseract가 있으면 어댑터 라벨에서 V·A·W를 읽어 P=VI 계산, 멀티탭은
  W 값을 합산해 전류를 계산. 없으면 자동으로 체크리스트로 폴백.

## 한계
완전한 부품 인식/회로 Netlist 추출은 범위 밖이다. 향후 개선 시 로컬 OCR 정확도 향상,
다중 트레이스 스코프 처리, 카메라 실시간 입력 등을 고려할 수 있다.
