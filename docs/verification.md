# 검증 기록

실행일: 2026-09-21. 환경: macOS, Python 3.12.14, fontTools 4.65.0, py7zr 1.1.3,
uharfbuzz 0.56.1. 의존성은 `uv.lock`에 고정했다.

## 실제 실행 결과

| 확인 | 결과 |
| --- | --- |
| 공식 source 최초 다운로드 및 archive 해제 | GitHub release 7z/ZIP, direct URL 모두 성공 |
| `./build.sh` | source 생략 시 Sarasa Regular/Bold 성공 |
| `./build.sh --all --offline` | 5 source × 2 weight 모두 성공, exit 0 |
| `python -m builder validate --all --offline` | 10개 저장된 TTF 모두 통과 |
| `python -m unittest discover -s tests -v` | **15 tests passed**, 6.165초 |
| `node tests/preview_ui.cjs` | 5 source/10 weight, 성공·실패 로딩 모의, 크기/굵기/필터/기준선/공통문장 동작, TTF 참조 확인 통과 |
| Sarasa 캐시 재빌드 재현성 | 실행 전후 Regular/Bold TTF SHA-256 각각 동일 |
| Python compileall 및 sh syntax | 통과 |

각 `build/<source>/build.json`에 config snapshot, 다운로드 원본/출력의 전체 SHA-256,
glyph 수, metrics, 개별 검증 결과가 저장되어 있다. 생성된 preview는 5 source 모두 포함한다.

| source | 각 weight 한글 문자 수 | Regular SHA-256 앞 16자리 | Bold SHA-256 앞 16자리 |
| --- | ---: | --- | --- |
| sarasa-mono-k | 11266 | e78b0bbdf36ac260 | c7f4c93df2df2054 |
| source-han-sans-kr | 11266 | 5546e51020b7c10f | b52f310502d54fb6 |
| noto-sans-kr | 11266 | 17954e5d77ed2cb3 | e655a437ed2dfcbc |
| pretendard | 11225 | 4852293ff194ae03 | 11ba5512144c1d4e |
| d2coding | 11266 | 836f4fb1ad0c46f8 | 0e3927bf0c8ada17 |

## Agave 보존 및 한글 검증

- Regular **2487/2487**, Bold **743/743** 원본 glyph의 raw glyf block이 정확히 같다(패딩 포함).
- 원래 glyph order/ID, hmtx, cmap과 hint/layout table bytes가 유지된다. Bold의 기존 vmtx도 유지된다.
- 모든 ASCII advance=1024, 가져온 모든 한글 advance=2048.
- 필수 완성형 11172자와 현대 호환 자모 존재, 양쪽 weight/family metadata 정상.
- 모든 10개 결과를 HarfBuzz로 shape하여 완성형 11172자의 glyph와 advance를 검사했다.
  전체 음절의 NFD 입력이 NFC와 동일한 glyph/position sequence로 조합된다.
- 원본 Agave와 병합 결과의 ASCII shaping 결과가 같다.
- **FreeType hinting을 켠 hb-view**에서 12/14/16/18px ASCII를 각각 렌더링했다.
  Regular/Bold 모두 원본과 생성 PNG가 바이트 단위로 동일하다(8쌍 비교).
- 합성 폰트 테스트로 scale/offset과 advance 분리, composite 해제, donor hint 제거,
  원본 metrics 변조 탐지, missing coverage, overflow, TTC face 선택, local embedding flags 보존을 확인했다.
- cache SHA 불일치, offline cache miss, local/archive 경로 이탈, 미확인 폰트 자동 다운로드 차단,
  batch 중 한 source 실패 후 다른 source 계속 처리도 검사했다.

## 시각 확인과 확인하지 못한 사항

HarfBuzz/Cairo로 다음 실제 결과의 18px sample PNG를 생성해 직접 확인했다.

- `build/qa/sarasa-regular-18.png`
- `build/qa/sarasa-bold-18.png`
- `build/qa/han-regular-18.png`
- `build/qa/pre-bold-18.png`

코드·숫자·괄호·혼합 문장·한글/ASCII 정렬·Regular/Bold를 확인했다.
이 이미지는 **브라우저 스크린샷이 아니다**.

브라우저 제어 도구는 `No browser is available`을 반환했고,
Safari native 확인 시도도 `Sky Computer Use service startup request failed`로 실행되지 않았다.
따라서 실제 브라우저의 file:// 허용 여부, CSS font loading/OTS 처리, 화면 layout은 직접 확인하지 못했다.

preview DOM 테스트는 linkedom으로 생성 HTML의 실제 JavaScript를 실행한다.
FontFaceSet와 canvas는 모의 객체이며, 결과는 UI 로직/참조 검증만 뜻한다.
실제 브라우저에서는 카드의 “로드 완료”와 실측 폭을 확인해야 한다.
file:// 차단 시 README의 loopback HTTP 서버 안내를 사용한다.

다른 OS/에디터/터미널에서의 설치 및 작은 크기 한글 가독성, OTS 별도 검사,
옛한글 shaping/세로쓰기/Nerd Font 후처리는 검증 범위에 포함되지 않았다.
폰트 설치나 공개 배포는 수행하지 않았다.

## 자체 검토

구현자가 수행한 **self-review**이며 독립 리뷰가 아니다.
검토 범위는 요구사항의 Agave 보존, 2-cell 한글, source 교체/캐시/local, license 기록,
preview, 실패 처리 및 자동 검증이다. Nerd Font/Italic/범용 layout merge는 제외했다.

검토 중 다음을 확인하고 수정한 뒤 관련 검증을 다시 실행했다.

- F1: local font의 임베딩 permission mode를 OR로 결합하면 서로 배타적인 fsType mode가 섞일 수 있었다.
  설치/임베딩을 허용하는 고정 Agave base 위에 donor mode를 그대로 복사하고 테스트로 확인했다.
- F2: batch 시작 전 모든 config를 검사하면 하나의 config 오류가 다른 source의 빌드도 중단시켰다.
  source별 오류 처리 범위에서 검사하게 옮기고 계속 처리/실패 종료 코드를 테스트했다.
- F3: non-OFL local config에 `redistribute: true`를 잘못 지정하면 name metadata와 실제 배포 판단이 달라질 수 있었다.
  검토한 OFL preset에만 true를 허용하도록 config 검증을 명확히 했다.

검토 revision은 Git commit 대신 다음 **25개 파일의 내용 fingerprint**로 고정한다.
경로를 정렬한 뒤 각 파일에 `UTF-8(relative path) + NUL + raw contents + NUL`을 연결해 SHA-256을 계산했다.

```text
builder/*.py
sources/*.json
tests/*.py
tests/preview_ui.cjs
tests/specimen.txt
preview/template.html
build.sh
pyproject.toml
uv.lock
.gitignore
README.md
docs/design.md
docs/licenses.md
examples/local-source.json
fonts/local/README.md

SHA-256: 152f02a7d48cb8cf348eddbf51854c4b0fb39d157df73befc011f285391f2fee
```

작업 기록과 이 검증 문서 자체는 순환 해시를 피하기 위해 제외했다.
폰트/preview/cache는 ignored deliverable이며 위 출력 해시 및 manifest로 구분한다.

**PASS — revision `152f02a7d48cb8cf348eddbf51854c4b0fb39d157df73befc011f285391f2fee`**.
확인한 범위에서 미해결 Critical/Major 문제 없음. 실제 브라우저 확인 제한은 위에 명시했다.
