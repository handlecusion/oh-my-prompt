---
description: stats + patterns + efficiency + suggest archive를 사이드바 탭으로 묶은 통합 대시보드 (인자 1=stats 일수, 2=patterns/efficiency 일수, 3=최소반복횟수)
---

다음 명령을 그대로 한 번 실행해서 브라우저로 통합 대시보드를 띄워.
실행 결과(한 줄 "통합 대시보드 열림: ...")만 사용자에게 보여주고, 데이터를 임의로 해석하거나 추가 설명을 하지 마.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/lib/dashboard_all.py" $ARGUMENTS
```

`$ARGUMENTS`가 비어있으면 `7 30 3` (stats 7일, patterns/efficiency 30일·최소 3회)을 기본값으로 써.
