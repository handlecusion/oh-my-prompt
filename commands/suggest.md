---
description: 사용 데이터에서 CLAUDE.md/메모리/hook 패치 후보 자동 생성 (인자 1=일수, 2=최소반복횟수). 결과는 ~/.claude/omp_suggestions/ 에 누적 저장됨.
---

다음 순서를 정확히 따라.

## 1단계: 데이터 수집

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/suggest_prep.py" $ARGUMENTS
```

`$ARGUMENTS`가 비어있으면 `30 3`을 기본값으로 써. stdout은 한 줄 JSON이며 `input_path`, `output_path`, `days`, `min_count`, `timestamp` 필드를 가진다. 그 JSON에서 `input_path`와 `output_path`를 추출해 변수처럼 다음 단계에 그대로 전달해.

## 2단계: 서브에이전트 호출

`Agent` 도구로 `subagent_type: "omp:suggest-analyzer"` 를 호출. **프롬프트는 정확히 다음 두 줄만** 적어 (다른 설명 금지):

```
input_path: <1단계의 input_path>
output_path: <1단계의 output_path>
```

서브에이전트는 분석 본문을 `output_path` 파일에 Write로 저장하고 `saved: <path>`만 반환한다.

## 3단계: 보관 파일을 그대로 출력

`output_path`를 `Read`로 읽어, **읽은 내용 전체를 너의 응답 본문에 한 글자도 빠짐없이 그대로 옮겨 적어**. 마크다운 헤더, 들여쓰기, 줄바꿈, 인용부호 모두 유지.

금지:
- 본문 앞뒤에 머리말·맺음말·이모지·요약·메타 코멘트 어떤 것도 추가하지 마.
- 분석 본문을 수정·요약·재구성·번역하지 마.
- bash 출력에만 남기고 끝내지 마 — 사용자가 펼치지 않아도 응답 메시지에서 바로 읽을 수 있어야 한다.

분석 본문 외에는 한 글자도 더 쓰지 마.
