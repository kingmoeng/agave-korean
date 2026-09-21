# 원본 폰트 라이선스 확인

2026-09-21에 공식 upstream 문서와 실제 다운로드한 font name table을 확인했다.
아래는 사용한 판본에 대한 구현 판단이며 새 source/판본을 추가할 때는 다시 확인해야 한다.

| 원본 | 공식 라이선스 | 확인 및 naming 처리 |
| --- | --- | --- |
| Agave 39 | [LICENSE](https://github.com/blobject/agave/blob/39/LICENSE) | dist/src는 OFL 1.1. 명시적 RFN 없음. 원본 Agave와 구분해 `Agave Korean` 사용 |
| Sarasa 1.0.41 | [LICENSE](https://github.com/be5invis/Sarasa-Gothic/blob/v1.0.41/LICENSE) | OFL 1.1. Renzhi Li 및 Inter/Adobe/Google 고지 포함, Source RFN 유지 |
| Source Han Sans | [LICENSE.txt](https://github.com/adobe-fonts/source-han-sans/blob/a4f7cf94edfb9d7ffbdfc4841de276358bd7e0f2/LICENSE.txt) | OFL 1.1, Source RFN. 결과 family는 `Agave Korean Han` |
| Noto Sans KR | [OFL.txt](https://github.com/google/fonts/blob/b38c5c93af322c45f633e17ac440ec1e6c94d489/ofl/notosanskr/OFL.txt) | 해당 배포의 Adobe/Source 고지 사용. 결과 family는 `Agave Korean Noto` |
| Pretendard 1.3.9 | [LICENSE](https://github.com/orioncactus/pretendard/blob/v1.3.9/LICENSE) | OFL 1.1, Pretendard RFN. 결과 family는 `Agave Korean Pre` |
| D2Coding 1.3.2 | [공식 OFL.txt](https://github.com/naver/d2-coding-font/blob/9d6f0559691ebe670a23fbf7b72a8dc42362f1fb/OFL.txt), [공식 LICENSE.md](https://github.com/naver/d2-coding-font/blob/master/LICENSE.md) | OFL 1.1, D2Coding 및 D2Coding-Bold RFN. 결과 family는 `Agave Korean D2` |

D2Coding 1.3.2 ZIP에는 별도 license text가 없고, 해당 tag의 repository에도 LICENSE가 없다.
하지만 실제 Regular/Bold의 name ID 13은 OFL 1.1을 명시하고 name ID 14는 당시 공식 OFL 안내를 가리킨다.
따라서 이 고지와 공식 repository의 저작권/RFN을 확인한 현재 OFL 전문(위 고정 commit)을 함께 사용한다.
결과 name ID 0에는 1.3.2 binary의 NHN/FONTRIX 고지도 보존한다. 구버전 asset에 동봉된 텍스트라고 주장하지 않는다.

OFL은 수정·병합·임베딩·재배포를 허용하되 조건을 붙인다.
저작권 고지와 라이선스 전문을 유지하고, 파생 폰트도 OFL로 제공하며, 원본의 Reserved Font Name을 파생 폰트의 이름으로 사용하지 않아야 한다.
폰트 자체의 단독 판매 제한과 원저작자의 endorsement를 암시하지 않는 조건도 적용된다.
구체적 조건은 각 라이선스 전문이 우선한다.

빌더는 각 build의 `LICENSES/`에 두 원본의 전문을 저장하고, font name ID 0/13에도 저작권/라이선스를 기록한다.
설명용 preview에는 `Agave + 원본 이름`을 출처로 표시하지만, font family/PS name은 별도 파생 이름이다.
`build.json`에는 source URL·판본·변환 설정·해시를 남긴다. 결과를 공유할 때 `LICENSES/`도 포함해야 한다.

Agave upstream 문서/pub의 MIT 라이선스와 폰트 dist/src의 OFL은 구분했다. 이 저장소는 upstream 구현 코드나 문서를 복사하지 않았다.
폰트 출력의 OFL을 이 저장소의 Python 코드에 자동으로 적용한다는 뜻은 아니다.

Apple SD Gothic Neo, SF 등의 독점 폰트는 이 프로젝트가 다운로드·추출·재배포하지 않는다.
local 구조는 사용자가 적법하게 준비한 파일을 처리하는 기술적 통로일 뿐이다.
소유/시스템 설치만으로 파생 폰트 제작·브라우저 임베딩 권한을 추정하면 안 된다.
미확인 preset은 `LicenseRef-Local-Unverified`, `redistribute: false`를 유지하고 결과 TTF와 preview 모두 공개하지 않는다.
