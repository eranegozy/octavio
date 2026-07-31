'use client';

import dynamic from 'next/dynamic';

import Box from '@mui/material/Box';
import { width } from '@mui/system';

// Dynamically import OpenMap to avoid SSR issues
const OpenMap = dynamic(() => import('../components/OpenMap'), {
  ssr: false, // Ensure client-side rendering
});

export default function HomePage() {
  return (
    // <Box component="main" sx={{ height: '100%', width: '100%' }}>
    <OpenMap />
    // </Box>
  );
}
