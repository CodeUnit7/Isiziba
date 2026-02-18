"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode, useRef, useCallback } from 'react';
import { getApiUrl, getWsUrl } from '@/lib/config';
import { WSMessage } from '@/types/market';

type WsStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED';

interface MarketContextType {
    agentNames: Record<string, string>;
    agentRoles: Record<string, string>;
    loading: boolean;
    refreshAgents: () => Promise<void>;
    wsStatus: WsStatus;
    subscribe: (callback: (msg: WSMessage) => void) => () => void;
}

const MarketContext = createContext<MarketContextType | undefined>(undefined);

export function MarketProvider({ children }: { children: ReactNode }) {
    const [agentNames, setAgentNames] = useState<Record<string, string>>({});
    const [agentRoles, setAgentRoles] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [wsStatus, setWsStatus] = useState<WsStatus>('CONNECTING');

    // WebSocket refs
    const wsRef = useRef<WebSocket | null>(null);
    const listenersRef = useRef<Set<(msg: WSMessage) => void>>(new Set());
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

    const fetchAgents = async () => {
        try {
            const res = await fetch(getApiUrl('/market/agents'));
            if (res.ok) {
                const agents = await res.json();
                const nameMap: Record<string, string> = {};
                const roleMap: Record<string, string> = {};

                agents.forEach((a: any) => {
                    const id = a.id || a.agent_id;
                    nameMap[id] = a.name || id;
                    roleMap[id] = a.type || (id.toLowerCase().includes('buyer') ? 'buyer' : 'seller');
                });

                setAgentNames(nameMap);
                setAgentRoles(roleMap);
            }
        } catch (err) {
            console.error('Failed to fetch agents:', err);
        } finally {
            setLoading(false);
        }
    };

    const connectWs = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        const ws = new WebSocket(getWsUrl('/ws/market'));
        wsRef.current = ws;
        setWsStatus('CONNECTING');

        ws.onopen = () => {
            console.log('WS Connection Open. Sending identification...');
            ws.send(JSON.stringify({ type: 'identify_view' }));
            setWsStatus('CONNECTED');
        };

        ws.onclose = () => {
            setWsStatus('DISCONNECTED');
            wsRef.current = null;
            // Reconnect logic
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = setTimeout(connectWs, 3000);
        };

        ws.onerror = (err) => {
            // Suppress errors if the connection is already closing/closed (normal during restarts)
            if (ws.readyState === WebSocket.CLOSING || ws.readyState === WebSocket.CLOSED) {
                console.log('Market WS Connection closed (normal)');
                return;
            }
            console.error('Market WS Error state:', ws.readyState);
            console.error('Market WS details:', err);
            ws.close();
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data) as WSMessage;
                // Broadcast to listeners
                listenersRef.current.forEach(listener => listener(msg));
            } catch (e) {
                console.error('Failed to parse WS message:', e);
            }
        };
    }, []);

    const subscribe = useCallback((callback: (msg: WSMessage) => void) => {
        listenersRef.current.add(callback);
        return () => {
            listenersRef.current.delete(callback);
        };
    }, []);

    useEffect(() => {
        fetchAgents();
        connectWs();
        return () => {
            wsRef.current?.close();
            clearTimeout(reconnectTimeoutRef.current);
        };
    }, [connectWs]);

    return (
        <MarketContext.Provider value={{
            agentNames,
            agentRoles,
            loading,
            refreshAgents: fetchAgents,
            wsStatus,
            subscribe
        }}>
            {children}
        </MarketContext.Provider>
    );
}

export function useMarketContext() {
    const context = useContext(MarketContext);
    if (context === undefined) {
        throw new Error('useMarketContext must be used within a MarketProvider');
    }
    return context;
}
