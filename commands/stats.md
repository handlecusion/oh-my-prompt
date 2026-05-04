---
description: 토큰/세션/프롬프트 종합 통계 (기본 7일, 인자로 일수 지정 가능)
---

다음 명령을 실행해서 결과를 그대로 사용자에게 보여줘.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/report.py" $ARGUMENTS
```

만약 `$ARGUMENTS`가 비어있으면 `7`을 기본값으로 사용해.
실행 후 짧게 한 줄로 무엇을 보여주는 결과인지만 덧붙이고, 데이터를 임의로 해석하지 마.
