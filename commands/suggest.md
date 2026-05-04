---
description: 분석 결과를 claude -p로 해석시켜 CLAUDE.md/메모리/hook 패치 초안을 자동 생성 (인자 1=일수, 2=최소반복횟수)
---

다음 명령을 실행하고 출력을 그대로 사용자에게 보여줘. 결과는 별도 claude 프로세스가 생성한 거니까 임의로 수정·요약하지 말고 그대로 표시해.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/suggest.py" $ARGUMENTS
```

`$ARGUMENTS`가 비어있으면 `30 3`을 기본값으로 사용해.
