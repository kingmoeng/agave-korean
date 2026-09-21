# Agave Korean

Agave의 일반형 Regular/Bold에 원하는 한글을 더하고, 설치 없이 비교하는 작은 font builder입니다.
Agave 원본 glyph를 다시 그리거나 확대하지 않습니다. 한글 outline만 조절하며 **ASCII 1칸 : 한글 2칸**을 정확히 유지합니다.

기본 결과는 `Agave Korean` family의 `AgaveKorean-Regular.ttf`, `AgaveKorean-Bold.ttf`입니다.
대체 source는 설치 시 충돌하지 않도록 서로 다른 family 이름을 사용합니다.

## 시작

Python 3.11 이상과 [uv](https://docs.astral.sh/uv/)를 권장합니다. 런타임 의존성은 fontTools와 py7zr뿐이며 FontForge, Node, 웹 프레임워크는 필요하지 않습니다.

```sh
uv sync --frozen
./build.sh                         # Sarasa Mono K Regular + Bold
./build.sh pretendard
./build.sh sarasa-mono-k noto-sans-kr
./build.sh --all                   # 등록된 모든 source
```

CLI를 직접 실행할 수도 있습니다.

```sh
uv run --frozen python -m builder list
uv run --frozen python -m builder build   # 기본값 Sarasa
uv run --frozen python -m builder validate --all --offline
uv run --frozen python -m builder preview
```

uv 없이 실행하려면:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'fonttools>=4.61,<5' 'py7zr>=1.1,<2'
.venv/bin/python -m builder build
```

첫 실행에는 인터넷이 필요합니다. 이후 `./build.sh --all --offline`으로 캐시만 사용해 재빌드할 수 있습니다.
폰트·라이선스 다운로드는 고정 태그/commit URL과 SHA-256을 사용합니다. 압축 파일에서는 지정한 파일만 해제합니다.
실패한 source는 오류로 표시하고, 여러 source 중 나머지는 계속 처리한 뒤 종료 코드 1을 반환합니다.
`--all`에 local preset도 포함되므로 해당 파일은 미리 준비해야 합니다.

```text
sources/                 source별 JSON preset (agave.json은 고정 base)
builder/                 다운로드, 병합, 검증, preview 생성
fonts/local/<id>/        사용자가 제공한 폰트 (Git 제외)
.cache/                  다운로드·압축 해제·uv 캐시 (Git 제외)
build/<id>/              검증을 통과한 결과 (Git 제외)
  AgaveKorean-Regular.ttf
  AgaveKorean-Bold.ttf
  LICENSES/              원본 저작권 고지 및 OFL 전문
  build.json             config, 원본/결과 해시, metrics, 검증 결과
preview/template.html    비교 UI 소스
preview/index.html       빌드마다 갱신되는 결과 (Git 제외)
```

TTF 두 개를 임시 디렉터리에서 모두 생성·검증한 다음 결과 경로에 반영합니다.
`build.json`은 마지막에 교체하며, preview는 결과 해시가 맞는 빌드만 표시합니다.
한 프로젝트에서 빌드는 하나씩 실행하세요. 여러 프로세스의 동시 빌드는 지원하지 않습니다.

## 제공하는 preset

| CLI id | 고정 원본 | 형식 | 결과 family |
| --- | --- | --- | --- |
| `sarasa-mono-k` | Sarasa 1.0.41, Mono K Unhinted | TTF / GitHub 7z | Agave Korean |
| `source-han-sans-kr` | Source Han Sans KR 2.005 | CFF OTF / 공식 URL | Agave Korean Han |
| `noto-sans-kr` | Google Fonts commit `b38c5c93` | variable TTF, 400/700 | Agave Korean Noto |
| `pretendard` | Pretendard 1.3.9 | CFF OTF / 공식 URL | Agave Korean Pre |
| `d2coding` | D2Coding 1.3.2 | TTF / GitHub ZIP | Agave Korean D2 |

Agave는 **39**의 `Agave-Regular.ttf`, `Agave-Bold.ttf`를 고정합니다.
`zeroslashed`, `parenbulged` 변형은 사용하지 않습니다. D2Coding은 최신 자동 추적 대신 검사한 1.3.2를 고정했습니다.

## Preview

빌드 후 **`preview/index.html`을 브라우저에서 여세요.** 상대 경로의 TTF를 `@font-face`로 로드하며 외부 서비스에 접속하지 않습니다.

- source 표시/숨김, Regular/Bold 선택, 12·14·16·18px 등 크기 선택
- 같은 코드·숫자·영문·한글 sample과 공통 편집 문장
- baseline 비교용 `HH xx gg pq | 한글 가나다`
- ASCII 두 글자 간격의 2-cell 눈금, `MM`과 `한`의 브라우저 실측 폭
- 폰트 로딩 성공/실패 표시, synthetic bold/italic 비활성화

브라우저가 `file://`의 폰트 접근을 차단하면 Python 내장 서버를 선택적으로 사용하세요.

```sh
python3 -m http.server 8000 --bind 127.0.0.1
# http://localhost:8000/preview/
```

이는 개발용 선택지이며 외부 웹서버 설치는 필요 없습니다. 로딩 실패 상태에서는 시스템 fallback이므로 비교하지 마세요.
TTF 해시가 URL에 붙어 재빌드 후 캐시를 구분합니다. 재빌드 후 페이지를 새로고침하세요.

## 한글 크기와 위치 조절

`sources/sarasa-mono-k.json` 등의 값을 편집합니다.

```json
"transform": {
  "scale": 0.85,
  "x_offset": 0,
  "y_offset": -60
}
```

- `scale`: source UPM → Agave UPM 변환 뒤 적용하는 **균일한 x/y 배율**입니다. `1.0`은 원본의 em 비율을 유지합니다.
- `x_offset`, `y_offset`: **Agave font units**입니다. 현재 UPM은 2048이며 x 양수는 오른쪽, y 양수는 위쪽입니다.
- source의 advance box를 새 2-cell 안에 중앙 정렬하고 offset을 적용합니다. 원본의 좌우 sidebearing 비대칭은 유지됩니다.
- advance는 scale/offset에 관계없이 항상 2048입니다. 축별로 다른 배율을 써서 글자를 찌그러뜨리지 않습니다.
- 기본 `.85, 0, -60`은 Agave 높이와 줄 간격에 맞춘 출발점입니다. source마다 원하는 크기·굵기 느낌을 preview로 확인하세요.

```sh
./build.sh sarasa-mono-k --offline
```

셀 밖으로 나가는 outline은 빌드 시 경고합니다. 크게 확대하면 글자나 줄 사이가 겹칠 수 있습니다.
Agave의 hhea/typo 줄 간격은 유지하고, Windows clipping bounds만 전체 outline을 수용하도록 늘립니다.
preview는 비교를 위해 1.8 line-height를 쓰므로 실제 에디터의 줄 간격에서도 확인하세요.

## 다른 source 추가

기존 JSON을 `sources/<id>.json`으로 복사해 `id`, `name`, **고유한** `family`, 두 `fonts`, `transform`, `license`를 수정합니다.
`id`는 소문자/숫자/하이픈, `family`는 45자 이내 ASCII 문자/숫자/공백입니다. family에는 원본의 Reserved Font Name을 쓰지 마세요.

폰트 위치는 다음 세 형태를 지원합니다.

```json
{"github": {"repo": "owner/repo", "tag": "v1.0", "asset": "fonts.zip"}, "archive": "zip", "member": "fonts/Regular.ttf", "sha256": "..."}
```

```json
{"url": "https://official.example/Regular.otf", "sha256": "..."}
```

```json
{"local": "my-korean/Regular.ttf"}
```

`sha256`에는 다운로드 파일 자체의 64자리 소문자 해시를 지정합니다(압축 파일이면 archive 해시).
직접 추가한 source에서는 선택 사항이지만, 재현성과 변조 검사를 위해 지정하는 것을 권장합니다.
archive는 `zip` 또는 `7z`이며 `member`는 정확한 내부 파일 경로입니다.
TTC/OTC는 `font_number`, 가변 폰트는 `axes`를 추가합니다. 지정하지 않은 가변 축은 기본값에 고정됩니다.

local 예제는 [examples/local-source.json](examples/local-source.json)과 [fonts/local/README.md](fonts/local/README.md)에 있습니다.
라이선스가 확인된 OFL source만 `license.id: "OFL-1.1"`, `redistribute: true`로 두고 `license.files`에 저작권 고지를 포함한 전문을 지정합니다.
미확인·독점 폰트는 `redistribute: false`와 local 파일만 허용합니다. 결과에는 `LOCAL-ONLY.txt`와 preview 경고가 붙습니다.
이 값은 이용허락을 대신하지 않습니다. 수정·병합·임베딩이 허용되는지는 사용자가 확인해야 합니다.

## 설치

마음에 드는 source의 Regular/Bold 두 TTF를 설치합니다.

- macOS: TTF를 열고 서체 관리자에서 설치
- Windows: 두 파일을 선택하고 우클릭 → 설치
- Linux: `~/.local/share/fonts/`에 두 파일을 복사하고 `fc-cache -f`

에디터/터미널을 재시작한 뒤 preset 표의 family 이름을 선택합니다.
같은 family를 tuning해서 다시 설치할 때는 기존 버전을 제거하고 교체하면 OS font cache 혼동을 줄일 수 있습니다.
배포할 때는 해당 폴더의 `LICENSES/`도 함께 포함하세요. 이 도구는 설치나 공개 배포를 자동 수행하지 않습니다.

## 검증

매 빌드에 자동으로 다음 검사가 실행됩니다.

- 저장한 TTF 재로딩 및 모든 테이블 파싱, Regular/Bold family/style/weight 확인
- ASCII U+0020–007E의 고정폭, 현대 한글 완성형 11,172자와 현대 호환 자모 존재
- 가져온 모든 한글의 advance가 ASCII의 정확히 2배인지 검사
- **Agave 전체 glyph의 raw `glyf` 바이트, glyph ID, hmtx, 원래 cmap 보존**
- 기존 fpgm/prep/cvt/gasp 및 layout 테이블 바이트 보존, Agave 줄 간격 보존
- 한글 composite 해제와 원본 한글 hinting 미반입 확인

```sh
uv sync --frozen
uv run --frozen python -m unittest discover -s tests -v
./build.sh --all --offline
uv run --frozen python -m builder validate --all --offline
```

unit test는 작은 합성 폰트로 transform, composite, hinting, 오류·캐시·local 경로를 검사합니다.
실제 `build/`가 있으면 HarfBuzz로 원본/결과 ASCII shaping과 **전체 완성형 NFC/NFD**의 동일한 glyph/2-cell 폭을 추가 검사합니다.
`hb-view`가 설치돼 있으면 FreeType 힌팅 렌더링도 원본과 픽셀 단위로 비교합니다. HarfBuzz는 개발 검증용이며 빌드 의존성은 아닙니다.
실행 증거와 환경상 제한은 [docs/verification.md](docs/verification.md)에 기록합니다.

## 라이선스와 범위

조사한 Agave·Sarasa·Source Han Sans·Noto Sans KR·Pretendard·D2Coding은 OFL 1.1입니다.
파생 폰트도 OFL로 제공하고, 저작권 고지/라이선스 유지, Reserved Font Name 회피, 폰트 단독 판매 금지 등의 조건을 따라야 합니다.
실제 고지와 링크, D2Coding 구버전의 라이선스 출처는 [docs/licenses.md](docs/licenses.md)를 확인하세요.
폰트 바이너리는 저장소에 포함하지 않습니다. `build/`, 캐시, local 폰트, 생성된 preview는 Git에서 제외됩니다.

지원 범위는 현대 한글 완성형과 호환 자모입니다. 옛 호환 자모는 donor가 제공하면 추가합니다(Pretendard는 일부 없음).
HarfBuzz에서 현대 NFD 조합은 검증했지만, 옛한글 조합·독립 conjoining jamo·한자·세로쓰기·원본 한글 GSUB/GPOS 기능은 지원하지 않습니다.
Agave Regular/Bold의 기존 Unicode coverage 차이는 그대로 유지합니다.
한글 hinting은 제거되므로 작은 크기의 선명도는 렌더러에 따라 다를 수 있습니다.
CFF 변환에는 최대 0.5 Agave unit의 cubic→quadratic 근사와 정수 좌표 반올림이 들어갑니다.
자세한 테이블별 결정은 [docs/design.md](docs/design.md)에 있습니다.

Italic, 추가 weight, Nerd Fonts patcher는 이번 범위에서 제외했습니다. Nerd Font 후처리를 추가한다면 기본 결과 뒤에 별도 실행하고 원본 보존·폭·라이선스를 다시 검증해야 합니다.
