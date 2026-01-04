/**
 * 剪贴板工具函数
 */

import {message} from 'antd';

/**
 * 复制文本到剪贴板
 * @param text 要复制的文本
 * @param showMessage 是否显示提示消息
 * @returns Promise<boolean> 复制是否成功
 */
export async function copyToClipboard(
    text: string,
    showMessage: boolean = true
): Promise<boolean> {
    try {
        // 优先使用现代 Clipboard API
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(text);
            if (showMessage) {
                message.success('已复制到剪贴板');
            }
            return true;
        }

        // 降级方案：使用 execCommand
        const textArea = document.createElement('textarea');
        textArea.value = text;

        // 防止页面滚动
        textArea.style.position = 'fixed';
        textArea.style.left = '-9999px';
        textArea.style.top = '-9999px';

        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);

        if (successful) {
            if (showMessage) {
                message.success('已复制到剪贴板');
            }
            return true;
        } else {
            throw new Error('execCommand copy failed');
        }
    } catch (error) {
        console.error('复制到剪贴板失败:', error);
        if (showMessage) {
            message.error('复制失败，请手动复制');
        }
        return false;
    }
}

/**
 * 从剪贴板读取文本
 * @returns Promise<string | null> 剪贴板中的文本，失败时返回 null
 */
export async function readFromClipboard(): Promise<string | null> {
    try {
        if (navigator.clipboard && window.isSecureContext) {
            const text = await navigator.clipboard.readText();
            return text;
        }

        // 降级方案不支持读取
        console.warn('当前环境不支持读取剪贴板');
        return null;
    } catch (error) {
        console.error('读取剪贴板失败:', error);
        return null;
    }
}

/**
 * 检查剪贴板 API 是否可用
 */
export function isClipboardAvailable(): boolean {
    return !!(navigator.clipboard && window.isSecureContext);
}

export default {
    copyToClipboard,
    readFromClipboard,
    isClipboardAvailable,
};
