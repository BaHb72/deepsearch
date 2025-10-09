import re
from pathlib import Path

path = Path('deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_types.py')
text = path.read_text(encoding='utf-8')

period_pattern = re.compile(r"class AmazingDataPeriod\(Enum\):\s+\"\"\"AmazingData .*?\"\"\"\s+(?:    .*\n)+?    YEAR = \"1Y\"  # .*?\n", re.S)
new_period = """class AmazingDataPeriod(Enum):\n    \"\"\"AmazingData ��������\"\"\"\n\n    TICK = \"tick\"  # ���\n    SNAPSHOT = \"snapshot\"  # ����\n    SNAPSHOT_FUTURE = \"snapshot_future\"  # �ڻ�ʵʱ����\n    SNAPSHOT_HKT = \"snapshot_hkt\"  # ����ͨʵʱ����\n    M1 = \"1m\"  # 1����\n    M3 = \"3m\"  # 3����\n    M5 = \"5m\"  # 5����\n    M10 = \"10m\"  # 10����\n    M15 = \"15m\"  # 15����\n    M30 = \"30m\"  # 30����\n    M60 = \"60m\"  # 60����\n    M120 = \"120m\"  # 120����\n    DAY = \"1d\"  # ����\n    WEEK = \"1w\"  # ����\n    MONTH = \"1M\"  # ����\n    QUARTER = \"1Q\"  # ����\n    YEAR = \"1Y\"  # ����\n\n"""
if not period_pattern.search(text):
    raise SystemExit('Failed to locate AmazingDataPeriod definition')
text = period_pattern.sub(new_period, text, count=1)

security_pattern = re.compile(r"class AmazingDataSecurityType\(Enum\):\s+\"\"\".*?\"\"\"\s+(?:    .*\n)+?    OPTION = \"EXTRA_OPTION\"  # .*?\n", re.S)
new_security = """class AmazingDataSecurityType(Enum):\n    \"\"\"֤ȯ����\"\"\"\n\n    STOCK_A = \"EXTRA_STOCK_A\"  # A��\n    STOCK_A_SH_SZ = \"EXTRA_STOCK_A_SH_SZ\"  # �Ͻ��������A��\n    INDEX = \"EXTRA_INDEX\"  # ����ָ��(ͨ用)\n    INDEX_A = \"EXTRA_INDEX_A\"  # ����ָ��\n    INDEX_A_SH_SZ = \"EXTRA_INDEX_A_SH_SZ\"  # �Ͻ��������ָ��\n    SH_INDEX = \"SH_INDEX\"  # �Ϻ���ָ��\n    SZ_INDEX = \"SZ_INDEX\"  # ������ָ��\n    BJ_INDEX = \"BJ_INDEX\"  # ������ָ��\n    ETF = \"EXTRA_ETF\"  # ETF\n    SH_ETF = \"SH_ETF\"  # �Ϻ��� ETF\n    SZ_ETF = \"SZ_ETF\"  # ������ ETF\n    KZZ = \"EXTRA_KZZ\"  # ��תծ\n    SH_KZZ = \"SH_KZZ\"  # �Ϻ�תծ\n    SZ_KZZ = \"SZ_KZZ\"  # ����תծ\n    HKT = \"EXTRA_HKT\"  # ����ͨ\n    SH_HKT = \"SH_HKT\"  # �Ϻ�����ͨ\n    SZ_HKT = \"SZ_HKT\"  # ��������ͨ\n    FUTURE = \"EXTRA_FUTURE\"  # �ڻ�\n    ZJ_FUTURE = \"ZJ_FUTURE\"  # �н����ڻ�\n    SQ_FUTURE = \"SQ_FUTURE\"  # �������ڻ�\n    DS_FUTURE = \"DS_FUTURE\"  # �������ڻ�\n    ZS_FUTURE = \"ZS_FUTURE\"  # ֣�����ڻ�\n    SN_FUTURE = \"SN_FUTURE\"  # �Ϻ�������Դ���ڻ�\n    OPTION = \"EXTRA_OPTION\"  # ��Ȩ\n\n"""
if not security_pattern.search(text):
    raise SystemExit('Failed to locate AmazingDataSecurityType definition')
text = security_pattern.sub(new_security, text, count=1)

path.write_text(text, encoding='utf-8')
