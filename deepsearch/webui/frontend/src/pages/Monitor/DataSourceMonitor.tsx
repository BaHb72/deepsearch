import React from 'react';
import { PageContainer } from '@ant-design/pro-components';
import { Result } from 'antd';

const DataSourceMonitor: React.FC = () => {
    return (
        <PageContainer
            header={{
                title: '数据源监控',
                ghost: true,
            }}
        >
            <Result
                status="info"
                title="数据源监控"
                subTitle="此功能正在开发中，请访问 数据源浏览器 获取数据源信息。"
            />
        </PageContainer>
    );
};

export default DataSourceMonitor;
