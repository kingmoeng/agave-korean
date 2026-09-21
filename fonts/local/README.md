# 직접 제공하는 폰트

`examples/local-source.json`을 `sources/my-korean.json`으로 복사하고
`fonts/local/my-korean/Regular.ttf`, `Bold.ttf`를 준비하세요.
`./build.sh my-korean`으로 빌드합니다. 원본은 Git에서 제외됩니다.

- `.otf`도 가능하며 config의 파일명만 맞추면 됩니다.
- TTC/OTC는 같은 파일을 두 weight에 지정하고 각각 `"font_number": 0`, `1`처럼 정확한 face index를 지정합니다.
- 가변 폰트는 같은 파일에 `"axes": {"wght": 400}` / `700`을 지정합니다.
- 영문 glyph는 사용하지 않습니다. 필수 현대 한글 coverage가 없으면 빌드가 실패합니다.
- local 파일을 소유했다는 사실만으로 수정·병합·임베딩·재배포 권리가 생기지 않습니다.
  Apple SD Gothic Neo, SF 등 독점 폰트는 해당 EULA에서 허용하는 작업만 하세요.
  이 프로젝트는 그러한 폰트를 내려받거나 시스템 폰트에서 추출하지 않습니다.
- 라이선스 미확인 preset은 `redistribute: false`로 유지합니다.
  결과와 preview도 로컬 실험용이며 공개 저장소·웹사이트에 올리지 마세요.
