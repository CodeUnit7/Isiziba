import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL;

if (!BACKEND_URL) {
    console.error('❌ BACKEND_URL environment variable is not set.');
}

export const dynamic = 'force-dynamic';

export async function GET() {
    try {
        const res = await fetch(`${BACKEND_URL}/market/negotiations`, {
            cache: 'no-store'
        });

        if (!res.ok) {
            return NextResponse.json({ error: 'Failed to fetch negotiations' }, { status: res.status });
        }

        const data = await res.json();
        return NextResponse.json(data.negotiations);
    } catch (error) {
        console.error('Error fetching negotiations:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
