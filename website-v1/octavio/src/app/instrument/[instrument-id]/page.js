'use client';

import { useParams } from 'next/navigation'
// import InstrumentDisplay from '@/components/InstrumentDisplay';
import Box from '@mui/material/Box';
import dynamic from 'next/dynamic';

// Dynamically import OpenMap to avoid SSR issues
const InstrumentDisplay = dynamic(() => import('@/components/InstrumentDisplay'), {
    ssr: false, // Ensure client-side rendering
});

export default function InstrumentPage() {
    const params = useParams();
    const instrumentID = params["instrument-id"];
    return (
        <InstrumentDisplay instrument_id={instrumentID} />
    );
}
