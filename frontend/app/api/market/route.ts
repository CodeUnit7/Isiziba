import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL;

if (!BACKEND_URL) {
    console.error('❌ BACKEND_URL environment variable is not set.');
}

export const dynamic = 'force-dynamic';

export async function GET() {
    try {
        const res = await fetch(`${BACKEND_URL}/market/feed`, {
            cache: 'no-store'
        });

        if (!res.ok) {
            return NextResponse.json({ error: 'Failed to fetch market feed' }, { status: res.status });
        }

        const data = await res.json();
        // The backend returns { "feed": [...] }
        // We want to map it to the format expected by the frontend
        const events = data.feed.map((item: any) => ({
            type: 'market_event',
            data: item
        }));

        return NextResponse.json(events);
    } catch (error) {
        console.error('Error fetching market feed:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
