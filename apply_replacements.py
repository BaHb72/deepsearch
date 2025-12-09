from pathlib import Path

path = Path("deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process.py")
text = path.read_text(encoding="utf-8")
block1 = "        callbacks_snapshot: dict[str, tuple[SubscriptionCallback, ...]] = {}\n        should_start = False\n        async with self._subscription_lock:\n            for code in unique_codes:\n                bucket = self._subscription_callbacks.get(code)\n                if bucket is None:\n                    bucket = set()\n                    self._subscription_callbacks[code] = bucket\n                bucket.add(callback)\n                callbacks_snapshot[code] = tuple(bucket)\n            task = self._subscription_task\n            should_start = task is None or task.done()\n"
block1_new = "        callbacks_snapshot: dict[str, tuple[SubscriptionCallback, ...]] = {}\n        should_start = False\n        async with self._subscription_lock:\n            self._subscription_registry.add(unique_codes, callback, canonical_type)\n            for code in unique_codes:\n                bucket = self._subscription_callbacks.get(code)\n                if bucket is None:\n                    bucket = set()\n                    self._subscription_callbacks[code] = bucket\n                bucket.add(callback)\n                info = self._subscription_registry.get(code)\n                if info and info.callbacks:\n                    callbacks_snapshot[code] = tuple(info.callbacks)\n            task = self._subscription_task\n            should_start = task is None or task.done()\n"
if block1 not in text:
    raise SystemExit('block1 not found')
text = text.replace(block1, block1_new)
block2 = "        should_stop = False\n        async with self._subscription_lock:\n            for code in normalized_codes:\n                self._subscription_callbacks.pop(code, None)\n            should_stop = not self._subscription_callbacks\n\n        if should_stop:\n            await self._stop_subscription_loop()\n\n        logger.info(\n            \"AmazingData 进程模式取消订阅 snapshot codes={} 剩余={}\",\n            len(normalized_codes),\n            len(self._subscription_callbacks),\n        )\n        return True\n"
block2_new = "        should_stop = False\n        async with self._subscription_lock:\n            for code in normalized_codes:\n                self._subscription_callbacks.pop(code, None)\n            self._subscription_registry.remove(normalized_codes)\n            should_stop = not self._subscription_registry\n\n        if should_stop:\n            await self._stop_subscription_loop()\n\n        logger.info(\n            \"AmazingData 进程模式取消订阅 snapshot codes={} 剩余={}\",\n            len(normalized_codes),\n            len(self._subscription_registry),\n        )\n        return True\n"
if block2 not in text:
    raise SystemExit('block2 not found')
text = text.replace(block2, block2_new)
block3 = "                async with self._subscription_lock:\n                    callbacks_map = {\n                        code: tuple(callbacks)\n                        for code, callbacks in self._subscription_callbacks.items()\n                        if callbacks\n                    }\n                if not callbacks_map:\n                    return\n"
block3_new = "                async with self._subscription_lock:\n                    snapshot = self._subscription_registry.snapshot()\n                    callbacks_map = {\n                        code: tuple(info.callbacks)\n                        for code, info in snapshot.items()\n                        if info.callbacks\n                    }\n                if not callbacks_map:\n                    return\n"
if block3 not in text:
    raise SystemExit('block3 not found')
text = text.replace(block3, block3_new)
block4 = "        await self._stop_subscription_loop()\n        async with self._subscription_lock:\n            self._subscription_registry.clear()\n"
block4_new = "        await self._stop_subscription_loop()\n        async with self._subscription_lock:\n            self._subscription_callbacks.clear()\n            self._subscription_registry.clear()\n"
if block4 not in text:
    raise SystemExit('block4 not found')
text = text.replace(block4, block4_new)
path.write_text(text, encoding="utf-8")
