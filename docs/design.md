# Merge design and upstream inspection

## 조사 기준 (2026-09-21)

GitHub release API에서 [Agave tag 39](https://github.com/blobject/agave/releases/tag/39),
[Sarasa v1.0.41](https://github.com/be5invis/Sarasa-Gothic/releases/tag/v1.0.41)의 실제 asset을 확인하고 다운로드하여 fontTools로 검사했다.
웹 검색의 이전 README snapshot보다 실제 API/파일을 기준으로 버전을 고정했다.

| 속성 | Agave Regular | Agave Bold | Sarasa Mono K |
| --- | --- | --- | --- |
| UPM | 2048 | 2048 | 1000 |
| ASCII advance | 1024 | 1024 | 500 |
| glyph 수 | 2487 | 743 | weight별 56682 |
| 한글 완성형 | 없음 | 없음 | 11172 |
| outline | hinted glyf | hinted glyf | unhinted glyf asset 선택 |
| OpenType layout | GDEF | GDEF | GDEF/GSUB/GPOS |
| 수직 metrics | 없음 | vhea/vmtx | vhea/vmtx/VORG |

Sarasa의 `가`는 Regular에서 advance=1000, bounds=(95,-77,929,827).
Agave는 cap height=1280, x-height=1024, hhea/typo ascender=1536, descender=-512, lineGap=0이다.
이 차이를 고려해 한글 초기 scale=.85, y=-60을 preset으로 선택했다.

## 선택

Agave TTFont를 base로 열고 한글 outline만 append한다. FontForge는 필요하지 않다.
[fontTools의 범용 Merger](https://fonttools.readthedocs.io/en/latest/merge.html)는 중복 cmap 처리와 cross-font metrics/layout 병합을 수행한다.
이 프로젝트는 Agave Latin과 hinting 보존이 우선이므로 필요한 문자만 명시적으로 추가하는 편이 작고 검증하기 쉽다.

작업은 acquisition/config → merge/validation → preview/docs → regression/end-to-end 검증 순서로 수행했다.
각 범위는 `builder/sources.py`+`sources/`, `builder/merge.py`, `builder/preview.py`+`preview/`+문서, `tests/`이며 단일 실행자가 순차 구현했다.

## 테이블 처리

| 테이블 | 처리 |
| --- | --- |
| cmap | 기존 매핑 유지. Unicode format 4/12에 선택한 한글만 추가. Mac cmap 등은 유지 |
| glyph order | 기존 모든 glyph ID 고정, `krXXXX`를 뒤에 추가 |
| glyf/loca | 원본 glyf byte block을 보관했다가 구조 계산 후 그대로 복원. loca는 새 배열로 직렬화 |
| hmtx | 원본 튜플 그대로. 추가 한글 advance=2048, lsb=변환 후 xMin |
| head | UPM/스타일 기준 유지, 전체 bbox/checksum/loca 형식은 출력에 맞게 계산 |
| hhea | Agave ascent/descent/lineGap 유지, advanceWidthMax/sidebearing extrema/hmetric 개수 갱신 |
| OS/2 | typo metrics/x-height/cap-height/평균 ASCII 폭 유지. Unicode/codepage 범위, lastChar, 굵기, Win clipping bounds 갱신 |
| maxp | glyph/point/contour/composite maxima 계산. 기존 hint VM resource maxima 유지 |
| name | 고유 family/PS/full/typographic/WWS 이름과 weight, 파생 버전/입력 fingerprint, 양쪽 저작권/라이선스 기록 |
| fpgm/prep/cvt/gasp | Agave 원본 bytes 유지; donor 것은 가져오지 않음 |
| GDEF/GSUB/GPOS/kern | Agave에 있으면 보존; donor layout은 가져오지 않음 |
| post | Agave fixed-pitch 분류/밑줄 설정 유지, glyph 이름 추가 |
| vhea/vmtx | Bold의 기존 glyph metrics 유지. 추가 glyph 수만큼 vmtx 채움, aggregate extrema 계산. 한국어 세로쓰기 지원을 뜻하지 않음 |
| TTFA/FFTM | base의 hinting provenance 유지. 전체 병합 결과를 새로 hint했다는 뜻이 아님 |
| DSIG | 존재하면 무효가 되므로 제거 |

개별 글리프와 전역 metrics의 차이는 [OpenType glyf](https://learn.microsoft.com/en-us/typography/opentype/spec/glyf),
[hhea](https://learn.microsoft.com/en-us/typography/opentype/spec/hhea), [OS/2](https://learn.microsoft.com/en-us/typography/opentype/spec/os2)를 기준으로 처리했다.
Agave glyph를 다시 compile하면서 좌표나 bytecode가 바뀌지 않게 `recalcBBoxes=False`로 저장한다.
전체 maxp/hhea 등은 그 전에 명시적으로 계산하고, 원본 glyf byte blocks를 복원한다.
출력을 다시 연 다음 모든 원본 raw glyph block과 hint/layout 테이블의 bytes를 비교한다.

## 한글 outline과 폭

```text
s = Agave_UPM / donor_UPM * config.scale
dx = (2 * Agave_ASCII_advance - donor_glyph_advance * s) / 2 + x_offset
x' = s * x + dx
y' = s * y + y_offset
advance = 2 * Agave_ASCII_advance
```

비등폭 source도 각 glyph의 advance box를 중앙 정렬한다. bbox 중심으로 글자마다 이동하면 원본 optical spacing이 깨지므로 사용하지 않는다.
큰 transform이 셀 밖으로 나가면 경고하고, TrueType 좌표 범위를 넘으면 실패한다.

한글 composite는 [DecomposingRecordingPen](https://fonttools.readthedocs.io/en/latest/pens/recordingPen.html)으로 재귀적으로 풀어 glyph-ID/component/hint 참조 충돌을 제거한다.
CFF는 [Cu2QuPen](https://fonttools.readthedocs.io/en/latest/pens/cu2quPen.html)으로 quadratic으로 근사하고 TrueType winding으로 바꾼다.
한글에만 적용되는 과정이며, 원본 Agave는 이 pen pipeline에 들어가지 않는다.
가변 font는 모든 축을 static instance로 고정하며 Noto는 실제 wght=400/700을 검증했다.

## Coverage 및 layout 경계

필수: U+AC00–D7A3 현대 완성형 11172자, U+3131–3163 현대 호환 자모 51자.
추가: U+3164–318E 중 donor가 실제 제공하는 문자.
Sarasa/Han/Noto/D2는 합계 11266자, Pretendard는 11225자다.

독립 conjoining Jamo·옛한글·tone mark를 무작정 가져오면 GSUB ljmo/vjmo/tjmo나 GPOS positioning 없이 잘못 렌더링될 수 있다.
따라서 해당 cmap/layout은 반입하지 않는다. 현대 NFD는 HarfBuzz의 Hangul normalization으로 대응되는 완성형 glyph가 선택되는 것을 전체 음절에 대해 검증했다.
모든 플랫폼의 구형 shaper 동작을 보장하지 않으며 NFC 사용이 가장 예측 가능하다.

## 확인한 위험과 선택한 제한

- Agave와 donor의 hint VM state/CVT를 합치지 않는다. 한글은 unhinted이며 전체 폰트 재힌팅은 하지 않는다.
- font family는 source별 고유하고 RFN을 피한다. 비교 UI의 원본 이름은 출처 설명이다.
- local 설정은 미확인 라이선스에 자동 다운로드를 허용하지 않으며 출력에 LOCAL ONLY 표시를 한다.
- 미확인 local donor의 OS/2 fsType 임베딩 제한 비트는 출력에서도 유지한다. 비트 값 자체를 이용허락으로 해석하지 않는다.
- 다운로드 cache는 URL로 구분하고 SHA-256 검사한다. 해제 cache는 archive hash로 구분한다.
- 모든 출력은 source별 임시 경로에서 검증한 후 반영한다. manifest의 해시 검사로 중단된 교체를 preview에 노출하지 않는다.
- generic layout merge, font plugin architecture, 자동 설치/배포는 만들지 않는다.
