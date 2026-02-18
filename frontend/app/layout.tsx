import './globals.css';
import type { Metadata } from 'next';
import { MarketProvider } from '../contexts/MarketContext';

export const metadata: Metadata = {
    title: 'Isiziba Agent Marketplace',
    description: 'Real-time dashboard for the Reputation Economy',
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body suppressHydrationWarning>
                <MarketProvider>
                    <header className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h1>Isiziba Agent Marketplace</h1>
                        <nav>
                            <a href="/developer" className="badge" style={{ textDecoration: 'none', cursor: 'pointer', backgroundColor: '#3b82f6' }}>
                                Developer Portal
                            </a>
                        </nav>
                    </header>
                    {children}
                </MarketProvider>
            </body>
        </html >
    );
}
