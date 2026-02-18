'use client';

import { useEffect, useState } from 'react';
import { WSMessage, Offer } from '@/types/market';
import { getApiUrl, CURRENCY } from '@/lib/config';
import { useMarketContext } from '@/contexts/MarketContext';

export default function OrderBook() {
    const [bids, setBids] = useState<Offer[]>([]);
    const [asks, setAsks] = useState<Offer[]>([]);
    const { wsStatus, subscribe } = useMarketContext();
    const [isLoading, setIsLoading] = useState(true);

    // Initial fetch
    useEffect(() => {
        const fetchMarketData = async () => {
            setIsLoading(true);
            try {
                // Fetch existing offers (Asks)
                const res = await fetch(getApiUrl('/market/feed'));
                if (res.ok) {
                    const data = await res.json();
                    if (data.feed) {
                        const initialAsks = data.feed.map((o: any) => ({
                            id: o.offer_id,
                            price: o.price,
                            product: o.product,
                            agent_id: o.seller_id,
                            timestamp: o.created_at,
                            type: 'ask',
                            agent_name: o.agent_name
                        }));
                        setAsks(prev => {
                            const prevIds = new Set(prev.map(a => a.id));
                            const uniqueInitial = initialAsks.filter((a: Offer) => !prevIds.has(a.id));
                            return [...uniqueInitial, ...prev].sort((a: Offer, b: Offer) => a.price - b.price);
                        });
                    }
                }
            } catch (err) {
                console.error("Failed to fetch order book data:", err);
            } finally {
                setIsLoading(false);
            }
        };

        const fetchActiveBids = async () => {
            try {
                const res = await fetch(getApiUrl('/market/active'));
                if (res.ok) {
                    const data = await res.json();
                    if (data.items) {
                        // Process Requests (Bids)
                        const activeRequests = data.items
                            .filter((i: any) => i.type === 'Request')
                            .map((r: any) => ({
                                id: r.id || `req-${r.timestamp}`,
                                price: r.max_budget,
                                product: r.item,
                                agent_id: r.buyer_id,
                                timestamp: r.timestamp,
                                type: 'bid',
                                agent_name: r.agent_name
                            }));

                        setBids(prev => {
                            const prevIds = new Set(prev.map(b => b.id));
                            const uniqueInitial = activeRequests.filter((b: Offer) => !prevIds.has(b.id));
                            return [...uniqueInitial, ...prev].sort((a: Offer, b: Offer) => b.price - a.price);
                        });

                        // Process Offers (Asks) - optional but good for consistency
                        const activeOffers = data.items
                            .filter((i: any) => i.type === 'Offer')
                            .map((o: any) => ({
                                id: o.offer_id,
                                price: o.price,
                                product: o.product,
                                agent_id: o.seller_id,
                                timestamp: o.created_at,
                                type: 'ask',
                                agent_name: o.agent_name
                            }));

                        setAsks(prev => {
                            const prevIds = new Set(prev.map(a => a.id));
                            const uniqueInitial = activeOffers.filter((a: Offer) => !prevIds.has(a.id));
                            return [...uniqueInitial, ...prev].sort((a: Offer, b: Offer) => a.price - b.price);
                        });
                    }
                }
            } catch (err) {
                console.error("Failed to fetch active bids:", err);
            }
        };

        fetchMarketData();
        fetchActiveBids();
    }, []);

    // Shared WebSocket subscription
    useEffect(() => {
        return subscribe((msg: WSMessage) => {
            if (msg.type === 'market_event') {
                const data = msg.data;

                // Identify Bids (Requests)
                if (data.type === 'Request') {
                    const newBid: Offer = {
                        id: data.id || `req-${Date.now()}`,
                        price: data.max_budget || 0,
                        product: data.item,
                        agent_id: data.buyer_id,
                        timestamp: data.timestamp,
                        type: 'bid',
                        agent_name: data.agent_name
                    };
                    setBids(prev => {
                        const filtered = prev.filter(b => b.id !== newBid.id);
                        return [newBid, ...filtered].sort((a, b) => b.price - a.price).slice(0, 50);
                    });
                }
                // Identify Asks (Offers)
                else if (data.offer_id && typeof data.price === 'number') {
                    const newAsk: Offer = {
                        id: data.offer_id,
                        price: data.price,
                        product: data.product,
                        agent_id: data.seller_id || data.sender_id,
                        timestamp: data.created_at || data.timestamp,
                        type: 'ask',
                        agent_name: data.agent_name
                    };
                    setAsks(prev => {
                        const filtered = prev.filter(a => a.id !== newAsk.id);
                        return [newAsk, ...filtered].sort((a, b) => a.price - b.price).slice(0, 50);
                    });
                }
            }
        });
    }, [subscribe]);

    const OrderItem = ({ order, isAsk }: { order: Offer, isAsk: boolean }) => {
        const statusColor = isAsk ? '#f59e0b' : '#3b82f6'; // Amber for Ask, Blue for Bid

        return (
            <div className="ticker-item" style={{
                flexDirection: 'column',
                alignItems: 'flex-start',
                borderLeft: `4px solid ${statusColor}`,
                paddingLeft: '0.75rem',
                background: 'rgba(255,255,255,0.03)',
                padding: '0.75rem',
                borderRadius: '0 8px 8px 0',
                marginBottom: '1.5rem',
                position: 'relative',
                transition: 'transform 0.2s ease, background 0.2s ease',
                cursor: 'default'
            }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginBottom: '0.25rem' }}>
                    <span style={{
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        color: statusColor,
                        display: 'inline-block',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em'
                    }}>
                        {isAsk ? 'ASK (OFFER)' : 'BID (REQUEST)'}
                    </span>
                    <span style={{ fontSize: '0.7rem', color: 'var(--secondary)', fontFamily: 'monospace' }}>
                        {order.timestamp ? new Date(order.timestamp * 1000).toLocaleTimeString() : 'LIVE'}
                    </span>
                </div>
                <div style={{ fontSize: '0.85rem', marginBottom: '0.25rem', color: '#fff', fontWeight: 500 }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#fff', marginBottom: '2px' }}>
                        {order.product}
                    </div>
                    <div style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ color: 'var(--secondary)' }}>Agent:</span>
                        <span style={{ color: '#cbd5e1', fontFamily: 'monospace' }}>
                            {order.agent_name || (order.agent_id.startsWith('ext-') ? order.agent_id.split('-').slice(1).join('-').substring(0, 15) + '...' : order.agent_id.substring(0, 12))}
                        </span>
                    </div>
                </div>

                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    width: '100%',
                    marginTop: '0.5rem',
                    paddingTop: '0.5rem',
                    borderTop: '1px solid rgba(255,255,255,0.05)'
                }}>
                    <span style={{ fontSize: '0.65rem', color: 'var(--secondary)', textTransform: 'uppercase', fontWeight: 700 }}>
                        Price
                    </span>
                    <div style={{ color: statusColor, fontSize: '0.9rem', fontWeight: 700, fontFamily: 'monospace' }}>
                        {typeof order.price === 'number' ? order.price.toFixed(2) : '---'} <span style={{ fontSize: '0.7rem', opacity: 0.7 }}>{CURRENCY}</span>
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="card col-span-2" style={{ gridColumn: 'span 2', height: '600px', display: 'flex', flexDirection: 'column' }}>
            <div className="card-header" style={{ flexShrink: 0 }}>
                <span>Order Book</span>
                <span className="badge" style={{
                    backgroundColor: wsStatus === 'CONNECTED' ? '#10b981' : '#ef4444',
                    color: '#fff'
                }}>
                    {wsStatus === 'CONNECTED' ? 'LIVE' : 'OFFLINE'}
                </span>
            </div>

            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
                {/* Bids Column */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: '1px solid rgba(255,255,255,0.05)' }}>
                    <div style={{
                        padding: '0.5rem',
                        textAlign: 'center',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        color: '#3b82f6',
                        background: 'rgba(59, 130, 246, 0.05)',
                        borderBottom: '1px solid rgba(59, 130, 246, 0.1)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em'
                    }}>
                        Bids (Buying)
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }} className="custom-scrollbar">
                        {isLoading && <div className="text-gray-500 text-center p-4 text-xs animate-pulse">Loading Bids...</div>}
                        {!isLoading && bids.length === 0 && <div className="text-gray-500 text-center p-4 text-xs">No active bids</div>}
                        {bids.map(order => <OrderItem key={order.id} order={order} isAsk={false} />)}
                    </div>
                </div>

                {/* Asks Column */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                    <div style={{
                        padding: '0.5rem',
                        textAlign: 'center',
                        fontSize: '0.7rem',
                        fontWeight: 700,
                        color: '#f59e0b',
                        background: 'rgba(245, 158, 11, 0.05)',
                        borderBottom: '1px solid rgba(245, 158, 11, 0.1)',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em'
                    }}>
                        Asks (Selling)
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }} className="custom-scrollbar">
                        {isLoading && <div className="text-gray-500 text-center p-4 text-xs animate-pulse">Loading Offers...</div>}
                        {!isLoading && asks.length === 0 && <div className="text-gray-500 text-center p-4 text-xs">No active asks</div>}
                        {asks.map(order => <OrderItem key={order.id} order={order} isAsk={true} />)}
                    </div>
                </div>
            </div>

            <div style={{
                padding: '0.5rem 1rem',
                borderTop: '1px solid rgba(255,255,255,0.05)',
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '0.7rem',
                color: 'var(--secondary)'
            }}>
                <span>Total Liquidity: {bids.length + asks.length} orders</span>
                <span>Spread: {bids.length > 0 && asks.length > 0 ? (asks[0].price - bids[0].price).toFixed(2) : '-.--'}</span>
            </div>

            <style jsx>{`
                .ticker-item:hover {
                    background: rgba(255,255,255,0.06) !important;
                    transform: translateX(2px);
                }
            `}</style>
        </div>
    );
}
