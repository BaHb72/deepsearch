import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import StrategyParamForm from '../StrategyParamForm';
import type { UnifiedParamDef, UnifiedParamMap } from '../types';

describe('StrategyParamForm', () => {
    it('renders empty text when no definitions', () => {
        render(
            <StrategyParamForm
                definitions={{}}
                value={{}}
                onChange={() => {}}
                emptyText="暂无参数"
            />,
        );

        expect(screen.getByText('暂无参数')).toBeInTheDocument();
    });

    it('emits changed values for switch and text input', () => {
        const definitions: Record<string, UnifiedParamDef> = {
            enabled: {
                type: 'bool',
                label: '启用',
            },
            keyword: {
                type: 'str',
                label: '关键字',
            },
        };
        const value: UnifiedParamMap = {
            enabled: false,
            keyword: 'ma',
        };
        const onChange = jest.fn();

        render(
            <StrategyParamForm
                definitions={definitions}
                value={value}
                onChange={onChange}
            />,
        );

        fireEvent.click(screen.getByRole('switch'));
        fireEvent.change(screen.getByDisplayValue('ma'), { target: { value: 'momentum' } });

        expect(onChange).toHaveBeenCalledWith({
            enabled: true,
            keyword: 'ma',
        });
        expect(onChange).toHaveBeenCalledWith({
            enabled: false,
            keyword: 'momentum',
        });
    });
});
