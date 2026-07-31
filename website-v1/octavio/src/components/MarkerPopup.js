'use client';

import Image from 'next/image';
import { useState } from 'react';
import { Marker, Popup } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

import Link from 'next/link'
import { Box } from '@mui/material';

export default function MarkerPopup({ instrument }) {
    const [popupVisible, setPopupVisible] = useState(false);

    return (
        <>
            <Marker
                longitude={instrument.longitude}
                latitude={instrument.latitude}
            >
                <Link href={`/instrument/${instrument.instrument_id}`}>
                    <Box
                        // sx={{ color: 'red', fontSize: '24px', cursor: 'pointer' }}
                        onMouseEnter={ () => {setPopupVisible(true)} }
                        onMouseLeave={ () => {setPopupVisible(false)} }
                    >
                        {/* 🎹 */}
                        <Image src="/piano.svg" alt="Piano Icon" width={24} height={24} />
                    </Box>
                </Link>
            </Marker>
            {
                popupVisible &&
                <Popup
                    longitude={instrument.longitude}
                    latitude={instrument.latitude}
                    closeButton={false}
                    anchor="bottom-left"
                    offset={15}
                >
                    {instrument.label}
                </Popup>
            }
        </>
    )
}
