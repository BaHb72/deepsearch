"""
AmazingData SDK v1.0.4 Monkey Patches

修复两个已确认的 SDK 内部 bug（通过字节码反编译验证）：

Bug 1: get_margin_detail (info_data.py line 413)
  - LocalDataFolder.margin_detail (小写) 在枚举中不存在，应为 Margin_Detail (PascalCase)
  - 查询路径用 INFODATA，但下载路径用 BASEDATA，目录不一致

Bug 2: get_right_issue (info_data.py line 147)
  - df[30列] 直接下标选择，服务端不返回 PASS_DATE/APPROVED_DATE/EXPECTED_FUND_RAISING
  - download 层已处理缺失列（补 NaN），但 query 层没有

验证方法：对 info_data.pyc 使用 dis.dis() 反汇编确认。
"""

from __future__ import annotations

from importlib import import_module

from loguru import logger

_SDK_DEFAULT_LOCAL_PATH = "D://AmazingData_local_data//"

# get_margin_detail 下载层使用的列名（从 download_info_data.pyc 反编译确认）
_MARGIN_DETAIL_COLUMNS = (
    "MARKET_CODE",
    "TRADE_DATE",
    "BORROW_MONEY_BALANCE",
    "PURCH_WITH_BORROW_MONEY",
    "REPAYMENT_OF_BORROW_MONEY",
    "SEC_LENDING_BALANCE",
    "SALES_OF_BORROWED_SEC",
    "REPAYMENT_OF_BORROW_SEC",
    "SEC_LENDING_BALANCE_VOL",
    "MARGIN_TRADE_BALANCE",
)

# get_right_issue 查询层使用的 30 列名（从 info_data.pyc 反编译确认）
_RIGHT_ISSUE_COLUMNS = (
    "MARKET_CODE",
    "PROGRESS",
    "PRICE",
    "RATIO",
    "AMT_PLAN",
    "AMT_REAL",
    "COLLECTION_FUND",
    "SHAREB_REG_DATE",
    "EX_DIVIDEND_DATE",
    "LISTED_DATE",
    "PAY_START_DATE",
    "PAY_END_DATE",
    "PREPLAN_DATE",
    "SMTG_ANN_DATE",
    "PASS_DATE",
    "APPROVED_DATE",
    "EXECUTE_DATE",
    "RESULT_DATE",
    "LIST_ANN_DATE",
    "GUARANTOR",
    "GUARTYPE",
    "RIGHTSISSUE_CODE",
    "ANN_DATE",
    "RIGHTSISSUE_YEAR",
    "RIGHTSISSUE_DESC",
    "RIGHTSISSUE_NAME",
    "RATIO_DENOMINATOR",
    "RATIO_MOLECULAR",
    "SUBS_METHOD",
    "EXPECTED_FUND_RAISING",
)


def _patched_get_margin_detail(self, code_list, local_path=_SDK_DEFAULT_LOCAL_PATH, is_local=True):
    """
    修复后的 get_margin_detail (替换 InfoData.get_margin_detail)

    原始 bug:
      line 413: get_data_from_hdf5(path, LocalDataFolder.margin_detail.value)
                                                         ^^^^^^^^^^^^^^ 小写，枚举中不存在
      line 411: folder_name = INFODATA/Margin_Detail  (但下载保存到 BASEDATA/Margin_Detail)

    修复:
      1. margin_detail -> Margin_Detail (PascalCase)
      2. INFODATA -> BASEDATA (与 download_margin_detail 的保存路径一致)
    """
    local_data_folder_mod = import_module("AmazingData.config.local_data_folder")
    download_mod = import_module("AmazingData.download_data.download_info_data")
    save_mod = import_module("AmazingData.utils.save_get_data")

    LocalDataFolder = getattr(local_data_folder_mod, "LocalDataFolder")
    DownloadInfoData = getattr(download_mod, "DownloadInfoData")
    get_data_from_hdf5 = getattr(save_mod, "get_data_from_hdf5")

    if is_local:
        # [Fix] BASEDATA (not INFODATA) + Margin_Detail (not margin_detail)
        folder_name = LocalDataFolder.BASEDATA.value + "/" + LocalDataFolder.Margin_Detail.value
        path = local_path + folder_name + "/"
        try:
            self.margin_detail = get_data_from_hdf5(path, LocalDataFolder.Margin_Detail.value)
        except FileNotFoundError:
            download_obj = DownloadInfoData(local_path)
            self.margin_detail = download_obj.download_margin_detail(code_list)
    else:
        try:
            download_obj = DownloadInfoData(local_path)
            self.margin_detail = download_obj.download_margin_detail(code_list)
        except FileNotFoundError:
            download_obj = DownloadInfoData(local_path)
            self.margin_detail = download_obj.download_margin_detail(code_list)

    return self.margin_detail


