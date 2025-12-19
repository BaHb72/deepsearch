"""
测试 AmazingData 行业相关的扩展接口

测试以下接口:
1. get_industry_base_info - 行业指数基本信息
2. get_industry_constituent - 行业指数成分股
3. get_industry_weight - 行业指数成分股日权重
4. get_industry_daily - 行业指数日行情
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from deepsearch.infrastructure.providers.implementations.amazingdata import AmazingDataExtended
from deepsearch.config.models.amazingdata import AmazingDataConfig


async def test_industry_interfaces():
    """测试行业相关接口"""
    
    # 创建配置
    config = AmazingDataConfig(
        username="your_username",  # 替换为实际用户名
        password="your_password",  # 替换为实际密码
        local_path="D:/AmazingData_local_data/"
    )
    
    # 创建提供者实例
    provider = AmazingDataExtended(config)
    
    try:
        # 初始化连接
        print("正在初始化AmazingData连接...")
        await provider.initialize()
        print("连接成功！\n")
        
        # 测试1: 获取行业指数基本信息
        print("=" * 60)
        print("测试1: 获取行业指数基本信息")
        print("=" * 60)
        industry_base_info = await provider.get_industry_base_info()
        if not industry_base_info.empty:
            print(f"成功获取 {len(industry_base_info)} 条行业指数基本信息")
            print("\n前5条数据:")
            print(industry_base_info.head())
            print(f"\n列名: {list(industry_base_info.columns)}")
            
            # 获取几个测试用的行业指数代码
            test_codes = industry_base_info['INDEX_CODE'].head(3).tolist() if 'INDEX_CODE' in industry_base_info.columns else []
            print(f"\n选择测试代码: {test_codes}")
        else:
            print("未获取到行业指数基本信息")
            test_codes = []
        
        if test_codes:
            # 测试2: 获取行业指数成分股
            print("\n" + "=" * 60)
            print("测试2: 获取行业指数成分股")
            print("=" * 60)
            print(f"测试指数代码: {test_codes}")
            constituent_df = await provider.get_industry_constituent(test_codes)
            if not constituent_df.empty:
                print(f"成功获取成分股数据，共 {len(constituent_df)} 条")
                print("\n前5条数据:")
                print(constituent_df.head())
                print(f"\n列名: {list(constituent_df.columns)}")
            else:
                print("未获取到成分股数据")
            
            # 测试3: 获取行业指数成分股日权重
            print("\n" + "=" * 60)
            print("测试3: 获取行业指数成分股日权重")
            print("=" * 60)
            print(f"测试指数代码: {test_codes}")
            print("时间范围: 20241201 - 20241215")
            weight_df = await provider.get_industry_weight(
                code_list=test_codes,
                begin_date=20241201,
                end_date=20241215
            )
            if not weight_df.empty:
                print(f"成功获取权重数据，共 {len(weight_df)} 条")
                print("\n前5条数据:")
                print(weight_df.head())
                print(f"\n列名: {list(weight_df.columns)}")
            else:
                print("未获取到权重数据")
            
            # 测试4: 获取行业指数日行情
            print("\n" + "=" * 60)
            print("测试4: 获取行业指数日行情")
            print("=" * 60)
            print(f"测试指数代码: {test_codes}")
            print("时间范围: 20241201 - 20241215")
            daily_df = await provider.get_industry_daily(
                code_list=test_codes,
                begin_date=20241201,
                end_date=20241215
            )
            if not daily_df.empty:
                print(f"成功获取日行情数据，共 {len(daily_df)} 条")
                print("\n前5条数据:")
                print(daily_df.head())
                print(f"\n列名: {list(daily_df.columns)}")
            else:
                print("未获取到日行情数据")
        
        print("\n" + "=" * 60)
        print("所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 清理资源
        try:
            await provider.stop_async()
            print("\n已断开连接")
        except Exception as e:
            print(f"断开连接时发生错误: {e}")


if __name__ == "__main__":
    asyncio.run(test_industry_interfaces())
