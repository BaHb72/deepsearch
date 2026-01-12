from pathlib import Path

path = Path("deepsearch/utils/patterns/retry_handler.py")
text = path.read_text(encoding="utf-8")
old_async = '        # �������Զ�ʧ��\n        self.stats["failed_retries"] += 1\n        logger.error(f"��������ʧ��: {source_name} ����: {str(last_error)[:200]}")\n        raise last_error\n\n'
new_async = '        # �������Զ�ʧ��\n        self.stats["failed_retries"] += 1\n        logger.error(f"��������ʧ��: {source_name} ����: {str(last_error)[:200]}")\n        if last_error is None:\n            raise RuntimeError("Retry failed without capturing an exception")\n        raise last_error\n\n'
if old_async in text:
    text = text.replace(old_async, new_async, 1)
old_sync = '        self.stats["failed_retries"] += 1\n        raise last_error\n\n    def _extract_error_code'
new_sync = '        self.stats["failed_retries"] += 1\n        if last_error is None:\n            raise RuntimeError("Retry failed without capturing an exception")\n        raise last_error\n\n    def _extract_error_code'
if old_sync in text:
    text = text.replace(old_sync, new_sync, 1)
path.write_text(text, encoding="utf-8")
