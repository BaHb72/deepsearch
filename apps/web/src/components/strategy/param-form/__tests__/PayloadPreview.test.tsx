import React from 'react';
import { render, screen } from '@testing-library/react';
import PayloadPreview from '../PayloadPreview';

describe('PayloadPreview', () => {
    it('renders formatted json text', () => {
        render(
            <PayloadPreview
                payload={{
                    strategy_id: 'ma_crossover',
                    limit: 20,
                }}
                showCopy={false}
            />,
        );

        expect(screen.getByText(/payload 预览/)).toBeInTheDocument();
        expect(screen.getByText(/"strategy_id": "ma_crossover"/)).toBeInTheDocument();
        expect(screen.getByText(/"limit": 20/)).toBeInTheDocument();
    });
});
