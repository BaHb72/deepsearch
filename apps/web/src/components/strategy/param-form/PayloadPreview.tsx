import React, { useMemo } from 'react';
import { Space, Typography } from 'antd';

const { Text } = Typography;

export interface PayloadPreviewProps {
    payload: unknown;
    maxHeight?: number;
    showCopy?: boolean;
}

const PayloadPreview: React.FC<PayloadPreviewProps> = ({
    payload,
    maxHeight = 300,
    showCopy = true,
}) => {
    const previewText = useMemo(() => {
        try {
            return JSON.stringify(payload ?? {}, null, 2);
        } catch {
            return String(payload);
        }
    }, [payload]);

    return (
        <div>
            <Space size={8} style={{ marginBottom: 8 }}>
                <Text type="secondary">payload 预览</Text>
                {showCopy && <Text copyable={{ text: previewText }} />}
            </Space>

            <div
                style={{
                    border: '1px solid #1f2b40',
                    borderRadius: 8,
                    background: '#0f1728',
                    color: '#cfdaef',
                    padding: '10px 12px',
                    maxHeight,
                    overflow: 'auto',
                    whiteSpace: 'pre',
                    fontFamily: 'Consolas, Menlo, monospace',
                    fontSize: 12,
                    lineHeight: 1.4,
                }}
            >
                {previewText}
            </div>
        </div>
    );
};

export default PayloadPreview;
