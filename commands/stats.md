---
description: 토큰/세션/프롬프트 종합 통계 웹 대시보드 (기본 7일, 인자로 일수 지정 가능)
---

다음 명령을 그대로 한 번 실행해서 브라우저로 대시보드를 띄워.
실행 결과(한 줄 "대시보드 열림: ...")만 사용자에게 보여주고, 데이터를 임의로 해석하거나 추가 설명을 하지 마.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/dashboard.py" $ARGUMENTS
```

`$ARGUMENTS`가 비어있으면 `7`을 기본값으로 써.
