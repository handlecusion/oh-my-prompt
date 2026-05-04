---
description: 세션별 효율(지렛대/자율도/도구사용) 메트릭 + 상/하위 세션 비교 (인자 1=일수, 2=최소 프롬프트수)
---

다음 명령을 실행하고 결과를 그대로 사용자에게 보여줘. 결과를 임의로 해석하지 마.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/analyzers/efficiency.py" $ARGUMENTS
```

`$ARGUMENTS`가 비어있으면 `30 3`(최근 30일, 프롬프트 3회 이상 세션)을 기본값으로 사용해.
