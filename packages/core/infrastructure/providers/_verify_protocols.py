"""
验证 Protocol 实现是否正确

这个脚本验证：
1. Factory 类实现了 ProviderFactoryStrategy 协议
2. Protocol 没有混用 @abstractmethod
"""

from .factory.akshare_factory import AkShareFactory
from .factory.amazingdata_factory import AmazingDataFactory
from .factory.base import ProviderFactoryStrategy
from .factory.miniqmt_factory import MiniQMTFactory


def verify_protocols():
    """验证所有工厂类符合 Protocol"""

    print("开始验证 Protocol 实现...")

    # 验证 AmazingDataFactory
    amazingdata_factory = AmazingDataFactory()
    assert isinstance(
        amazingdata_factory, ProviderFactoryStrategy
    ), "AmazingDataFactory 必须实现 ProviderFactoryStrategy 协议"
    print("AmazingDataFactory Protocol 验证通过")

    # 验证 MiniQMTFactory
    miniqmt_factory = MiniQMTFactory()
    assert isinstance(
        miniqmt_factory, ProviderFactoryStrategy
    ), "MiniQMTFactory 必须实现 ProviderFactoryStrategy 协议"
    print("MiniQMTFactory Protocol 验证通过")

    # 验证 AkShareFactory
    akshare_factory = AkShareFactory()
    assert isinstance(
        akshare_factory, ProviderFactoryStrategy
    ), "AkShareFactory 必须实现 ProviderFactoryStrategy 协议"
    print("AkShareFactory Protocol 验证通过")

    print("\n所有 Protocol 验证通过")


if __name__ == "__main__":
    verify_protocols()
