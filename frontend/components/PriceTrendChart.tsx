'use client';

import { useEffect, useState, useMemo } from 'react';
import { WSMessage } from '@/types/market';
import { getApiUrl } from '@/lib/config';
import { useMarketContext } from '@/contexts/MarketContext';

// TrendPoint is largely compatible with Transaction
type TrendPoint = {
    timestamp: number;
    price: number;
    product: string;
    explanation: string;
    tx_id: string;
};

export default function PriceTrendChart() {
    const [trends, setTrends] = useState<TrendPoint[]>([]);
    const [selectedProduct, setSelectedProduct] = useState<string>('Auto-Rotate'); // 'Auto-Rotate' or specific product name
    const [autoRotateIndex, setAutoRotateIndex] = useState<number>(0);
    const [hoverPoint, setHoverPoint] = useState<TrendPoint | null>(null);
    const { subscribe } = useMarketContext();

    // Configuration
    const ROTATION_INTERVAL_MS = (parseInt(process.env.NEXT_PUBLIC_CHART_ROTATION_SECONDS || '120', 10)) * 1000;

    // Initial fetch
    useEffect(() => {
        const fetchTrends = async () => {
            try {
                const res = await fetch(getApiUrl('/market/trends'));
                if (res.ok) {
                    const data = await res.json();
                    setTrends(data.trends || []);
                }
            } catch (err) {
                console.error('Failed to fetch trends:', err);
            }
        };
        fetchTrends();
    }, []);

    // Subscribe to shared WS events
    useEffect(() => {
        return subscribe((msg: WSMessage) => {
            if (msg.type === 'market_event' && msg.data.status === 'COMPLETED') {
                const data = msg.data;
                setTrends(prev => {
                    // Avoid duplicates
                    if (prev.find(t => t.tx_id === (data.tx_id || data.id))) return prev;

                    const newPoint: TrendPoint = {
                        timestamp: data.timestamp,
                        price: data.amount,
                        product: data.product || 'Unknown',
                        explanation: data.reasoning || 'Market transaction finalized.',
                        tx_id: data.tx_id || data.id
                    };

                    // Keep only the last 100 points per product to avoid memory issues if needed,
                    // but for now just global 500 is fine or just let it grow a bit more.
                    // The slice(-100) was global, which might be too aggressive if we have many products.
                    // Let's keep 200 for now.
                    const next = [...prev, newPoint];
                    return next.sort((a, b) => a.timestamp - b.timestamp).slice(-200);
                });
            }
        });
    }, [subscribe]);

    const productList = useMemo(() => {
        const set = new Set(trends.map(t => t.product));
        return Array.from(set).sort();
    }, [trends]);

    // Rotation Logic
    // Rotation Logic: Only depends on selection mode
    useEffect(() => {
        if (selectedProduct !== 'Auto-Rotate') return;

        const interval = setInterval(() => {
            // Just increment indefinitely, handle modulo at display time
            setAutoRotateIndex(prev => prev + 1);
        }, ROTATION_INTERVAL_MS);

        return () => clearInterval(interval);
    }, [selectedProduct, ROTATION_INTERVAL_MS]);

    // Determine which product to show
    const displayProduct = useMemo(() => {
        if (productList.length === 0) return null;
        if (selectedProduct === 'Auto-Rotate') {
            return productList[autoRotateIndex % productList.length];
        }
        return selectedProduct;
    }, [selectedProduct, productList, autoRotateIndex]);

    const filteredTrends = useMemo(() => {
        if (!displayProduct) return [];
        let filtered = trends.filter(t => t.product === displayProduct);
        return [...filtered].sort((a, b) => a.timestamp - b.timestamp);
    }, [trends, displayProduct]);

    // Chart dimensions
    const width = 800;
    const height = 450;
    const padding = 40;

    const chartData = useMemo(() => {
        if (filteredTrends.length === 0) return null;

        const prices = filteredTrends.map(t => t.price);
        const minPrice = Math.min(...prices) * 0.95;
        const maxPrice = Math.max(...prices) * 1.05;
        const priceRange = maxPrice - minPrice || 1; // Prevent division by zero

        const times = filteredTrends.map(t => t.timestamp);
        const minTime = Math.min(...times);
        const maxTime = Math.max(...times);
        const timeRange = maxTime - minTime || 1;

        const points = filteredTrends.map(t => ({
            x: padding + ((t.timestamp - minTime) / timeRange) * (width - 2 * padding),
            y: height - padding - ((t.price - minPrice) / priceRange) * (height - 2 * padding),
            data: t
        }));

        // Generate Path
        let path = '';
        if (points.length > 0) {
            path = `M ${points[0].x} ${points[0].y} ` + points.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ');
        }

        return { points, path, minPrice, maxPrice };
    }, [filteredTrends]);

    return (
        <div className="card col-span-3" style={{ gridColumn: 'span 3', minHeight: '600px', position: 'relative' }}>
            <div className="card-header flex justify-between items-center">
                <div className="flex items-center gap-4">
                    <span>Market Price Trends</span>
                    {displayProduct && (
                        <span style={{
                            backgroundColor: '#f59e0b',
                            color: '#000',
                            fontSize: '0.7rem',
                            fontWeight: 900,
                            padding: '4px 10px',
                            borderRadius: '2px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.1em',
                            marginLeft: '1rem',
                            boxShadow: '0 0 15px rgba(245, 158, 11, 0.3)',
                            display: 'inline-block'
                        }}>
                            {displayProduct}
                        </span>
                    )}
                </div>
                <select
                    value={selectedProduct}
                    onChange={(e) => setSelectedProduct(e.target.value)}
                    className="bg-slate-800 text-white border border-slate-700 rounded text-xs px-2 py-0.5 outline-none focus:border-blue-500"
                >
                    <option value="Auto-Rotate">Auto-Rotate</option>
                    {productList.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
            </div>

            <div className="p-8 h-full flex flex-col">
                {filteredTrends.length < 2 ? (
                    <div className="flex-1 flex flex-col items-center justify-center text-gray-500 text-sm gap-2">
                        <span>Waiting for more transactions to plot trends...</span>
                        {displayProduct && <span className="text-xs text-slate-600">Current Product: {displayProduct}</span>}
                    </div>
                ) : chartData && (
                    <div className="relative flex-1">
                        <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="450" className="overflow-visible">
                            {/* Grid Lines */}
                            <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="#3b82f6" strokeOpacity="0.5" strokeWidth="2" />
                            <line x1={padding} y1={padding} x2={padding} y2={height - padding} stroke="#3b82f6" strokeOpacity="0.5" strokeWidth="2" />

                            {/* Line */}
                            <path
                                d={chartData.path}
                                fill="none"
                                stroke="#8b5cf6"
                                strokeWidth="3"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                className="transition-all duration-500"
                            />

                            {/* Bubbles */}
                            {chartData.points.map((p, i) => (
                                <g key={i}>
                                    <circle
                                        cx={p.x}
                                        cy={p.y}
                                        r="6"
                                        fill="#f59e0b"
                                        className="cursor-pointer drop-shadow-lg hover:r-8 transition-all"
                                        onMouseEnter={() => setHoverPoint(p.data)}
                                        onMouseLeave={() => setHoverPoint(null)}
                                    />
                                    {/* Invisible hit target */}
                                    <circle
                                        cx={p.x}
                                        cy={p.y}
                                        r="12"
                                        fill="transparent"
                                        onMouseEnter={() => setHoverPoint(p.data)}
                                        onMouseLeave={() => setHoverPoint(null)}
                                    />
                                </g>
                            ))}

                            {/* Axis Labels */}
                            <text x={padding - 10} y={padding} fill="#3b82f6" className="text-xs font-bold" textAnchor="end">${chartData.maxPrice.toFixed(0)}</text>
                            <text x={padding - 10} y={height - padding} fill="#3b82f6" className="text-xs font-bold" textAnchor="end">${chartData.minPrice.toFixed(0)}</text>
                        </svg>

                        {/* Hover Tooltip */}
                        {hoverPoint && (
                            <div className="absolute left-1/2 top-2 -translate-x-1/2 bg-slate-800 border border-blue-500 p-4 rounded-lg w-[300px] z-10 shadow-2xl pointer-events-none animate-in fade-in zoom-in-95 duration-200">
                                <div className="text-xs text-blue-400 font-bold mb-1">
                                    {hoverPoint.product.toUpperCase()} @ ${hoverPoint.price}
                                </div>
                                <div className="text-sm text-slate-300 leading-snug">
                                    {hoverPoint.explanation}
                                </div>
                                <div className="text-[0.6rem] text-slate-500 mt-2 font-mono">
                                    TXID: {hoverPoint.tx_id.substring(0, 8)}... | {new Date(hoverPoint.timestamp * 1000).toLocaleTimeString()}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