def _patched_get_right_issue(self, code_list, local_path=_SDK_DEFAULT_LOCAL_PATH, is_local=True):
    """
    修复后的 get_right_issue (替换 InfoData.get_right_issue)

    原始 bug:
      line 147: self.right_issue = self.right_issue[list(30列)]
      服务端返回数据缺少 PASS_DATE, APPROVED_DATE, EXPECTED_FUND_RAISING
      pandas 抛出 KeyError

    修复:
      df[columns] -> df.reindex(columns=columns, fill_value=NaN)
      缺失列自动补 NaN，不再 KeyError
    """
    import numpy as np

    local_data_folder_mod = import_module("AmazingData.config.local_data_folder")
    download_mod = import_module("AmazingData.download_data.download_info_data")
    save_mod = import_module("AmazingData.utils.save_get_data")

    LocalDataFolder = getattr(local_data_folder_mod, "LocalDataFolder")
    DownloadInfoData = getattr(download_mod, "DownloadInfoData")
    get_data_from_hdf5 = getattr(save_mod, "get_data_from_hdf5")

    if is_local:
        folder_name = LocalDataFolder.INFODATA.value + "/" + LocalDataFolder.Right_Issue.value
        path = local_path + folder_name + "/"
        try:
            self.right_issue = get_data_from_hdf5(path, LocalDataFolder.Right_Issue.value)
        except FileNotFoundError:
            download_obj = DownloadInfoData(local_path)
            self.right_issue = download_obj.download_right_issue(code_list)
        # [Fix] reindex 代替直接下标，缺失列补 NaN
        if hasattr(self.right_issue, "reindex"):
            self.right_issue = self.right_issue.reindex(
                columns=list(_RIGHT_ISSUE_COLUMNS), fill_value=np.nan
            )
    else:
        try:
            download_obj = DownloadInfoData(local_path)
            self.right_issue = download_obj.download_right_issue(code_list)
        except FileNotFoundError:
            download_obj = DownloadInfoData(local_path)
            self.right_issue = download_obj.download_right_issue(code_list)

    return self.right_issue


_patches_applied: list[str] = []


def apply_sdk_patches() -> list[str]:
    """
    应用 SDK monkey patches。

    在 SDK 加载后调用，替换 InfoData 类上的两个有 bug 的方法。
    由于 Python 方法解析通过类查找，补丁对所有现有和未来实例生效。

    Returns:
        应用成功的补丁名称列表
    """
    global _patches_applied
    if _patches_applied:
        return _patches_applied

    try:
        info_mod = import_module("AmazingData.query_api.info_data")
        InfoData = getattr(info_mod, "InfoData")
    except ImportError:
        logger.debug("[SDK补丁] AmazingData SDK 未安装，跳过")
        return _patches_applied

    # Patch 1: get_margin_detail
    try:
        InfoData.get_margin_detail = _patched_get_margin_detail
        _patches_applied.append("get_margin_detail")
        logger.info(
            "[SDK补丁] get_margin_detail: "
            "修复 LocalDataFolder 大小写(margin_detail->Margin_Detail) "
            "+ 路径不一致(INFODATA->BASEDATA)"
        )
    except Exception as e:
        logger.warning(f"[SDK补丁] get_margin_detail 补丁失败: {e}")

    # Patch 2: get_right_issue
    try:
        InfoData.get_right_issue = _patched_get_right_issue
        _patches_applied.append("get_right_issue")
        logger.info(
            "[SDK补丁] get_right_issue: "
            "修复硬编码列名 KeyError (PASS_DATE/APPROVED_DATE/EXPECTED_FUND_RAISING 缺失)"
        )
    except Exception as e:
        logger.warning(f"[SDK补丁] get_right_issue 补丁失败: {e}")

    if _patches_applied:
        logger.info(
            f"[SDK补丁] 共应用 {len(_patches_applied)} 个 v1.0.4 补丁: "
            f"{', '.join(_patches_applied)}"
        )

    return _patches_applied
