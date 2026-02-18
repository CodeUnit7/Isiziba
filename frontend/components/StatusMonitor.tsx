'use client';

import { useState, useEffect } from 'react';
import { Agent, WSMessage, AgentStatus } from '@/types/market';
import { getApiUrl } from '@/lib/config';
import { useMarketContext } from '@/contexts/MarketContext';

export default function StatusMonitor() {
    const [agents, setAgents] = useState<Record<string, AgentStatus>>({});
    const { wsStatus, subscribe } = useMarketContext();
    const [isLoading, setIsLoading] = useState(true);

    // Initial fetch of active agents
    useEffect(() => {
        const fetchAgents = async () => {
            try {
                const res = await fetch(getApiUrl('/agents'));
                if (res.ok) {
                    const data = await res.json();
                    const now = Date.now() / 1000;
                    const initialAgents: Record<string, AgentStatus> = {};

                    data.forEach((agent: any) => {
                        // Include all registered agents (removed 5m restriction)
                        initialAgents[agent.id] = {
                            id: agent.id,
                            agent_id: agent.agent_id || agent.id,
                            name: agent.name,
                            type: (agent.type || (agent.id.includes('buyer') ? 'buyer' : 'seller')) as 'buyer' | 'seller',
                            status: "IDLE",
                            activity: "Ready for market",
                            timestamp: now,
                            global_reputation: agent.global_reputation || 50,
                            total_transactions: agent.total_transactions || 0
                        };
                    });
                    // Merge, don't overwrite if WS already populated something
                    setAgents(prev => ({ ...initialAgents, ...prev }));
                }
            } catch (err) {
                console.error('Failed to fetch initial agents:', err);
            } finally {
                setIsLoading(false);
            }
        };
        fetchAgents();
    }, []);

    useEffect(() => {
        const unsubscribe = subscribe((msg: WSMessage) => {
            if (msg.type === 'agent_status' && msg.agent_id) {
                setAgents((prev) => ({
                    ...prev,
                    [msg.agent_id!]: {
                        id: msg.agent_id!,
                        agent_id: msg.agent_id!,
                        name: msg.name || "Unknown Agent",
                        status: msg.status,
                        activity: msg.activity,
                        timestamp: msg.timestamp,
                        type: (msg.agent_id!.toLowerCase().includes('buyer') ? 'buyer' : 'seller') as 'buyer' | 'seller',
                        global_reputation: prev[msg.agent_id!]?.global_reputation || 50,
                        total_transactions: prev[msg.agent_id!]?.total_transactions || 0
                    }
                }));
            }
        });
        return unsubscribe;
    }, [subscribe]);

    // Update agent status based on heartbeat and cleanup ghosts
    useEffect(() => {
        const interval = setInterval(() => {
            const now = Date.now() / 1000;
            setAgents((prev) => {
                const next = { ...prev };
                let changed = false;
                Object.keys(next).forEach((id) => {
                    const agent = next[id];
                    if (!agent) return;

                    const lastSeen = agent.timestamp || 0;
                    const timeSinceHeartbeat = now - lastSeen;

                    // Mark OFFLINE if > 45s silence (was 15s)
                    if (timeSinceHeartbeat > 45 && agent.status !== 'OFFLINE') {
                        next[id] = { ...agent, status: 'OFFLINE', activity: 'Offline (Last seen > 45s ago)' };
                        changed = true;
                    }

                    // Remove completely if > 300s silence (was 30s)
                    if (timeSinceHeartbeat > 300) {
                        delete next[id];
                        changed = true;
                    }
                });
                return changed ? next : prev;
            });
        }, 5000); // Check every 5s for better performance
        return () => clearInterval(interval);
    }, []);

    const getStatusColor = (status: string) => {
        switch (status.toUpperCase()) {
            case 'NEGOTIATING': return '#8b5cf6'; // Purple
            case 'BUYING':
            case 'SELLING': return '#10b981'; // Green
            case 'IDLE': return '#3b82f6'; // Blue
            case 'OFFLINE': return '#ef4444'; // Red
            case 'EVALUATING': return '#8b5cf6'; // Purple
            default: return '#94a3b8';
        }
    };

    const statusPriority: Record<string, number> = {
        'NEGOTIATING': 1,
        'EVALUATING': 2,
        'BUYING': 3,
        'SELLING': 3,
        'IDLE': 4,
        'OFFLINE': 5
    };

    const agentList = Object.values(agents)
        .sort((a, b) => {
            const statusA = a.status || 'UNKNOWN';
            const statusB = b.status || 'UNKNOWN';
            const pA = statusPriority[statusA.toUpperCase()] || 10;
            const pB = statusPriority[statusB.toUpperCase()] || 10;
            if (pA !== pB) return pA - pB;
            return (b.timestamp || 0) - (a.timestamp || 0); // Recent first within same priority
        });

    return (
        <div className="card" style={{ height: '600px', display: 'flex', flexDirection: 'column' }}>
            <div className="card-header" style={{ flexShrink: 0 }}>
                <span>Agent Fleet Command</span>
                <span className="badge" style={{
                    backgroundColor: wsStatus === 'CONNECTED' ? '#10b981' : '#ef4444',
                    color: '#fff'
                }}>
                    {wsStatus === 'CONNECTED' ? 'LIVE' : 'OFFLINE'}
                </span>
            </div>

            <div style={{
                flex: 1,
                overflowY: 'auto',
                padding: '1rem',
                scrollbarWidth: 'thin',
                scrollbarColor: '#475569 #1e293b'
            }}>
                {isLoading ? (
                    <div className="flex flex-col gap-4 p-4 animate-pulse">
                        <div className="h-20 bg-gray-800 rounded"></div>
                        <div className="h-20 bg-gray-800 rounded"></div>
                        <div className="h-20 bg-gray-800 rounded"></div>
                    </div>
                ) : agentList.length === 0 ? (
                    <div style={{ textAlign: 'center', color: 'var(--secondary)', marginTop: '2rem' }}>
                        Waiting for telemetry from agents...
                    </div>
                ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        {agentList.map((agent) => {
                            const statusColor = getStatusColor(agent.status || 'UNKNOWN');
                            return (
                                <div key={agent.id} className="ticker-item" style={{
                                    flexDirection: 'column',
                                    alignItems: 'flex-start',
                                    borderLeft: `4px solid ${statusColor}`,
                                    paddingLeft: '0.75rem',
                                    background: 'rgba(255,255,255,0.03)',
                                    padding: '0.75rem',
                                    borderRadius: '0 8px 8px 0',
                                    position: 'relative',
                                    transition: 'transform 0.3s ease, background 0.3s ease, border-color 0.3s ease',
                                    transform: agent.status === 'NEGOTIATING' ? 'scale(1.02)' : 'scale(1)',
                                    boxShadow: agent.status === 'NEGOTIATING' ? `0 0 15px ${statusColor}33` : 'none'
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginBottom: '0.25rem' }}>
                                        <span style={{
                                            fontSize: '0.8rem',
                                            fontWeight: 700,
                                            color: statusColor,
                                            display: 'inline-block'
                                        }}>
                                            {(agent.status || 'UNKNOWN').toUpperCase()}
                                        </span>
                                        <span style={{ fontSize: '0.7rem', color: 'var(--secondary)' }}>
                                            {agent.activity || 'No activity'}
                                        </span>
                                    </div>
                                    <div style={{ fontSize: '0.85rem', marginBottom: '0.25rem', color: '#fff', fontWeight: 500 }}>
                                        <div style={{ fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                                            <span style={{ color: 'var(--secondary)', fontWeight: 600 }}>
                                                {agent.type === 'buyer' ? 'Buyer' : agent.type === 'seller' ? 'Seller' : ((agent.agent_id || agent.id).toLowerCase().includes('buyer') ? 'Buyer' : 'Seller')}
                                            </span>
                                            <span style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
                                            <span style={{ color: '#fff', fontWeight: 600 }}>{agent.name || agent.agent_id || agent.id}</span>
                                        </div>
                                        <span style={{ fontSize: '0.75rem', color: 'var(--secondary)', fontFamily: 'monospace' }}>
                                            UID: {agent.agent_id || agent.id}
                                        </span>
                                    </div>

                                    <div style={{
                                        fontSize: '0.8rem',
                                        fontStyle: 'italic',
                                        color: '#cbd5e1',
                                        marginTop: '0.5rem',
                                        padding: '0.5rem',
                                        backgroundColor: 'rgba(255,255,255,0.05)',
                                        borderRadius: '4px',
                                        width: '100%',
                                        borderLeft: '2px solid rgba(255,255,255,0.1)',
                                        transition: 'all 0.3s ease'
                                    }}>
                                        "{agent.activity || 'Monitoring market signals...'}"
                                    </div>

                                    <div style={{
                                        display: 'flex',
                                        justifyContent: 'space-between',
                                        width: '100%',
                                        marginTop: '0.75rem',
                                        paddingTop: '0.5rem',
                                        borderTop: '1px solid rgba(255,255,255,0.05)',
                                        fontSize: '0.65rem'
                                    }}>
                                        <span style={{ color: 'var(--secondary)', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>
                                            Signal Latency
                                        </span>
                                        <span style={{ color: '#94a3b8', fontFamily: 'monospace' }}>
                                            {agent.timestamp ? `${((Date.now() / 1000) - agent.timestamp).toFixed(1)}s` : 'N/A'}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
            <style jsx>{`
                .ticker-item:hover {
                    background: rgba(255,255,255,0.06) !important;
                    transform: translateY(-2px);
                }
            `}</style>
        </div >
    );
}
