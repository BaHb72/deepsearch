"""AmazingData 集成测试标记。

跳过策略集中在 ``tests.integration.conftest``，这里仅保留目录级语义说明。
"""

import pytest

pytestmark = [
    pytest.mark.manual(reason="需要接入 AmazingData 真实环境"),
    pytest.mark.external,
    pytest.mark.amazingdata,
]
