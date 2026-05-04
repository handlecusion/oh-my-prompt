---
description: 반복되는 사용자 프롬프트와 의도 분포를 분석해 CLAUDE.md/메모리 후보를 제안 (인자 1=일수, 2=최소반복횟수)
---

다음 명령을 실행하고 결과를 그대로 사용자에게 보여줘. 결과를 임의로 해석하거나 요약하지 마.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/analyzers/patterns.py" $ARGUMENTS
```

`$ARGUMENTS`가 비어있으면 `30 3`(최근 30일, 최소 3회 반복)을 기본값으로 사용해.
